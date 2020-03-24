import sys
import os
import platform

from path import Path
import jaraco.functools
import cherrypy

appname = 'RecaptureDocs'

ensure_dir_exists = jaraco.functools.apply(lambda p: p.makedirs_p())


def get_log_file():
    return get_config_dir() / 'log.txt'


def get_error_file():
    return get_config_dir() / 'error.txt'


def get_config_dir():
    def get_env_root():
        if hasattr(sys, 'real_prefix'):
            # virtualenv
            return sys.prefix
        elif os.environ.get('PYTHONUSERBASE', None):
            # PEP-370 env
            return os.environ['PYTHONUSERBASE']

    @ensure_dir_exists
    def get_app_root_Windows():
        return Path(get_env_root() or os.environ['APPDATA']) / appname

    @ensure_dir_exists
    def get_app_root_Linux():
        return Path(get_env_root() or '/var') / appname.lower()

    getter = locals().get('get_app_root_' + platform.system(), 'get_app_root_Linux')
    base = getter()

    @ensure_dir_exists
    def resolve_base():
        # todo: consider adding an honest setting for the config identifier
        dir = base
        if not cherrypy.config.get('server.production', False):
            dir = base / 'dev'
        return dir

    # return an absolute Path because CherryPy requires one
    return resolve_base().abspath()
