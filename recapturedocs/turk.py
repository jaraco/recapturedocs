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

from . import aws

page_ideas = """
tagline (or unattributed quote): It's nothing to write home about... unless you need a document retyped; then it's the shi*"""

todo = """
Typist Rejection (for jobs that are too complex)
Terms and Conditions
Privacy Policy
Same Job Detection
Improved persistence (S3 storage or similar)
Job Naming (maybe use filename, maybe provide user-supplied field)
Add new and pending features page
Automatically approve submitted work
Sanity checks on submitted work
Site Design
Rich text editor
Port to App Engine
Support for non-standard documents
 - image extraction
 - standard forms
 - data sheets
Privacy Enhancements
Partial Page support
"""

completed_features = """
Auto-refresh Status Page
Improved Sample HIT support
Thread Safety
Basic Aesthetics
Payment System
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

class DollarAmount(float):
	def __str__(self):
		string = super(DollarAmount, self).__str__()
		return lf('${string}')

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
		conn = aws.ConnectionFactory.get_mturk_connection()
		all_hits = conn.get_all_hits()
		hit_type = cls.get_hit_type()
		is_local_hit = lambda h: h.HITTypeId == hit_type
		local_hits = filter(is_local_hit, all_hits)
		for hit in local_hits:
			conn.disable_hit(hit.HITId)
		return len(local_hits)

	@classmethod
	def get_hit_type(cls):
		conn = aws.ConnectionFactory.get_mturk_connection()
		result = conn.register_hit_type(**cls.type_params)
		return result.HITTypeId

	def register(self):
		conn = aws.ConnectionFactory.get_mturk_connection()
		res = conn.create_hit(question=self.get_external_question(),
			**self.type_params)
		self.registration_result = res
		return res

	@property
	def id(self):
		if not len(self.registration_result) == 1: return None
		return self.registration_result[0].HITId

	def load_assignments(self):
		conn = aws.ConnectionFactory.get_mturk_connection()
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
		return DollarAmount(float(2*len(self)))

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
		return '\n\n\n'.join(hit.get_data() for hit in self.hits)

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
