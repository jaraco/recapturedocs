from __future__ import print_function

import json
import pprint

from six.moves import urllib

import keyring.http
import jaraco.net.http

app_name = 'recapturedocs'

class FixedUserKeyringPasswordManager(keyring.http.PasswordMgr):
	def __init__(self, username):
		self.username = username

	def get_username(self, realm, authuri):
		print('realm is', realm)
		print('authuri is', authuri)
		return self.username

	# provide clear_password until delete_password is officially
	#  implemented.
	def clear_password(self, realm, authuri):
		user = self.get_username(realm, authuri)
		# this call will only succeed on WinVault for now
		keyring.get_keyring().delete_password(realm, user)

def install_opener():
	auth_manager = FixedUserKeyringPasswordManager(
		username='jaraco@jaraco.com')
	auth_handler = urllib.request.HTTPBasicAuthHandler(auth_manager)
	# build a new opener
	opener = urllib.request.build_opener(auth_handler)
	# install it
	urllib.request.install_opener(opener)

def configure_AWS():
	access_key = '0ZWJV1BMM1Q6GXJ9J2G2'
	secret_key = keyring.get_password('AWS', access_key)
	assert secret_key, "secret key is null"
	set_env_vars(
		AWS_ACCESS_KEY_ID = access_key,
		AWS_SECRET_ACCESS_KEY = secret_key,
	)

def set_env_vars(*args, **kwargs):
	do(path='config_vars', data=dict(*args, **kwargs), method='PUT')

def check_MongoHQ():
	do('addons')

def add_MongoHQ():
	install_addon('mongohq:free')

def do(path, **kwargs):
	headers = {
		'Accept': 'application/json',
	}
	headers.update(kwargs.pop('headers', {}))
	if 'data' in kwargs and isinstance(kwargs['data'], dict):
		kwargs['data'] = json.dumps(kwargs['data'])
	base = 'https://api.heroku.com/apps/{app_name}/'.format(**globals())
	url = urllib.parse.urljoin(base, path)
	req = jaraco.net.http.MethodRequest(url = url, headers=headers, **kwargs)
	res = urllib.request.urlopen(req)
	data = json.loads(res.read())
	if not 200 <= res.code < 300:
		print("ERROR: ", res.code)
	pprint.pprint(data)
	return data

def install_addon(name):
	path = 'addons/{name}'.format(name = name)
	do(path, method='POST')

def set_production():
	set_env_vars(
		COMMAND_LINE_ARGS='-C prod'
	)

def create_app():
	data = {
		'app[name]': app_name,
		'app[stack]': 'cedar',
	}
	do('/apps', method='POST', data=urllib.parse.urlencode(data))

if __name__ == '__main__':
	install_opener()
	create_app()
	configure_AWS()
	check_MongoHQ()
	add_MongoHQ()
	if app_name == 'recapturedocs':
		set_production()
