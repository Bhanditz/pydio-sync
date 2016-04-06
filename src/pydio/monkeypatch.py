#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
#  This file is part of Pydio.
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
# coding=utf-8
import sys
import requests.certs
from pathlib import *
import os
import logging

def _load_backends():
    "ensure that all keyring backends are loaded"
    from keyring.backend import _load_backend

    backends = ('file', 'Gnome', 'Google', 'keyczar', 'multi', 'OS_X', 'pyfs', 'SecretService', 'Windows')
    list(map(_load_backend, backends))

import keyring.backend
keyring.backend._load_backends = _load_backends

# Fix to the bug in requests package, to load the certificates while running in frozen state
# ref: https://github.com/pydio/pydio-sync/issues/33
if getattr(sys, 'frozen', False):
    def _certs_where():
        return str((Path(sys._MEIPASS)) / 'res' / 'cacert.pem')
    requests.certs.where = _certs_where
    os.environ['REQUESTS_CA_BUNDLE'] = requests.certs.where()
    logging.info("Setting certificate path to " + requests.certs.where())

if sys.getfilesystemencoding() is not None:
    fs_encoding = sys.getfilesystemencoding()
else:
    logging.warning('Filesystem encoding forced to UTF-8')
    fs_encoding = 'UTF-8'

if not fs_encoding and sys.platform.startswith('linux'):
    def _watchdog_encode(path):
        if isinstance(path, unicode):
            path = path.encode('utf-8', 'strict')
        return path

    def _watchdog_decode(path):
        if isinstance(path, str):
            path = path.decode('utf-8', 'strict')
        return path

    import watchdog.utils.unicode_paths
    watchdog.utils.unicode_paths.encode = _watchdog_encode
    watchdog.utils.unicode_paths.decode = _watchdog_decode
