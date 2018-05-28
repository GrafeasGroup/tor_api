import logging
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Dict
from typing import List

import cherrypy
from tor_core.initialize import configure_logging
from tor_core.initialize import configure_redis

from users import User


# conf = {
#     '/': {
#         'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
#         'tools.response_headers.on': True,
#         'tools.response_headers.headers': [
#             ('Content-Type', 'application/json')
#         ],
#     },
# }


# noinspection SqlNoDataSourceInspection
class DatabaseHandler(object):
    def __init__(self):
        self.db_name = './log.sqlite'

        if not os.path.exists(self.db_name):
            self.conn = sqlite3.connect(self.db_name)
            c = self.conn.cursor()
            # make the users table; we want to know which API key corresponds
            # with which person and when that API key was granted.
            c.execute(
                """
                CREATE TABLE users (
                  api_key TEXT PRIMARY KEY,
                  name TEXT,
                  is_admin BOOLEAN,
                  date_granted TIMESTAMP,
                  authed_by TEXT
                )
                """
            )
            c.execute(
                """
                CREATE TABLE log (
                  api_key TEXT,
                  endpoint TEXT,
                  date TIMESTAMP,
                  request_data TEXT,
                  FOREIGN KEY(api_key) REFERENCES users(api_key)
                )
                """
            )
            self.conn.commit()
            self.conn.close()

    def _create_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_name)

    def _close_conn(self, conn: sqlite3.Connection) -> None:
        conn.close()

    def write_log_entry(self, data: Dict) -> None:
        conn = self._create_conn()
        c = conn.cursor()
        c.execute(
            'INSERT INTO log VALUES (?,?,?,?)',
            (
                data.get('api_key'),
                data.get('endpoint'),
                str(datetime.now()),
                data.get('request_data')
            )
        )
        conn.commit()
        self._close_conn(conn)

    def write_user_entry(self, data: Dict) -> None:
        conn = self._create_conn()
        c = conn.cursor()
        c.execute(
            'INSERT INTO users VALUES (?,?,?,?,?)',
            (
                data.get('api_key'),
                data.get('name'),
                1 if data.get('is_admin') is True else 0,
                str(datetime.now()),
                data.get('admin_api_key')
            )
        )
        conn.commit()
        self._close_conn(conn)

    def log(self, request: cherrypy.request, data: Dict) -> Dict:
        # TODO: stuff
        pass

    def get_self(self, api_key: str) -> [dict, None]:

        def format_self(doohickey: tuple) -> Dict:
            return {
                'api_key': doohickey[0],
                'username': doohickey[1],
                'is_admin': True if doohickey[2] == 1 else False,
                'date_granted': doohickey[3],
                'authorized_by': doohickey[4]
            }

        conn = self._create_conn()
        c = conn.cursor()

        result = c.execute(
            'SELECT * FROM users WHERE api_key = ?', (api_key,)
        )
        me = result.fetchone()
        if isinstance(me, tuple):
            return format_self(me)
        # but seriously we should never hit this
        logging.error(
            'Received /me call for invalid api key {}'.format(api_key)
        )
        self._close_conn(conn)
        return None

    def is_admin(self, api_key: str) -> bool:
        conn = self._create_conn()
        c = conn.cursor()
        result = c.execute(
            """SELECT is_admin FROM users WHERE api_key IS ?""", (api_key,)
        )
        # SQL stores True / False as 1 and 0. Grab the first entry we receive,
        # then return true if it's a 1 or false if it's a 0.
        result = result.fetchone()[0] == 1
        self._close_conn(conn)
        return result


