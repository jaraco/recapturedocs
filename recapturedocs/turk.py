from __future__ import print_function
import os
import sys
import optparse
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

class RetypePageHIT:
	def register(self):
		conn = get_connection()
		from boto.mturk.price import Price
		type_params = dict(
			title="Type a Page",
			description="You will read a scanned page and retype its textual contents.",
			keywords='typing page rekey'.split(),
			reward=Price(1.0),
			)
			
		return conn.create_hit(question=self.get_external_question(), **type_params)

	@staticmethod
	def get_external_question():
		from boto.mturk.question import ExternalQuestion
		external_url = 'http://drake.jaraco.com:8080/'
		return ExternalQuestion(external_url=external_url, frame_height=600)
		conn = get_connection()

	@staticmethod
	def get_questions():
		"""
		This techniuque attempts to use the amazon mturk api to construct
		a QuestionForm suitable for performing the operation. Unfortunately,
		it appears Amazon does not support inline PDF content.
		http://developer.amazonwebservices.com/connect/thread.jspa?threadID=48210&tstart=0
		"""
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
<h1>Type a Page</h1>
<p>Please re-type the content of the PDF page (a link is provided below). Please note,</p>
<ul>
    <li>You will need a PDF viewer. If you do not already have a PDF viewer, you can <a href="http://get.adobe.com/reader/">download Adobe Reader</a>.</li>
    <li>Please use your best judgement for including hand-written notes.</li>
    <li>If you encounter something that's unrecognizable or unclear, do your best, then include three exclamation marks (!!!) to indicate that a problem occurred.</li>
    <li>Please use exact capitalization spacing and punctuation.</li>
    <li>In general, do not worry about formatting. Type each paragraph without carriage returns, and include a single carriage return between paragraphs.</li>
    <li>If you encounter tables, type each row on the same line using the pipe (|) to separate columns.</li>
</ul>
<p>The page is displayed below. If you prefer, you can use a <a href="{page_url}">link to the page</a> to save the file or open it in a separate window (using right-click and Save Link As or Save Target As).</p>
<p><iframe width="100%" height="50%" src="{page_url}">[Your browser does <em>not</em> support <code>iframe</code>,
or has been configured not to display inline frames.
You can access <a href="{page_url}">the document</a>
via a link though.]</iframe></p>
<p>Type the content of the page here.</p>
<form action="http://www.mturk.com/mturk/externalSubmit" method="POST">
	<field type="hidden" value="{assignmentId}" name="assignmentId" />
	<p><textarea rows="15" cols="80" name="content"></textarea></p>
	<p>If you have any comments or questions, please include them here.</p>
	<p><textarea rows="3" cols="80" name="comment"></textarea></p>
</form>
"""


class Server:
	def index(self, hitId, assignmentId):
		page_url = 'http://tbd'
		return template.format(**vars())
	index.exposed = True

def start_server():
	import cherrypy
	config = {
		'global' : {
		'server.socket_host': '::0'
		},
	}
	cherrypy.quickstart(Server(), config=config)

def handle_command_line():
	parser = optparse.OptionParser()
	options, args = parser.parse_args()
	if 'serve' in args:
		start_server()
		raise SystemExit(0)
	hit = RetypePageHIT()
	res = hit.register()
	assert res.status == True

if __name__ == '__main__':
	handle_command_line()
