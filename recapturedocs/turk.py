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

def save_credentials(access_key, secret_key):
	import keyring
	keyring.set_password('AWS', access_key, secret_key)

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

def register_hit():
	conn = get_connection()
	from boto.mturk.price import Price
	type_params = dict(
		title="Type a Page",
		description="You will read a scanned page and retype its textual contents.",
		#keywords='typing,page,rekey',
		reward=Price(1.0),
		questions = RetypePageHIT.get_questions(),
		)
		
	return conn.create_hit(**type_params)

class RetypePageHIT:
	@staticmethod
	def get_questions():
		from boto.mturk.question import (
			Overview, FormattedContent, Question, FreeTextAnswer,
			QuestionContent, List, QuestionForm, AnswerSpecification,
			)
		form = QuestionForm()
		o = Overview()
		o.append_field('Title', 'Type a Page')
		o.append_field('Text', 'You will read a scanned page and retype its textual contents. Here are some tips.')
		instructions = List([
			'You will need a PDF viewer. If you do not already have a PDF viewer, you can &lt;a href="http://get.adobe.com/reader/"&gt;download Adobe Reader&lt;/a&gt;',
			'Please use your best judgement for including hand-written notes.',
			'If you encounter something that is unrecognizable or unclear, do your best, then include three exclamation marks (!!!) to indicate that a problem occurred.',
			'Please use exact capitalization spacing and punctuation.',
			'In general, do not worry about formatting. Type each paragraph without carriage returns, and include a single carriage return between paragraphs.',
			'If you encounter tables, type each row on the same line using the pipe (|) to separate columns.',
			])
		o.append(instructions)
		url="http://drake.jaraco.com/docs/"
		o.append(FormattedContent(
			'The page is displayed below. If you prefer, you can use a '
			'<a href="{url}">link to the page</a> to save the file or open '
			'it in a separate window (using right-click and Save Link As or '
			'Save Target As).'.format(**vars())))
		form.append(o)
		
		c = QuestionContent()
		c.append_field("Text", "Type the content of the page here")
		a = AnswerSpecification(FreeTextAnswer())
		q = Question('content', c, a)
		form.append(q)
		
		c = QuestionContent()
		c.append_field('Text', 'If you have any comments or questions, please include them here.')
		a = AnswerSpecification(FreeTextAnswer())
		q = Question('comment', c, a)
		form.append(q)
		
		form.validate()
		return form

template = """		
<p><iframe width="100%" height="50%" src="${PAGE_URL}">[Your browser does <em>not</em> support <code>iframe</code>,
or has been configured not to display inline frames.
You can access <a href="${PAGE_URL}">the document</a>
via a link though.]</iframe></p>
"""


class Server:
	def index(self, hitId, assignmentId):
		return '<div>Hit ID is %(hitId)s</div><div>Assignment ID is %(assignmentId)s</div>' % vars()
	index.exposed = True

def start_server():
	import cherrypy
	config = {
		'global' : {
		'server.socket_host': '::0'
		},
	}
	cherrypy.quickstart(Server(), config=config)

if __name__ == '__main__':
	#make_turk_recognition_job_from_pdf()
	res = register_hit()
