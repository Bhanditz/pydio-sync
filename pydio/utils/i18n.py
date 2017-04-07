#
# Copyright 2007-2016 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
#
#  Pydio is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pydio is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Pydio.  If not, see <http://www.gnu.org/licenses/>.
#
#  The latest code can be found at <http://pyd.io/>.
#
# -*- coding: utf-8 -*-

import os, sys
import locale
import gettext
import logging
from pathlib import *

# Change this variable to your app name!
#  The translation files will be under
#  @LOCALE_DIR@/@LANGUAGE@/LC_MESSAGES/@APP_NAME@.mo
APP_NAME = "pydio"
if getattr(sys, 'frozen', False):
    LOCALE_DIR = str((Path(sys._MEIPASS)) / 'res' / 'i18n' )
else:
    LOCALE_DIR = str(Path(__file__).parent.parent / 'res' / 'i18n')


# This is ok for maemo. Not sure in a regular desktop:

# Now we need to choose the language. We will provide a list, and gettext
# will use the first translation available in the list
#
#  In maemo it is in the LANG environment variable
#  (on desktop is usually LANGUAGES)
def get_default_language():
    DEFAULT_LANGUAGES = os.environ.get('LANG', '').split(':')
    DEFAULT_LANGUAGES += ['en_US']
    languages = []
    if sys.platform == "darwin":
        try:
            languages += [os.popen("defaults read .GlobalPreferences AppleLanguages | tr -d [:space:] | cut -c2-3").read()[:-1]]
        except Exception as e:
            logging.debug("There was a problem getting the language. " + str(e.message))
            logging.exception(e)

    lc, encoding = locale.getdefaultlocale()
    if lc:
        languages = [lc]

    # Concat all languages (env + default locale),
    #  and here we have the languages and location of the translations
    languages += DEFAULT_LANGUAGES
    logging.info("LANGUAGE guessed: " + str(languages))
    return languages

def get_languages():
    try:
        from pydio.utils.global_config import GlobalConfigManager
    except ImportError:
        from utils.global_config import GlobalConfigManager
    try:
        conf = GlobalConfigManager.Instance().get_general_config()
    except Exception:
        # languages not ready, default to English
        return ["en_US"]
    languages = []
    try:
        if conf["language"] == "":
            languages = get_default_language()
        else:
            return [conf["language"]]
    except KeyError:
        languages = get_default_language()
    return languages


languages = get_languages()
mo_location = LOCALE_DIR
gettext.install(True, localedir=None, unicode=1)
gettext.find(APP_NAME, mo_location)
gettext.textdomain(APP_NAME)
gettext.bind_textdomain_codeset(APP_NAME, "UTF-8")
language = gettext.translation(APP_NAME, mo_location, languages=languages, fallback=True)

"""
New process:
 > pydio-sync-agent --extract_html=extract
 MANUALLY EDIT PO FILES
 > pydio-sync-agent --extract_html=compile

To add a new language :
 see below and edit extract_html in main.py

-- OBSOLETE Kept for reference, useful to add languages --
Utilitary to transform HTML strings to PO compatible strings.
Process is the following
* In PY files, declare the following import, and use _('')
    from pydio.utils import i18n
    _ = i18n.language.ugettext
* In HTML files, Use {{_('')}} function.
    Make sure to assign the function to the scope:
    > $scope._ = window.translate;

* Update the content of html_strings.py
    > pydio-sync-agent --extract_html=extract
    This will update the content of res/i18n/html_strings.py with all html strings in a python format

* Update the pydio.pot file by using gettext standard command (from the root of pydio source folder)
    > xgettext --language=Python --keyword=_ --output=res/i18n/pydio.pot `find . -name "*.py"`

* Merge its content into existing PO files using msgmerge. For example for french:
    > msgmerge -vU fr.po pydio.pot

* To add a new language, use msginit
    > msginit --input=pydio.pot --locale=fr_FR --output-file=fr.po

* Manually update PO files with missing strings
* Compile PO to MO files using msgfmt
    > msgfmt fr.po --output-file fr/LC_MESSAGES/pydio.mo

* Compile PO to JSON file using application tool
    > pydio-sync-agent --extract_html=compile
    This will update the file ui/res/i18n.js that is loaded by the UI and contains all languages.


"""
class PoProcessor:

    def __init__(self):
        pass

    def po_to_json(self, glob_expr, dest_file):

        import json
        import polib
        import glob

        files = glob.glob(glob_expr)
        dest = open(dest_file, "w")
        dest.write('window.PydioLangs={};\n')

        for srcfile in files:

            print("INFO: converting %s to %s" % (srcfile, dest_file))

            xlate_map = {}

            po = polib.pofile(srcfile, autodetect_encoding=False, encoding="utf-8", wrapwidth=-1)
            for entry in po:
                if entry.obsolete or entry.msgstr == '' or entry.msgstr == entry.msgid:
                    continue

                xlate_map[entry.msgid] = entry.msgstr

            lang = os.path.basename(srcfile).replace(".po", "")
            dest.write('window.PydioLangs["%s"]=' % lang)
            dest.write(json.dumps(xlate_map, sort_keys= True))
            dest.write(';\n')

        dest.close()

    def extract_html_strings(self,file_name):
        import re
        groups = []
        with open(file_name) as fp:
            for line in fp:
                mo = re.findall("_\('(.*?)'", line)
                if mo:
                    groups += mo
        return groups

    def extract_all_html_strings(self, root_html, output_file):
        strings = []
        logging.info(root_html)
        # Scan html files in root_html for translations strings
        for root, dirs, files in os.walk(root_html):
            for file in files:
                if file.endswith(".html") and root.find('node_modules') == -1:
                    html_file = os.path.join(root, file)
                    logging.info("Scanning " + html_file)
                    strings += self.extract_html_strings(html_file)

        index = 1
        with open(output_file, 'w') as fp:
            fp.write('def _(a_string): return a_string\n')
            for a_string in strings:
                fp.write('var_%i=_(\'%s\')\n' % (index, a_string,))
                index += 1

        return len(strings)
