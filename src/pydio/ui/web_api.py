#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
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
# -*- coding: utf-8 -*-

from flask import Flask
from flask_restful import Api

from flask import request, redirect, Response
from flask.ext.restful import Resource
from requests.exceptions import SSLError, ProxyError, TooManyRedirects, ChunkedEncodingError, ContentDecodingError, \
    InvalidSchema, InvalidURL, Timeout, RequestException
from pydio.job.job_config import JobConfig, JobsLoader
from pydio.job.EventLogger import EventLogger
from pydio.job.localdb import LocalDbHandler
from pydio.job.scheduler import PydioScheduler
import json
import requests
import keyring
import xmltodict
import types
import logging
import sys
import os
from pathlib import *
from pydio.utils.global_config import ConfigManager
from pydio.utils.functions import connection_helper
from pydio.utils import i18n
_ = i18n.language.ugettext

from functools import wraps
import authdigest
import flask
from pydio.utils.pydio_profiler import pydio_profile

try:
    #raise ImportError
    from pydio.endpoint.resolver import EndpointResolver, RESOLVER_CONFIG, EndpointException
except ImportError:
    EndpointResolver = False
    RESOLVER_CONFIG = False
    EndpointException = False

class FlaskRealmDigestDB(authdigest.RealmDigestDB):
    def requires_auth(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            request = flask.request
            if not self.isAuthenticated(request):
                return self.challenge()

            return f(*args, **kwargs)

        return decorated

authDB = FlaskRealmDigestDB('PydioSyncAuthRealm')

class PydioApi(Api):

    def __init__(self, server_port, user, password, external_ip=None):
        logging.info('-----------------------------------------------')
        if external_ip:
            logging.info('Starting agent on http://' + external_ip + ':' + str(server_port) + '/')
            logging.info('Warning, this agent UI is world accessible!')
        else:
            logging.info('Starting agent locally on http://localhost:' + str(server_port) + '/')
        logging.info('------------------------------------------------')

        self.user_data_path = JobsLoader.Instance().data_path
        self.port = server_port
        self.external_ip = external_ip
        authDB.add_user(user, password)
        self.running = False
        if getattr(sys, 'frozen', False):
            self.real_static_folder = Path(sys._MEIPASS) / 'ui' / 'res'
            static_folder = str(self.real_static_folder)
        else:
            self.real_static_folder = Path(__file__).parent / 'res'
            static_folder = 'res'

        logging.debug('Starting Flask server with following static folder : '+ static_folder)
        self.app = Flask(__name__, static_folder=static_folder, static_url_path='/res')
        self.app.logger.setLevel(logging.ERROR)
        l = logging.getLogger("werkzeug")
        if l:
            l.setLevel(logging.ERROR)
        super(PydioApi, self).__init__(self.app)
        self.add_resource(JobManager, '/', '/jobs', '/jobs/<string:job_id>', '/jobs-status')
        self.add_resource(WorkspacesManager, '/ws/<string:job_id>')
        self.add_resource(FoldersManager, '/folders/<string:job_id>')
        self.add_resource(LogManager, '/jobs/<string:job_id>/logs')
        self.add_resource(ConflictsManager, '/jobs/<string:job_id>/conflicts', '/jobs/conflicts')
        self.add_resource(CmdManager, '/cmd/<string:cmd>/<string:job_id>', '/cmd/<string:cmd>')
        self.add_resource(UrlManager, '/url/<path:complete_url>')
        self.add_resource(TaskInfoManager, '/stat', '/stat/<string:job_id>', '/stat/<string:job_id>/<path:relative_path>')
        self.add_resource(ShareManager, '/share/<string:job_id>')
        self.add_resource(ShareLinkManager, '/share_link/<string:job_id>/<string:folder_flag>/<path:relative_path>')
        self.app.add_url_rule('/res/i18n.js', 'i18n', self.serve_i18n_file)
        self.app.add_url_rule('/res/config.js', 'config', self.server_js_config)
        self.app.add_url_rule('/res/dynamic.css', 'dynamic_css', self.serve_dynamic_css)
        self.app.add_url_rule('/res/about.html', 'dynamic_about', self.serve_about_content)

        if EndpointResolver:
            self.add_resource(ProxyManager, '/proxy')
            self.add_resource(ResolverManager, '/resolve/<string:client_id>')
            self.app.add_url_rule('/res/dynamic.png', 'dynamic_png', self.serve_dynamic_image)
        else:
            self.app.add_url_rule('/res/settings.html', 'dynamic_settings', self.serve_settings)


    @pydio_profile
    def serve_i18n_file(self):
        s = ''
        from pydio.utils.i18n import get_languages
        import json
        languages = get_languages()
        short_lang = []
        for l in languages:
            lang_part = l.split('_')[0]
            if lang_part:
                short_lang.append(lang_part)

        with open(str(self.real_static_folder / 'i18n.js')) as js:
            for line in js:
                s += line

        if EndpointResolver:
            additional_strings = EndpointResolver.Instance().load_additional_strings()
            if additional_strings:
                s += '\nvar PydioAdditionalStrings = ' + json.dumps(additional_strings) + ';'
                s += '\nwindow.PydioLangs = merge(PydioAdditionalStrings, PydioLangs);'

        s += '\n'
        s += 'window.PydioEnvLanguages = ' + json.dumps(short_lang) + ';'
        return Response(response=s,
                        status=200,
                        mimetype="text/javascript")

    def server_js_config(self):
        content = "window.ui_config = {'login_mode':'standard', 'proxy_enabled':'false'}"
        if EndpointResolver:
            content = EndpointResolver.Instance().get_ui_config()
        return Response(response=content,
                        status=200,
                        mimetype="text/javascript")

    def serve_dynamic_css(self):
        content = ''
        if EndpointResolver:
            content = EndpointResolver.Instance().load_css()
        return Response(response=content,
                        status=200,
                        mimetype="text/css")

    def serve_dynamic_image(self):
        # This is called only if there is a resolved.
        return Response(response=EndpointResolver.Instance().load_image_content(),
                        status=200,
                        mimetype="image/png")

    def serve_about_content(self):
        content = ''
        if EndpointResolver:
            content = EndpointResolver.Instance().load_about_content()
        else:
            about_file = str(self.real_static_folder / 'about.html')
            with open(about_file, 'r') as handle:
                content = handle.read()
        return Response(response=content,
                        status=200,
                        mimetype="text/html")

    def serve_settings(self):
        content = '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta http-equiv="refresh" content="0; ' \
                  'url=#" /></head><body></body></html>'
        if EndpointResolver:
            with open(self.real_static_folder + '/settings.html', 'r') as handle:

                content = handle.read()
        return Response(response=content,
                        status=200,
                        mimetype="text/html")

    @pydio_profile
    def start_server(self):
        try:
            self.running = True
            self.app.run(port=self.port, host=self.external_ip)
        except Exception:
            self.running = False
            logging.exception("Error while starting web server")

    @pydio_profile
    def shutdown_server(self):
        logging.debug("Shutdown api server: %s" % self.app)
        with self.app.test_request_context():
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                raise RuntimeError('Not running with the Werkzeug Server')
            func()

class WorkspacesManager(Resource):

    @authDB.requires_auth
    @pydio_profile
    def get(self, job_id):
        if job_id != 'request':
            jobs = JobsLoader.Instance().get_jobs()
            if not job_id in jobs:
                return {"error": "Cannot find job"}
            job = jobs[job_id]

            url = job.server + '/api/pydio/state/user/repositories?format=json'
            auth = (job.user_id, keyring.get_password(job.server, job.user_id))
            verify = not job.trust_ssl
        else:
            args = request.args
            base = args['url'].rstrip('/')
            verify = False if args['trust_ssl'] == 'true' else True
            url = base + '/api/pydio/state/user/repositories?format=json'
            if 'password' in args:
                auth = (args['user'], args['password'])
            else:
                auth = (args['user'], keyring.get_password(base, args['user']))
            app_name_url = base + '/api/pydio/state/plugins?format=json'
            display_name_url = base + '/api/pydio/state/user/preferences?format=json'

        if verify and "REQUESTS_CA_BUNDLE" in os.environ:
            verify = os.environ["REQUESTS_CA_BUNDLE"]
        try:
            # TRY TO GET APPLICATION TITLE
            if app_name_url:
                resp = requests.get(app_name_url, stream=False, auth=auth, verify=verify,
                                    proxies=ConfigManager.Instance().get_defined_proxies())
                resp.raise_for_status()
                try:
                    app_data = json.loads(resp.content)
                    app_name = ''
                    ajxpcores = app_data['plugins']['ajxpcore']
                    for core in ajxpcores:
                        if core['@id'] == 'core.ajaxplorer':
                            for prop in core['plugin_configs']['property']:
                                if prop['@name'] == 'APPLICATION_TITLE':
                                    app_name = json.loads(prop['$'])
                                    break
                            break
                except KeyError as k:
                    pass
                except ValueError:
                    pass
            # TRY TO GET USER DISPLAY NAME
            if display_name_url:
                resp = requests.get(display_name_url, stream=False, auth=auth, verify=verify,
                                    proxies=ConfigManager.Instance().get_defined_proxies())
                resp.raise_for_status()
                try:
                    user_data = json.loads(resp.content)
                    user_display_name = ''
                    prefs = user_data['preferences']['pref']
                    for pref in prefs:
                        if pref['@name'] == 'USER_DISPLAY_NAME':
                            if pref['@value']:
                                user_display_name = pref['@value']
                            break
                except KeyError as k:
                    pass
                except ValueError:
                    pass


            resp = requests.get(url, stream=True, auth=auth, verify=verify,
                                proxies=ConfigManager.Instance().get_defined_proxies())
            resp.raise_for_status()
            data = json.loads(resp.content)
            if 'repositories' in data and 'repo' in data['repositories']:
                if isinstance(data['repositories']['repo'], types.DictType):
                    data['repositories']['repo'] = [data['repositories']['repo']]
                data['repositories']['repo'] = filter(lambda x: not x['@access_type'].startswith('ajxp_'), data['repositories']['repo'])
            if app_name:
                data['application_title'] = app_name
            if user_display_name:
                data['user_display_name'] = user_display_name
            return data
        except requests.HTTPError:
            r = resp.status_code
            message = _("Couldn't load your workspaces, check your server !")
            if r == 404:
                message = _("Server not found (404), is it up and has it Pydio installed ?")
            elif r == 401:
                message = _("Authentication failed: please verify your login and password")
            elif r == 403:
                message = _("Access to the server is forbidden")
            elif r == 500 or r == 408:
                message = _("Server seems to be encountering problems (500)")
            logging.debug("Error while loading workspaces : " + message)
            return {'error': message}, resp.status_code
        except SSLError as rt:
            logging.error(rt.message)
            return {'error': _("An SSL error happened! Is your server using a self-signed certificate? In that case please check 'Trust SSL certificate'")}, 400
        except ProxyError as rt:
            logging.error(rt.message)
            return {'error': _('A proxy error happened, please check the logs')}, 400
        except TooManyRedirects as rt:
            logging.error(rt.message)
            return {'error': _('Connection error: too many redirects')}, 400
        except ChunkedEncodingError as rt:
            logging.error(rt.message)
            return {'error': _('Chunked encoding error, please check the logs')}, 400
        except ContentDecodingError as rt:
            logging.error(rt.message)
            return {'error': _('Content Decoding error, please check the logs')}, 400
        except InvalidSchema as rt:
            logging.error(rt.message)
            return {'error': _('Http connection error: invalid schema.')}, 400
        except InvalidURL as rt:
            logging.error(rt.message)
            return {'error': _('Http connection error: invalid URL.')}, 400
        except ValueError:
            message = "Error while parsing request result:" + resp.content
            logging.debug(message)
            return {'error': message}, 400
        except Timeout as to:
            logging.error(to)
            return {'error': _('Connection timeout!')}, 400
        except RequestException as ree:
            logging.error(ree.message)
            return {'error': _('Cannot resolve domain!')}, 400


class FoldersManager(Resource):

    @authDB.requires_auth
    @pydio_profile
    def get(self, job_id):
        if job_id != 'request':
            jobs = JobsLoader.Instance().get_jobs()
            if not job_id in jobs:
                return {"error":"Cannot find job"}
            job = jobs[job_id]
            url = job.server + '/api/'+job.workspace+'/ls/?options=d&recursive=true'
            auth = (job.user_id, keyring.get_password(job.server, job.user_id))
            verify = not job.trust_ssl
        else:
            args = request.args
            base = args['url'].rstrip('/')
            verify = False if args['trust_ssl'] == 'true' else True
            url = base + '/api/'+args['ws']+'/ls/?options=d&recursive=true&max_depth=2'
            if 'password' in args:
                auth = (args['user'], args['password'])
            else:
                auth = (args['user'], keyring.get_password(base, args['user']))

        if verify and "REQUESTS_CA_BUNDLE" in os.environ:
            verify = os.environ["REQUESTS_CA_BUNDLE"]
        resp = requests.get( url, stream=True, auth=auth, verify=verify,
                             proxies=ConfigManager.Instance().get_defined_proxies())
        o = xmltodict.parse(resp.content)
        if not 'tree' in o or not o['tree'] or 'message' in o['tree']:
            return [{'error':'Cannot load workspace'}]
        if not 'tree' in o['tree']:
            return []
        if isinstance(o['tree']['tree'], types.DictType):
            return [o['tree']['tree']]
        return o['tree']['tree']


class JobManager(Resource):

    loader = None

    @authDB.requires_auth
    @pydio_profile
    def post(self):
        JobsLoader.Instance().get_jobs()
        json_req = request.get_json()
        new_job = JobConfig.object_decoder(json_req)
        if 'test_path' in json_req:
            json_req['directory'] = os.path.join(ConfigManager.Instance().get_data_path(), json_req['repoObject']['label'])
            return json_req
        elif 'compute_sizes' in json_req:
            dl_rate = 2 * 1024 * 1024
            up_rate = 0.1 * 1024 * 1024
            # COMPUTE REMOTE SIZE
            from pydio.sdk.remote import PydioSdk
            trust_ssl = False
            if 'trust_ssl' in json_req:
                trust_ssl = json_req['trust_ssl']
            try:
                _timeout = int(json_req["timeout"])
            except ValueError:
                _timeout = 20 # default to 20
            sdk = PydioSdk(json_req['server'], json_req['workspace'], json_req['remote_folder'], '',
                           auth=(json_req['user'], json_req['password']),
                           device_id=ConfigManager.Instance().get_device_id(),
                           skip_ssl_verify=trust_ssl,
                           proxies=ConfigManager.Instance().get_defined_proxies(),
                           timeout=_timeout)
            up = [0.0]
            def callback(location, change, info):
                if change and "bytesize" in change and change["md5"] != "directory":
                    up[0] += float(change["bytesize"])
            sdk.changes_stream(0, callback)
            # COMPUTE LOCAL SIZE
            down = 0.0
            if os.path.exists(json_req['directory']):
                for dirpath, dirnames, filenames in os.walk(json_req['directory']):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            down += os.path.getsize(fp)
                        except OSError:
                            pass

            json_req['byte_size'] = up[0] + down
            json_req['eta'] = up[0] * 8 / dl_rate + down * 8 / up_rate
            return json_req

        JobsLoader.Instance().update_job(new_job)
        scheduler = PydioScheduler.Instance()
        scheduler.reload_configs()
        scheduler.disable_job(new_job.id)
        if not 'toggle_status' in json_req:
            JobsLoader.Instance().clear_job_data(new_job.id)
        scheduler.enable_job(new_job.id)
        return JobConfig.encoder(new_job)

    @authDB.requires_auth
    @pydio_profile
    def get(self, job_id = None):
        if request.path == '/':
            return redirect("/res/index.html", code=302)
        jobs = JobsLoader.Instance().get_jobs()
        if not job_id:
            json_jobs = []
            for k in jobs:
                data = JobConfig.encoder(jobs[k])
                self.enrich_job(data, k, (request.path == '/jobs-status'))
                json_jobs.append(data)
            if request.path == '/jobs-status':
                response = {'is_connected_to_internet': connection_helper.internet_ok, 'jobs': json_jobs}
                return response
            return json_jobs
        logging.info("Requiring job %s" % job_id)
        data = JobConfig.encoder(jobs[job_id])
        self.enrich_job(data, job_id)
        return data

    @pydio_profile
    def enrich_job(self, job_data, job_id, get_notification=False):
        running = PydioScheduler.Instance().is_job_running(job_id)
        job_data['running'] = running
        logger = EventLogger(JobsLoader.Instance().build_job_data_path(job_id))
        if get_notification:
            notification = logger.consume_notification()
            if notification:
                job_data['notification'] = notification
        last_events = logger.get_all(1, 0)
        if len(last_events):
            job_data['last_event'] = last_events.pop()
        if running:
            job_data['state'] = PydioScheduler.Instance().get_job_progress(job_id)
        try:
            job_data['last_action'] = EventLogger(JobsLoader.Instance().build_job_data_path(job_id)).get_last_action()[-1][-1]
        except IndexError:
            pass


    @authDB.requires_auth
    @pydio_profile
    def delete(self, job_id):
        JobsLoader.Instance().delete_job(job_id)
        scheduler = PydioScheduler.Instance()
        scheduler.reload_configs()
        scheduler.disable_job(job_id)
        JobsLoader.Instance().clear_job_data(job_id, parent=True)
        return job_id + "deleted", 204


class ConflictsManager(Resource):

    @authDB.requires_auth
    @pydio_profile
    def post(self):
        json_conflict = request.get_json()
        job_id = json_conflict['job_id']
        try:
            job_config = JobsLoader.Instance().get_job(job_id)
        except Exception:
            return "Can't find any job config with this ID.", 404

        dbHandler = LocalDbHandler(JobsLoader.Instance().build_job_data_path(job_id))
        dbHandler.update_node_status(json_conflict['node_path'], json_conflict['status'])
        if not dbHandler.count_conflicts() and job_config.active:
            t = PydioScheduler.Instance().get_thread(job_id)
            if t:
                t.start_now()
        return json_conflict

    @authDB.requires_auth
    @pydio_profile
    def get(self, job_id):
        if not job_id in JobsLoader.Instance().get_jobs():
            return "Can't find any job config with this ID.", 404

        dbHandler = LocalDbHandler(JobsLoader.Instance().build_job_data_path(job_id))
        return dbHandler.list_conflict_nodes()


class LogManager(Resource):

    def __init__(self):
        self.events = {}

    @authDB.requires_auth
    @pydio_profile
    def get(self, job_id):
        if not job_id in JobsLoader.Instance().get_jobs():
            return "Can't find any job config with this ID.", 404

        logger = EventLogger(JobsLoader.Instance().build_job_data_path(job_id))
        if not request.args:
            logs = logger.get_all(20,0)
        else:
            filter = request.args.keys()[0]
            filter_parameter = request.args.get(filter)
            logs = logger.filter(filter, filter_parameter)

        tasks = PydioScheduler.Instance().get_job_progress(job_id)
        return {"logs":logs, "running":tasks}


class CmdManager(Resource):

    @authDB.requires_auth
    @pydio_profile
    def get(self, cmd, job_id=None):
        if job_id:
            if cmd == 'enable' or cmd == 'disable':
                job_config = JobsLoader.Instance().get_job(job_id)
                job_config.active = True if cmd == 'enable' else False
                JobsLoader.Instance().update_job(job_config)
                PydioScheduler.Instance().reload_configs()
            PydioScheduler.Instance().handle_job_signal(self, cmd, job_id)
        else:
            return PydioScheduler.Instance().handle_generic_signal(self, cmd)
        return ('success',)


class ResolverManager(Resource):

    @authDB.requires_auth
    @pydio_profile
    def get(self, client_id):
        try:
            return EndpointResolver.Instance().get_customer_endpoints(client_id)
        except EndpointException as e:
            return {'message': e.message, 'code': e.error_id}, 500


class ProxyManager(Resource):

    @authDB.requires_auth
    @pydio_profile
    def get(self):
        # read contents from proxy.json
        res, response = {}, {}
        try:
            f = open(os.path.join(ConfigManager.Instance().get_configs_path(), 'proxies.json'))
            res = json.load(f)
            f.close()
        except IOError: # no proxy file exists
            res = json.loads('{"http": {"username": "", "password": "","hostname": "","port": "","active":"false"},"https": {"username": "", "password": "", "hostname": "","port": "","active":"false"}}')
        # parse the content and only return some fields
        for protocol in res.keys():
            response[protocol] = {}
            for field in res[protocol]:
                if field != u"password":
                    response[protocol][field] = res[protocol][field]
        return response

    @authDB.requires_auth
    @pydio_profile
    def post(self):
        json_req = request.get_json()
        logging.info("Writing into proxies.json file")
        try:
            for protocol in json_req.keys():
                if "password" in json_req[protocol]:
                    if json_req[protocol]['password'] != "":
                        keyring.set_password(json_req[protocol]["hostname"], json_req[protocol]["username"], json_req[protocol]["password"])
                        json_req[protocol]["password"] = "__pydio_proxy_pwd__"
        except keyring.errors.PasswordSetError as e:
            logging.error("Error while storing password in keychain, should we store it cyphered in the config?")
        except Exception as e:
            logging.error("Error while storing password in keychain, error message:" + e.message)

        ConfigManager.Instance().proxies_loaded = False
        # write the content into local proxy.json file
        ConfigManager.Instance().set_user_proxy(json_req)
        return self.get()


class TaskInfoManager(Resource):

    @authDB.requires_auth
    @pydio_profile
    def get(self, job_id='', relative_path=''):
        """
        retrieves the stat info for a given file / list the active job details
        :param job_id: (optional) Job Id of the file/ folder
        :param relative_path: (optional) relative path of the file/folder with respect
               to the corresponding repository(job_id)
        :returns a json response
        """
        if request.path == '/stat':
            jobs = JobsLoader.Instance().get_jobs()
            json_jobs = {}
            for job in jobs:
                json_jobs.update({jobs[job].id: [jobs[job].directory, jobs[job].server, jobs[job].label, jobs[job].workspace]})
            return json_jobs
        else:

            directory_path = JobsLoader.Instance().get_job(job_id).directory
            base_path = JobsLoader.Instance().build_job_data_path(job_id)
            path = os.path.join(directory_path, relative_path)

            #r = os.stat(path)

            # Get the status of the file idle/busy... by join of ajxp_index and ajxp_node_status tables
            db_handler = LocalDbHandler(base_path, directory_path)
            if Path(str(path.encode("utf-8"))).is_dir():
                node_status = db_handler.get_directory_node_status("/" + relative_path)
            else:
                node_status = db_handler.get_node_status("/" + relative_path)

            return {"node_status": node_status}

class UrlManager(Resource):
    """
        performs a url request via proxy if present
        :returns a json response
    """
    @authDB.requires_auth
    @pydio_profile
    def get(self, complete_url):
        resp = requests.get(complete_url, stream=False, proxies=ConfigManager.Instance().get_defined_proxies())
        return json.loads(resp.content)

class ShareManager(Resource):
    """
        provides share/un-share functionality for the desired item.
        :returns a json response
    """
    @authDB.requires_auth
    @pydio_profile
    def get(self, job_id):
            """
            retrieves the stat info for a given file / list the active job details
            :param job_id: (optional) Job Id of the file/ folder that needs to be shared
            :returns a json response
                        on success: returns a shared link
            """
            args = request.args
            jobs = JobsLoader.Instance().get_jobs()
            if not job_id in jobs:
                return {"error": "Cannot find job"}
            job = jobs[job_id]

            from pydio.sdk.remote import PydioSdk
            remote_instance = PydioSdk(job.server, job.workspace, job.remote_folder, job.user_id,
                           auth="",
                           device_id=ConfigManager.Instance().get_device_id(),
                           skip_ssl_verify=job.trust_ssl,
                           proxies=ConfigManager.Instance().get_defined_proxies(),
                           timeout=job.timeout)

            if args['action'] == 'share':
                relative_path = os.path.normpath("/" + args["relative_path"]).replace('\\', '/')
                # Check if the shared link is already present
                check_res = remote_instance.check_share_link(
                    relative_path
                )

                if len(check_res) > 2:  # when share link doesn't exists content length will be zero for file and 2 for folder
                    res = json.loads(check_res)
                    if "minisite" in res and res["minisite"]["public"]:
                        return {"link": res["minisite"]["public_link"], "existingLinkFlag": "true"}
                    elif "repositoryId" in res:
                        return {"link": _("The folder is already shared as a workspace!"), "existingLinkFlag": "true"}

                elif args["checkExistingLinkFlag"]:
                    return {"existingLinkFlag": "false"}

                res = remote_instance.share(
                    args["ws_label"],
                    args["ws_description"] if "ws_description" in args else "",
                    args["password"] if "password" in args else "",
                    args["expiration"] if "expiration" in args else 0,
                    args["downloads"] if "downloads" in args else 0,
                    args["can_read"] if "can_read" in args else "true",
                    args["can_download"] if "can_download" in args else "true",
                    relative_path,
                    args["link_handler"] if "link_handler" in args else "",
                    args["can_write"] if "can_write" in args else "false"
                )
                return {"link": res}
            else:
                res = remote_instance.unshare("/" + args["path"])
                return {"response": res, "existingLinkFlag": "false"}

class ShareLinkManager(Resource):
    """
        Gets the share content from the explorer and passes it to JS.
        :returns a json response
    """
    @authDB.requires_auth
    @pydio_profile
    def get(self, job_id, folder_flag, relative_path):
        """
        writes the necessary information required for share feature to LocalSocket/NamedPipe
        """
        #logging.info("[SHARE] " + job_id + " " + folder_flag + " " + relative_path)
        try:
            import platform
            is_system_windows = platform.system().lower().startswith("win")
            if is_system_windows:
                name_pipe_path = "//./pipe/pydioLocalServer"
            else:
                name_pipe_path = "/tmp/pydioLocalServer"
            data = {"RelativePath": relative_path, "JobId": job_id, "FolderFlag": folder_flag}
            txt = json.dumps(data)
            try:
                f = open(name_pipe_path, "w")
                f.write(txt)
                f.close()
            except IOError:
                from socket import *
                try:
                    s = socket(AF_UNIX, SOCK_STREAM)
                    s.connect(name_pipe_path)
                    s.send(txt)
                    s.close()
                except Exception as e:
                    raise e
            return {"status": "Write to the Name pipe is successful!"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
