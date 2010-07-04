from __future__ import print_function, absolute_import
import os
import sys
import optparse
import subprocess
import socket
import tempfile
import functools
import pkg_resources
import mimetypes
from glob import glob
from textwrap import dedent
from optparse import OptionParser

from jaraco.filesystem import insert_before_extension, DirectoryStack
from jaraco.util.string import local_format as lf

class ConversionError(BaseException):
	pass

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
			keywords='typing page rekey retype'.split(),
			reward=Price(1.0),
			)
			
		res = conn.create_hit(question=self.get_external_question(), **type_params)
		self.registration_result = res
		return res

	@staticmethod
	def get_external_question():
		from boto.mturk.question import ExternalQuestion
		external_url = 'http://drake.jaraco.com:8080/process'
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

local_resource = functools.partial(pkg_resources.resource_stream, __name__)
template = local_resource('retype page template.xhtml').read()

class ConversionJob(object):
	def __init__(self, file, content_type, filename=None):
		self.file = file
		self.content_type = content_type
		self.filename = filename

	def do_split_pdf(self):
		assert self.content_type == 'application/pdf'
		self.files = self.split_pdf(self.file, self.filename)

	@classmethod
	def _from_file(cls_, filename):
		content_type, encoding = mimetypes.guess_type(filename)
		return cls_(open(filename, 'rb'), content_type, filename)

	def register_hits(self):
		self.hits = [RetypePageHIT() for file in self.files]
		for hit in self.hits:
			hit.register()
		assert all(hit.registration_result.status == True for hit in self.hits)

	def run(self):
		self.do_split_pdf()
		self.register_hits()

	@staticmethod
	def split_pdf(source_stream, filename):
		page_fmt = insert_before_extension(filename, '-%002d')
		dest_dir = tempfile.mkdtemp()

		stack = DirectoryStack()
		with stack.context(dest_dir):
			cmd = ['pdftk', '-', 'burst', 'output', page_fmt]
			proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
			proc.communicate(source_stream.read())
			# pdftk always generates doc_data.txt in the current directory
			os.remove('doc_data.txt')
			if proc.returncode != 0:
				raise ConversionError("Error splitting file")
			
			output_filenames = glob(insert_before_extension(filename, '*'))
			files = map(ConversionJob.load_and_remove, output_filenames)
		os.rmdir(dest_dir)
		return files

	@staticmethod
	def load_and_remove(filename):
		with open(filename, 'rb') as f:
			data = f.read()
		os.remove(filename)
		return data

class JobServer(list):
	def index(self):
		return 'coming soon'
	index.exposed = True

	def test_upload(self):
		return dedent("""
			<form method='POST' enctype='multipart/form-data'
				action='upload'>
			File to upload: <input type="file" name="file"></input><br />
			<br />
			<input type="submit" value="Press"></input> to upload the file!
			</form>
			""").strip()
	test_upload.exposed = True

	def upload(self, file):
		job = ConversionJob(file.file, str(file.content_type), file.filename)
		job.run()
		self.append(job)
		nhits = len(job.hits)
		return lf('File was uploaded and created {nhits} hits')
	upload.exposed = True

	def process(self, hitId, assignmentId):
		page_url = lf('/image/{hitId}')
		return lf(template)
	process.exposed = True

	def image(self, hitId):
		# find the appropriate image
		for job in self:
			for file, hit in zip(job.files, job.hits):
				continue # todo: hit.id below is not correct
				if hit.id == hitId:
					cherrypy.response.headers['Content-Type'] = 'application/pdf'
					return file
		return lf('<div>File not found for hitId {hitId}</div>')
	image.exposed = True

def start_server():
	import cherrypy
	config = {
		'global' : {
		'server.socket_host': '::0'
		},
	}
	cherrypy.quickstart(JobServer(), config=config)

def handle_command_line():
	parser = optparse.OptionParser()
	options, args = parser.parse_args()
	if 'serve' in args:
		start_server()
		raise SystemExit(0)

if __name__ == '__main__':
	handle_command_line()
