from datetime import datetime
from typing import List, Dict

import cherrypy
from tor_core.initialize import configure_redis
from tor_api.users import User


class Tools(object):
    def __init__(self):
        self.r = configure_redis()

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
            attempt = data.get(field, None)
            if not attempt:
                return False

        return True

    def error_message_fields(
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
        return {
            'result': result_code,
            'data': 'Please supply the following fields: ' + ', '.join(
                [f for f in missing_fields]
            ),
            'server_time': str(datetime.utcnow().isoformat())
        }


class Posts(Tools):
    # API endpoints for claiming / completing / etc.

    # def __init__(self):
    #     super().__init__()

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

        missing_fields = List
        for field in fields:
            attempt = data.get(field, None)
            if not attempt:
                missing_fields.append(field)
        return missing_fields

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def claim(self):
        required_fields = ['api_key', 'post_id']
        if not self.validate_json(cherrypy.request, required_fields):
            ms = self.get_missing_fields(required_fields, cherrypy.request)
            return self.error_message_fields(400, ms)

        data = self.get_request_json(cherrypy.request)

        # DO STUFF
        return data

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def done(self):
        required_fields = ['api_key', 'post_id']
        if not self.validate_json(cherrypy.request, required_fields):
            ms = self.get_missing_fields(required_fields, cherrypy.request)
            return self.error_message_fields(400, ms)

        data = self.get_request_json(cherrypy.request)

        return data


class Keys(Tools):

    def create(self):
        pass

    def me(self):
        pass

    def revoke(self):
        pass


class Users(Tools):

    def _cp_dispatch(self, vpath):
        if len(vpath) == 1:
            return self.users(vpath.pop(0))  # this should be a username

        return vpath

    error_state = {
        'result': 400,
        'data': 'Please supply a username in the following URL format: '
                '/user/spez'
    }

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def users(self, username):
        user = User(username, create_if_not_found=False)
        if user is None:
            return
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


if __name__ == '__main__':
    # build the API tree
    api = API()
    api.claim = Posts().claim
    api.done = Posts().done
    api.user = Users()

    # start your engines
    cherrypy.quickstart(api, '/')
