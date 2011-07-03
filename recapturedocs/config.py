import sys
import os
from path import path
from jaraco.util.filesystem import ensure_dir_exists
import cherrypy

appname = 'RecaptureDocs'

def get_log_file():
	return get_config_dir() / 'log.txt'

def get_error_file():
	return get_config_dir() / 'error.txt'

def get_config_dir():
	#candidate = path(sys.prefix) / 'var'
	#if candidate.isdir():
	#	return candidate
	@ensure_dir_exists
	def get_log_root_win32():
		return path(os.environ['APPDATA']) / appname
	@ensure_dir_exists
	def get_log_root_linux2():
		if sys.prefix == '/usr':
			return path('/var') / appname.lower()
		return path(sys.prefix) / 'var' / appname.lower()
	getter = locals()['get_log_root_'+sys.platform]
	base = getter()
	@ensure_dir_exists
	def resolve_base():
		# todo: consider adding an honest setting for the config identifier
		dir = base
		if not cherrypy.config.get('server.production', False):
			dir = base / 'dev'
		return dir
	return resolve_base()