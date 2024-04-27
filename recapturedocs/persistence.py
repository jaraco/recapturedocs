import cherrypy
from jaraco.mongodb import helper

from . import jsonpickle


def init_mongodb():
    ps = cherrypy._whole_config.get('persistence', dict())
    storage_uri = ps.get('storage.uri', 'mongodb://localhost')
    is_production = cherrypy.config.get('server.production', False)
    s_name = 'recapturedocs' if is_production else 'recapturedocs_devel'
    store = helper.connect_db(storage_uri, default_db_name=s_name)
    globals().update(store=store)


def init():
    init_mongodb()
    jsonpickle.setup_handlers()
