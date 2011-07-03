
import os

from jaraco.util.string import local_format as lf
import boto.fps.connection
import boto.mturk.connection

def set_connection_environment(access_key='0ZWJV1BMM1Q6GXJ9J2G2'):
	"""
	boto requires the credentials to be either passed to the connection,
	stored in a unix-like config file unencrypted, or available in
	the environment, so pull the encrypted key out and put it in the
	environment.
	"""
	import keyring
	secret_key = keyring.get_password('AWS', access_key)
	assert secret_key, "Secret key is null"
	os.environ['AWS_ACCESS_KEY_ID'] = access_key
	os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key

class ConnectionFactory(object):
	production=True

	@classmethod
	def get_fps_endpoint(class_):
		host = 'authorize.payments-sandbox.amazon.com'
		if class_.production:
			host = host.replace('payments-sandbox', 'payments')
		return lf('https://{host}/cobranded-ui/actions/start')

	@classmethod
	def get_fps_connection(class_):
		set_connection_environment()
		host = ['fps.sandbox.amazonaws.com', 'fps.amazonaws.com'][
			class_.production]
		return boto.fps.connection.FPSConnection(host=host)

	@classmethod
	def get_mturk_connection(class_):
		set_connection_environment()
		host = ['mechanicalturk.sandbox.amazonaws.com',
			'mechanicalturk.amazonaws.com'][class_.production]
		return boto.mturk.connection.MTurkConnection(host=host)

