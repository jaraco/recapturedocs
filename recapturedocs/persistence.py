import cherrypy
from jaraco.mongodb import helper

from .config import get_config_dir
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
    patch_boto_config()
    jsonpickle.setup_handlers()


def patch_boto_config():
    """
    boto has a boto.config object which is used to persist boto
    settings. The FPS module abuses this config by saving config to
    system locations. This function patches the config so that config
    data is only ever written to the recapturedocs config location.
    """
    import boto.pyami.config

    config_file = get_config_dir() / 'boto.cfg'
    boto.pyami.config.UserConfigPath = config_file
    boto.pyami.config.BotoConfigLocations = [config_file]
    # set the system config path to an invalid name so nothing is ever
    #  stored there
    boto.pyami.config.BotoConfigPath = '/invalid/path/name'
    # recreate the boto.config instance
    boto.config = boto.pyami.config.Config()
