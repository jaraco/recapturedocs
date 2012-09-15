from __future__ import absolute_import, print_function

import keyring
import dropbox

def get_session(access_key='ld83qebudvbirmj'):
	secret = keyring.get_password('Dropbox RecaptureDocs', access_key)
	assert secret, "Dropbox secret is null"
	return dropbox.session.DropboxSession(access_key, secret, 'app_folder')

def get_client(sess):
	return dropbox.client.DropboxClient(sess)

def test_session():
	sess = get_session()
	request_token = sess.obtain_request_token()
	callback = 'http://www.recapturedocs.com/...'
	url = sess.build_authorize_url(request_token, oauth_callback=callback)
	print("url:", url)
	print("Please 'allow' this app at the above URL")
	raw_input()

	access_token = sess.obtain_access_token(request_token)
	client = get_client(sess)
	print("linked account:", client.account_info())

	folder_metadata = client.metadata('/')
	print("metadata:", folder_metadata)

if __name__ == '__main__':
	test_session()
