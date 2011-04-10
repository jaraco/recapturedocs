import pymongo
import cherrypy
import jaraco.modb

from .config import get_config_dir

def init_mongodb():
	ps = persistence_settings = cherrypy.config.get('persistence', dict())
	storage_host = ps.get('storage.host')
	conn = pymongo.Connection(storage_host, _connect=False)
	storage_db = ps.get('storage.db', 'recapturedocs')
	is_production = cherrypy.config.get('server.production', False)
	if not is_production:
		storage_db += '_devel'
	globals().update(store = conn[storage_db])

def init():
	init_mongodb()
	patch_boto_config()
	jaraco.modb.init()

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