class Tools(object):
    def __init__(self):
        self.r = configure_redis()
        self.db = DatabaseHandler()

    def get_request_json(self, request: cherrypy.request) -> [Dict, None]:
        """
        Pull the json out of the cherrypy request object and return it.

        :param request: the cherrypy request object
        :return: If there is json here, we return it. If not, it returns None.
        """
        if self.has_json(request):
            return request.json
        else:
            return None

    def has_json(self, request: cherrypy.request) -> bool:
        """
        Let's make sure that we actually have JSON with this request.

        :param request: the cherrypy request object
        :return: true if json is attached, false if not.
        """
        return hasattr(request, 'json')

    def validate_json(
            self, request: cherrypy.request,
            fields: List[str]
    ) -> bool:
        """
        Everything here should require both an API key and a post_id. Verify
        that those exist in the passed-in data.

        :param request: The cherrypy request object
        :param fields: the list of field names that we need for this request
        :return: True if the requested keys are there, false if not.
        """
        # Did we even get json in the request?
        if not self.has_json(request):
            return False

        data = self.get_request_json(request)

        for field in fields:
            # is everything here that we asked for?
            if field not in data:
                return False

        return True

    def get_missing_fields(
            self,
            fields: List[str],
            request: cherrypy.request,
    ) -> List[str]:
        """
        Take in a list of fields required to complete the request and send
        back a list of the fields that weren't included so we can yell at the
        client.

        :param fields: The list of field names to look for
        :param request: the cherrypy request object
        :return: A list of field names that are not present in the request
        """
        if not self.has_json(request):
            return fields

        data = self.get_request_json(request)

        missing_fields = list()
        for field in fields:
            attempt = data.get(field, None)
            if not attempt:
                missing_fields.append(field)
        return missing_fields

    def missing_fields_response(self, required_fields, request):
        ms = self.get_missing_fields(required_fields, request)
        return self.response_message_error_fields(400, ms)

    def response_message_base(
            self,
            result_code: int,
    ) -> Dict:
        return {
            'result': result_code,
            'server_time': str(datetime.utcnow().isoformat())
        }

    def response_message_error_fields(
        self,
        result_code: int,
        missing_fields: List[str],
    ) -> Dict:
        """
        Build out a JSON response dict for an error involving missing fields in
        the request.

        :param result_code: the particular error code to return
        :param missing_fields: what fields should be in the request that aren't?
        :return: the json dict, ready to pass back to the client.
        """
        m = self.response_message_base(result_code)
        m.update({
            'message': 'Please supply the following fields: ' + ', '.join(
                [f for f in missing_fields]
            ),
        })
        return m

    def response_message_general(
        self,
        result_code: int,
        message: str
    ) -> Dict:
        """
        A simple response object abstraction that creates an error response with
        a generic message.
        :param result_code: the particular error code to return
        :param message: the string message to be returned back to the client
        :return:
        """
        m = self.response_message_base(result_code)
        m.update({
            'message': message
        })
        return m

    def validate_request(self, request: cherrypy.request) -> bool:
        return self.db.is_admin(
            self.get_request_json(cherrypy.request).get('api_key')
        )


class Posts(Tools):
    # API endpoints for claiming / completing / etc.

    # def __init__(self):
    #     super().__init__()

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def claim(self):
        required_fields = ['api_key', 'post_id']
        if not self.validate_json(cherrypy.request, required_fields):
            return self.missing_fields_response(
                required_fields, cherrypy.request
            )

        data = self.get_request_json(cherrypy.request)

        # TODO: stuff

        return data

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def done(self):
        required_fields = ['api_key', 'post_id']
        if not self.validate_json(cherrypy.request, required_fields):
            return self.missing_fields_response(
                required_fields, cherrypy.request
            )

        data = self.get_request_json(cherrypy.request)

        # TODO: stuff

        return data

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def unclaim(self):
        required_fields = ['api_key', 'post_id']
        if not self.validate_json(cherrypy.request, required_fields):
            return self.missing_fields_response(
                required_fields, cherrypy.request
            )

        data = self.get_request_json(cherrypy.request)

        # TODO: stuff

        return data


