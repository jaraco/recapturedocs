from __future__ import absolute_import, print_function

import os

import keyring
import dropbox

def get_session(access_key='ld83qebudvbirmj'):
	if 'Dropbox secret' in os.environ:
		return
	secret = keyring.get_password('Dropbox RecaptureDocs', access_key)
	assert secret, "Dropbox secret is null"
	os.environ['Dropbox access key'] = access_key
	os.environ['Dropbox secret'] = secret
	return dropbox.session.DropboxSession(access_key, secret, 'app_folder')

def test_session():
	sess = get_session()
	request_token = sess.obtain_request_token()
	url = sess.build_authorize_url(request_token)
	print("url:", url)
	print("Please 'allow' this app at the above URL")
	raw_input()

	access_token = sess.obtain_access_token(request_token)
	client = dropbox.client.DropboxClient(sess)
	print("linked account:", client.account_info())

	folder_metadata = client.metadata('/')
	print("metadata:", folder_metadata)

if __name__ == '__main__':
	test_session()
