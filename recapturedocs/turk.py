from __future__ import print_function
import os
import sys
import subprocess
import socket
from glob import glob
from optparse import OptionParser
from jaraco.filesystem import insert_before_extension
from jaraco.util.string import local_format as lf

def make_turk_recognition_job_from_pdf():
	options, args = OptionParser().parse_args()
	infile = args.pop()

	dest = '/inetpub/wwwroot/pages'
	if not os.path.isdir(dest):
		os.makedirs(dest)

	name = os.path.basename(infile)
	page_fmt = insert_before_extension(name, '-%002d')
	dest_name = os.path.join(dest, page_fmt)

	cmd = ['pdftk', infile, 'burst', 'output', dest_name]
	res = subprocess.Popen(cmd).wait()
	if res != 0:
		print("failed", file=sys.stderr)
		raise SystemExit(res)

	os.remove('doc_data.txt')
	files = glob(os.path.join(dest, insert_before_extension(name, '*')))
	files = map(os.path.basename, files)
	job = open(os.path.join(dest, 'job.txt'), 'w')
	print("PAGE_URL", file=job)
	for file in files:
		hostname = socket.getfqdn()
		print(lf('http://{hostname}/pages/{file}'), file=job)

def set_connection_environment(access_key='0ZWJV1BMM1Q6GXJ9J2G2'):
	"""
	boto requires the credentials to be either passed to the connection,
	stored in a unix-like config file unencrypted, or available in
	the environment, so pull the encrypted key out and put it in the
	environment.
	"""
	import keyring
	secret_key = keyring.get_password('AWS', access_key)
	os.environ['AWS_ACCESS_KEY_ID'] = access_key
	os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key

def get_connection():
	from boto.mturk.connection import MTurkConnection
	set_connection_environment()
	return MTurkConnection(
		host='mechanicalturk.sandbox.amazonaws.com',
		debug=True,
		)

def get_question():
	from boto.mturk.question import Question, FreeTextAnswer, QuestionContent
	c = QuestionContent()
	c.append('foo', 'How many movies have you watched this month?')
	a = FreeTextAnswer()
	q = Question('movies', c, a)
	return q

def register_hit():
	conn = get_connection()
	from boto.mturk.price import Price
	type_params = dict(
		title="Movie Survey",
		description="This is a survey to find out how many movies you have watched recently.",
		#keywords='movies,subjective',
		reward=Price(0.05),
		)
		
	return conn.create_hit(question=get_question(), **type_params)

if __name__ == '__main__':
	make_turk_recognition_job_from_pdf()
