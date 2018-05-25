from datetime import datetime
from typing import List, Dict

import cherrypy
from tor_core.initialize import configure_redis
from users import User


class Tools(object):
    def __init__(self):
        self.r = configure_redis()

    def error_message(self, result_code: int, missing_fields: List[str]) -> Dict:
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

    def get_request_json(self, request):
        return request.json

    def validate_json(self, request):
        """
        Everything here should require both an API key and a post_id. Verify
        that those exist in the passed-in data.

        :param data: Dict; the passed-in json
        :return: True if the requested keys are there, false if not.
        """
        # Did we even get json in the request?
        if not hasattr(request, 'json'):
            return False

        data = self.get_request_json(request)

        api_key = data.get('api_key')
        post_id = data.get('post_id')

        if api_key is None or post_id is None:
            return False
        return True


    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def claim(self):
        if not self.validate_json(cherrypy.request):
            return self.error_state

        data = self.get_request_json(cherrypy.request)

        # DO STUFF
        return data

    @cherrypy.expose()
    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def done(self):
        if not self.validate_json(cherrypy.request):
            return self.error_state
        data = self.get_request_json(cherrypy.request)

        return data


class Keys(Tools):

    def create(self):
        pass

    def me(self):
        pass

    def destroy(self):
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