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
                  ip_address TEXT,
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
            'INSERT INTO log VALUES (?,?,?,?,?)',
            (
                data.get('api_key'),
                data.get('ip_address'),
                data.get('endpoint'),
                datetime.now().isoformat(),
                str(data.get('request_data'))
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
                datetime.now().isoformat(),
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
        raw_data = result.fetchone()
        if raw_data is not None:
            ret = raw_data[0] == 1
        else:
            ret = False
        self._close_conn(conn)
        return ret

    def validate_key(self, api_key: str) -> bool:
        conn = self._create_conn()
        c = conn.cursor()
        result = c.execute(
            """SELECT api_key from users where api_key is ?""", (api_key,)
        )
        raw_data = result.fetchone()
        if raw_data is None:
            return False
        return True

    def revoke_key(self, api_key: str) -> None:
        conn = self._create_conn()
        c = conn.cursor()
        c.execute(
            """DELETE FROM users WHERE api_key is ?""", (api_key,)
        )
        conn.commit()


class Tools(object):
    def __init__(self):
        self.r = configure_redis()
        self.db = DatabaseHandler()

    def log(self, api_key: str, endpoint:str, request_data: dict) -> None:
        """
        Package it all up into a nice little dict and send it off to the
        database.

        :param api_key: the key that is currently being used to access the
            resource.
        :param endpoint: a string that tells us what they're accessing. For
            example, /keys/me or /claim.
        :param request_data: the dict of all the data that was included in the
            original request.
        :return: None.
        """
        data = {
            'api_key': api_key,
            'ip_address': cherrypy.request.remote.ip,
            'endpoint': endpoint,
            'request_data': request_data,
        }
        self.db.write_log_entry(data)

    def get_request_json(self, request: cherrypy.request) -> [Dict, None]:
        """
        Pull the json out of the cherrypy request object and return it.

        :param request: the cherrypy request object.
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


@cherrypy.tools.register('before_handler')
def require_admin() -> None:
    """
    Decorator for endpoints that require an API key with admin permissions.

    :return: None -- it explodes if a non-admin api key (or none) is given.
    """
    t = Tools()
    if t.has_json(cherrypy.request):
        data = t.get_request_json(cherrypy.request)
        if t.db.is_admin(data.get('api_key')):
            return
        else:
            raise cherrypy.HTTPError(
                401, message='This resource requires admin access.'
            )
    else:
        raise cherrypy.HTTPError(
            400, 'Missing JSON in request.'
        )

@cherrypy.tools.register('before_handler')
def require_api_key() -> None:
    """
    Decorator for endpoints that require a valid API key.

    :return: None -- it explodes if no api key is given.
    """
    t = Tools()
    if t.has_json(cherrypy.request):
        data = t.get_request_json(cherrypy.request)
        # does the key that they sent actually exist?
        if not t.db.validate_key(data.get('api_key')):
            raise cherrypy.HTTPError(
                403, 'Missing api_key in request JSON'
            )
    else:
        raise cherrypy.HTTPError(
            400, 'Missing api_key in request JSON'
        )


class Posts(Tools):
    """
    API endpoints for interacting with content. Claim, unclaim, and done.

    Because these endpoints are for pieces of the system that don't exist
    yet, all three include a debug parameter so that you can force a
    particular result based on what we think the result will be. The options
    are:

    /claim
    ---
    You send:       Receive (not exact verbiage):
    {'debug': 0}    Success! (200)
    {'debug': 1}    Error: has already been claimed (409)
    {'debug': 2}    Error: already been completed (409)
    {'debug': 3}    Error: need to complete Code of Conduct (no idea how this
        is going to work yet) (406)

    /done
    ---
    You send:       Receive (not exact verbiage):
    {'debug': 0}    Success! (200)
    {'debug': 1}    Error: cannot find transcription (409)

    /unclaim
    ---
    You send:       Receive (not exact verbiage):
    {'debug': 0}    Success! (200)
    {'debug': 1}    Error: cannot unclaim (this post does not belong to you) (409)
    """

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    @cherrypy.tools.require_api_key()
    def claim(self):
        required_fields = ['api_key', 'post_id']
        if not self.validate_json(cherrypy.request, required_fields):
            return self.missing_fields_response(
                required_fields, cherrypy.request
            )

        data = self.get_request_json(cherrypy.request)
        self.log(data.get('api_key'), '/claim', data)

        if (
                isinstance(data.get('debug'), int)
        ):
            d = data.get('debug')
            if d == 0:
                return self.response_message_general(
                    200,
                    'Claim successful on post ID {}'.format(
                        data.get('post_id')
                    )
                )
            if d == 1:
                return self.response_message_general(
                    409,
                    'Post has already been claimed.'
                )
            if d == 2:
                return self.response_message_general(
                    409,
                    'Post has already been completed.'
                )
            if d == 3:
                return self.response_message_general(
                    406,
                    'Cannot continue; user has not accepted Code of Conduct!'
                )
        else:
            return self.response_message_general(
                200,
                'This endpoint has been written, but not connected to '
                'anything. Pass \'debug\' in your JSON with values 0-3 to test '
                'varying responses.'
            )

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    @cherrypy.tools.require_api_key()
    def done(self):
        required_fields = ['api_key', 'post_id']
        if not self.validate_json(cherrypy.request, required_fields):
            return self.missing_fields_response(
                required_fields, cherrypy.request
            )

        data = self.get_request_json(cherrypy.request)
        self.log(data.get('api_key'), '/done', data)

        if (
                isinstance(data.get('debug'), int)
        ):
            d = data.get('debug')
            if d == 0:
                return self.response_message_general(
                    200,
                    'Successfully completed post ID {}'.format(
                        data.get('post_id')
                    )
                )
            if d == 1:
                return self.response_message_general(
                    409,
                    'Cannot find transcription for post ID {}'.format(
                        data.get('post_id')
                    )
                )
        else:
            return self.response_message_general(
                200,
                'This endpoint has been written, but not connected to '
                'anything. Pass \'debug\' in your JSON with values 0-1 to test '
                'varying responses.'
            )

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    @cherrypy.tools.require_api_key()
    def unclaim(self):
        # TODO: Add admin override
        required_fields = ['api_key', 'post_id']
        if not self.validate_json(cherrypy.request, required_fields):
            return self.missing_fields_response(
                required_fields, cherrypy.request
            )

        data = self.get_request_json(cherrypy.request)
        self.log(data.get('api_key'), '/unclaim', data)

        if (
                isinstance(data.get('debug'), int)
        ):
            d = data.get('debug')
            if d == 0:
                return self.response_message_general(
                    200,
                    'Unclaim successful on post ID {}'.format(
                        data.get('post_id')
                    )
                )
            if d == 1:
                return self.response_message_general(
                    409,
                    'Post does not belong to requester, cannot unclaim.'
                )
        else:
            return self.response_message_general(
                200,
                'This endpoint has been written, but not connected to '
                'anything. Pass \'debug\' in your JSON with values 0-1 to test '
                'varying responses.'
            )


class Keys(Tools):
    def generate_api_key(self):
        return str(uuid.uuid4())

    @cherrypy.expose()
    @cherrypy.tools.allow(methods=['POST'])
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @cherrypy.tools.require_admin()
    def create(self):
        required_fields = ['api_key', 'name', 'is_admin']
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

        resp = self.response_message_general(201, 'user created')
        resp.update({'user_data': {
            'new_api_key': new_api_key,
            'name': data.get('name'),
            'is_admin': data.get('is_admin')
        }})
        self.log(data.get('api_key'), '/keys/create', data)
        return resp

    @cherrypy.expose()
    @cherrypy.tools.allow(methods=['POST'])
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @cherrypy.tools.require_api_key()
    def me(self):
        required_fields = ['api_key']
        if not self.validate_json(cherrypy.request, required_fields):
            return self.missing_fields_response(
                required_fields, cherrypy.request
            )
        data = self.get_request_json(cherrypy.request)
        self.log(data.get('api_key'), '/keys/me', data)

        result = self.db.get_self(data.get('api_key'))
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
    @cherrypy.tools.require_admin()
    def revoke(self):
        required_fields = ['api_key', 'revoked_key']
        if not self.validate_json(cherrypy.request, required_fields):
            return self.missing_fields_response(
                required_fields, cherrypy.request
            )

        data = self.get_request_json(cherrypy.request)
        self.log(data.get('api_key'), '/', data)

        self.db.revoke_key(data.get('revoked_key'))

        return self.response_message_general(
            200,
            'API key {} removed from table `users`.'.format(
                data.get('revoked_key')
            )
        )


class Users(Tools):

    @cherrypy.expose()
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @cherrypy.tools.require_api_key()
    def index(self):
        data = self.get_request_json(cherrypy.request)
        self.log(data.get('api_key'), '/', data)

        username = self.get_request_json(cherrypy.request).get('username')
        user = User(username, self.r, create_if_not_found=False)
        if user is None:
            return self.response_message_general(404, 'User not found!')
        resp = self.response_message_base(200)
        resp.update({'user_data': user.to_dict()})
        return resp


class API(Tools):

    @cherrypy.expose()
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    @cherrypy.tools.require_api_key()
    def index(self):
        """
        The base endpoint will be used for general stats.
        """
        transcription_count = int(self.r.get('total_completed'))
        total_volunteers = self.r.scard('accepted_CoC')
        current_percentage = (
            transcription_count / int(self.r.get('total_posted'))
        )

        data = self.get_request_json(cherrypy.request)
        self.log(data.get('api_key'), '/', data)

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
            'server.socket_port': 8080
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

    api.user = Users().index

    api.keys = Keys()
    api.keys.me = Keys().me
    api.keys.create = Keys().create
    api.keys.revoke = Keys().revoke

    # start your engines
    cherrypy.tree.mount(api, '/')
    cherrypy.server.socket_host = "127.0.0.1"
    cherrypy.engine.start()
    logging.info('ToR API started!')
