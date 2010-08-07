from __future__ import print_function, absolute_import
import os
import mimetypes
import hashlib
from cStringIO import StringIO

from jaraco.util.iter_ import one
# suppress the deprecation warning in PyPDF
import warnings
warnings.filterwarnings('ignore', module='pdf', lineno=52)
from pyPdf import PdfFileReader, PdfFileWriter

todo = """
Simple front-end aesthetic improvements
Job persistence
Payment system
Add new and pending page
Automatically approve submitted work
Sanity checks on submitted work
Per-page rejection
Rich text editor
Support for non-standard documents
Privacy Enhancements
Partial Page support
"""

completed_features = """
Native PDF handling (PyPDF)
Run as daemon
document upload
document processing
"""

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

class RetypePageHIT(object):
	def __init__(self, server_url):
		self.server_url = server_url

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

	@property
	def id(self):
		if not len(self.registration_result) == 1: return None
		return self.registration_result[0].HITId

	def is_complete(self):
		conn = get_connection()
		assignments = conn.get_assignments(self.id)
		some_results = int(assignments.NumResults) >= 1
		complete_status = ('Submitted', 'Approved')
		self.assignments_cache = assignments
		return all(
			assignment.AssignmentStatus in complete_status
			for assignment in assignments)

	def get_data(self):
		assert self.is_complete()
		assignments = self.assignments_cache
		assignment = one(assignments)
		answers_set = one(assignment.answers)
		answer = dict(
			(answer.QuestionIdentifier, answer.FreeText)
			for answer in answers_set
			)
		return answer['content']

	def matches(self, id):
		"Returns true if this HIT matches the supplied hit id"
		return self.id == id

	def get_external_question(self):
		from boto.mturk.question import ExternalQuestion
		return ExternalQuestion(external_url=self.server_url, frame_height=600)

	def get_questions(self):
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
		url=self.server_url
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

class ConversionJob(object):
	def __init__(self, file, content_type, server_url, filename=None):
		self.file = file
		self.content_type = content_type
		self.filename = filename
		self.server_url = server_url

	def do_split_pdf(self):
		assert self.content_type == 'application/pdf'
		self.files = self.split_pdf(self.file, self.filename)
		del self.file

	@classmethod
	def _from_file(cls_, filename):
		content_type, encoding = mimetypes.guess_type(filename)
		return cls_(open(filename, 'rb'), content_type, filename)

	def register_hits(self):
		self.hits = [RetypePageHIT(self.server_url) for file in self.files]
		for hit in self.hits:
			hit.register()
		assert all(hit.registration_result.status == True for hit in self.hits)

	@property
	def id(self):
		if not hasattr(self, 'hits'): return None
		hitids = (hit.id for hit in self.hits)
		hitids_cat = ''.join(hitids)
		return hashlib.md5(hitids_cat).hexdigest()

	def is_complete(self):
		return all(hit.is_complete() for hit in self.hits)

	def get_data(self):
		return '\n\nPAGE\n\n'.join(hit.get_data() for hit in self.hits)

	def run(self):
		self.do_split_pdf()
		self.register_hits()

	@staticmethod
	def split_pdf(source_stream, filename):
		input = PdfFileReader(source_stream)
		def get_page_data(page):
			output = PdfFileWriter()
			output.addPage(page)
			stream = StringIO()
			output.write(stream)
			return stream.getvalue()
		return map(get_page_data, input.pages)

