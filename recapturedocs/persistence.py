import pickle
import os

from jaraco.util.concurrency import AtomicGuard

def get_config_dir():
	return os.path.dirname(__file__)

guard = AtomicGuard()

@guard
def save(key, objects):
	"""
	Use pickle to save objects to a file
	"""
	filename = os.path.join(get_config_dir(), key+'.pickle')
	with open(filename, 'wb') as file:
		pickle.dump(objects, file, protocol=pickle.HIGHEST_PROTOCOL)

@guard
def load(key):
	filename = os.path.join(get_config_dir(), key+'.pickle')
	if not os.path.isfile(filename):
		return
	with open(filename, 'rb') as file:
		return pickle.load(file)

def init():
	patch_boto_config()

def patch_boto_config():
	"""
	boto has a boto.config object which is used to persist boto
	settings. The FPS module abuses this config by saving config to
	system locations. This function patches the config so that config
	data is only ever written to the recapturedocs config location.
	"""
	import boto.pyami.config
	config_file = os.path.join(get_config_dir(), 'boto.cfg')
	boto.pyami.config.UserConfigPath = config_file
	boto.pyami.config.BotoConfigLocations = [config_file]
	# set the system config path to an invalid name so nothing is ever
	#  stored there
	boto.pyami.config.BotoConfigPath = '/invalid/path/name'
	# recreate the boto.config instance
	boto.config = boto.pyami.config.Config()
