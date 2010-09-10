from __future__ import print_function, absolute_import
import os
import mimetypes
import hashlib
import datetime
from cStringIO import StringIO

from jaraco.util.iter_ import one
from jaraco.util.string import local_format as lf

# suppress the deprecation warning in PyPDF
import warnings
warnings.filterwarnings('ignore', module='pyPdf.pdf', lineno=52)
from pyPdf import PdfFileReader, PdfFileWriter

todo = """
Payment system
Terms and Conditions
Privacy Policy
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
Basic functional workflow
Job persistence
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
	type_params = dict(
		title="Type a Page",
		description="You will read a scanned page and retype its textual contents.",
		keywords='typing page rekey retype'.split(),
		reward=1.0,
		duration=datetime.timedelta(days=7),
		)

	def __init__(self, server_url):
		self.server_url = server_url

	@classmethod
	def disable_all(cls):
		"""
		Disable all hits that match this hit type
		"""
		conn = get_connection()
		all_hits = conn.get_all_hits()
		hit_type = cls.get_hit_type()
		is_local_hit = lambda h: h.HITTypeId == hit_type
		local_hits = filter(is_local_hit, all_hits)
		for hit in local_hits:
			conn.disable_hit(hit.HITId)
		return len(local_hits)

	@classmethod
	def get_hit_type(cls):
		conn = get_connection()
		result = conn.register_hit_type(**cls.type_params)
		return result.HITTypeId

	def register(self):
		conn = get_connection()
		res = conn.create_hit(question=self.get_external_question(),
			**self.type_params)
		self.registration_result = res
		return res

	@property
	def id(self):
		if not len(self.registration_result) == 1: return None
		return self.registration_result[0].HITId

	def load_assignments(self):
		conn = get_connection()
		return conn.get_assignments(self.id)

	def max_assignments(self):
		res = getattr(self.registration_result[0], 'MaxAssignments', None)
		return int(res) if res else 1

	def is_complete(self):
		if not self.id: return False
		assignments = self.load_assignments()
		some_results = int(assignments.NumResults) >= 1
		complete_status = ('Submitted', 'Approved')
		self.assignments_cache = assignments
		return some_results and all(
			assignment.AssignmentStatus in complete_status
			for assignment in assignments)

	def get_data(self):
		assert self.is_complete()
		assignments = self.assignments_cache
		assignment = one(assignments)
		answers_set = one(assignment.answers)
		answer = dict(
			answer.fields[0]
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
		self.created = datetime.datetime.now()
		self.file = file
		self.content_type = content_type
		self.filename = filename
		self.server_url = server_url
		self.do_split_pdf()
		self.authorized = False

	@property
	def cost(self):
		"$2 per page"
		cost = float(2*len(self))
		return lf('${cost}')

	def do_split_pdf(self):
		msg = "Only PDF content is supported"
		assert self.content_type == 'application/pdf', msg
		self.pages = self.split_pdf(self.file)
		del self.file

	@classmethod
	def _from_file(cls_, filename):
		content_type, encoding = mimetypes.guess_type(filename)
		return cls_(open(filename, 'rb'), content_type, filename)

	def register_hits(self):
		"""
		Create a hit for each page in the job.
		
		The mapping of HIT to page is implicit - they're kept arranged
		in order so that zip(self.pages, self.hits) always produces
		pairs of each page with its HIT.
		"""
		self.hits = [RetypePageHIT(self.server_url) for page in self.pages]
		for hit in self.hits:
			hit.register()
		assert all(hit.registration_result.status == True for hit in self.hits)

	@property
	def id(self):
		# Compute the id of this job as the hash of the content and the
		#  date it was created.
		hash = hashlib.md5()
		map(hash.update, self.pages)
		hash.update(str(self.created))
		return hash.hexdigest()

	def is_complete(self):
		return all(hit.is_complete() for hit in self.hits)

	def get_data(self):
		return '\n\nPAGE\n\n'.join(hit.get_data() for hit in self.hits)

	def get_hit(self, hit_id):
		return next(
			hit for hit in self.hits if hit.id == hit_id
			)

	def page_for_hit(self, hit_id):
		pages = dict(
			(hit.id, page)
			for hit, page in zip(self.hits, self.pages)
			)
		return pages[hit_id]

	@staticmethod
	def split_pdf(source_stream):
		input = PdfFileReader(source_stream)
		def get_page_data(page):
			output = PdfFileWriter()
			output.addPage(page)
			stream = StringIO()
			output.write(stream)
			return stream.getvalue()
		return map(get_page_data, input.pages)

	def __len__(self):
		return len(self.pages)

def get_all_hits(conn):
	page_size = 100
	search_rs = conn.search_hits(page_size=page_size)
	total_records = int(search_rs.TotalNumResults)
	def get_page_hits(page):
		search_rs = conn.search_hits(page_size=page_size, page_number=page)
		if not search_rs.status:
			fmt = 'Error performing search, code:%s, message:%s'
			msg = fmt%(search_rs.Code, search_rs.Message)
			raise Exception(msg)
		return search_rs
	hit_sets = map(get_page_hits, get_pages(page_size, total_records))
	return list(itertools.chain(*hit_sets))