class Keys(Tools):
    # Any time the api_key field is mentioned in this class, it's looking for
    # the admin API key, aka the "do stuff" key.
    @cherrypy.expose()
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def GET(self):
        return self.response_message_general(421, 'There\'s nothing here.')

    def POST(self):
        return self.response_message_general(421, 'There\'s nothing here.')

    def generate_api_key(self):
        return str(uuid.uuid4())

    @cherrypy.expose()
    @cherrypy.tools.allow(methods=['POST'])
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def create(self):
        required_fields = ['api_key', 'name', 'is_admin']
        if self.validate_request(cherrypy.request):
            if not self.validate_json(cherrypy.request, required_fields):
                return self.missing_fields_response(
                    required_fields, cherrypy.request
                )

            data = self.get_request_json(cherrypy.request)
            new_api_key = self.generate_api_key()
            self.db.write_user_entry({
                'api_key': new_api_key,
                'name': data.get('name'),
                'is_admin': data.get('is_admin', False),
                # this is confusing. The admin api_key here is what was
                # submitted to complete the original request. It's logged as
                # the person who originally signed off on this. Possibly should
                # rework.
                'admin_api_key': data.get('api_key')
            })

            resp = self.response_message_general(200, 'user created')
            resp.update({'new_user_data': {
                'new_api_key': new_api_key,
                'name': data.get('name'),
                'is_admin': data.get('is_admin')
            }})
            return resp
        else:
            return self.response_message_general(500, 'something went wrong')

    @cherrypy.expose()
    @cherrypy.tools.allow(methods=['POST'])
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def me(self):
        required_fields = ['api_key']
        if not self.validate_json(cherrypy.request, required_fields):
            return self.missing_fields_response(
                required_fields, cherrypy.request
            )

        result = self.db.get_self(cherrypy.request.json.get('api_key'))
        if result is None:
            return self.response_message_general(
                404,
                'I don\'t see that API key in use anywhere.'
            )
        else:
            resp = self.response_message_base(200)
            resp.update(result)
            return resp

    @cherrypy.expose()
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def revoke(self):
        # TODO: stuff
        pass


class Users(Tools):

    def _cp_dispatch(self, vpath):
        if len(vpath) == 1:
            return self.users(vpath.pop(0))  # this should be a username
        if len(vpath) == 0:
            return self.response_message_general(
                400,
                'Please supply a username in the following URL format: '
                '/user/spez'
            )
        return vpath

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def users(self, username):
        user = User(username, create_if_not_found=False)
        if user is None:
            return self.response_message_general(404, 'User not found!')
        return user


class API(Tools):

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def index(self):
        """
        The base endpoint will be used for general stats.

        TODO: Add API key support
        """
        transcription_count = int(self.r.get('total_completed'))
        total_volunteers = self.r.scard('accepted_CoC')
        current_percentage = (
            transcription_count / int(self.r.get('total_posted'))
        )
        return {
            'result': 200,  # yes, I'm hardcoding this one for now
            'transcription_count': transcription_count,
            'transcription_percentage': current_percentage,
            'volunteer_count': total_volunteers,
            'server_time': str(datetime.utcnow().isoformat())
        }


def set_extra_cherrypy_configs():
    # disable logging of requests -- mostly to pretty up the log and just
    # let us grab what we want
    # cherrypy.log.error_log.propagate = False
    # cherrypy.log.access_log.propagate = False
    # cherrypy.log.screen = None

    # global config update -- separate from the application-level conf dict
    cherrypy.config.update(
        {
            'server.socket_port': 80
        }
    )


if __name__ == '__main__':

    class DummyConfig(object):
        def __getattribute__(self, item):
            return False

    set_extra_cherrypy_configs()
    configure_logging(DummyConfig(), log_name='tor_api.log')

    # build the API tree
    api = API()
    api.claim = Posts().claim
    api.done = Posts().done
    api.unclaim = Posts().unclaim

    api.user = Users()

    api.keys = Keys()
    api.keys.me = Keys().me
    api.keys.create = Keys().create
    api.keys.revoke = Keys().revoke

    # start your engines
    cherrypy.tree.mount(api, '/')
    cherrypy.server.socket_host = "127.0.0.1"
    cherrypy.engine.start()
    logging.info('ToR API started!')
