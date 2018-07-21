from charlotte import Prototype


class User(Prototype):
    default = {
        'username': ''
    }
    schema = {
        'type': 'object',
        'properties': {
            'username': {
                'type': 'string'
            }
        }
    }