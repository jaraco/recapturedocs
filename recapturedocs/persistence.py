from __future__ import absolute_import

import urlparse
import warnings

import pymongo
import cherrypy
import jaraco.util.functools as functools

from .config import get_config_dir
from . import jsonpickle

@functools.once
def add_mongodb_scheme():
	"""
	urlparse doesn't support the mongodb scheme, but it's easy
	to make it so.
	"""
	lists = [urlparse.uses_relative, urlparse.uses_netloc, urlparse.uses_query]
	for l in lists:
		l.append('mongodb')

def mongodb_connect_uri(uri, **kwargs):
	"""
	Connect to the mongodb database specified by the URI.
	Return the connection and database object specified by the URI. If
	no database is specified, the admin db will be returned.
	"""
	add_mongodb_scheme()
	puri = urlparse.urlparse(uri)
	# in mongodb, if a username is not specified, but a database is included
	# in the URI, a warning will be emitted. Suppress this warning.
	with warnings.catch_warnings():
		cherrypy.log('Connecting to %s' % uri)
		conn = pymongo.Connection(uri, **kwargs)
	db_name = puri.path.lstrip('/') or 'admin'
	return conn, conn[db_name]

def init_mongodb():
	ps = cherrypy._whole_config.get('persistence', dict())
	storage_uri = ps.get('storage.uri', 'mongodb://localhost')
	conn, store = mongodb_connect_uri(storage_uri, _connect=False)
	if store.name == 'admin':
		store = conn['recapturedocs']
	is_production = cherrypy.config.get('server.production', False)
	if not is_production:
		store = conn[store.name + '_devel']
	globals().update(store = store)

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
