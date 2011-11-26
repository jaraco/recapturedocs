from __future__ import print_function, absolute_import
import os
import mimetypes
import hashlib
import datetime
from cStringIO import StringIO
import logging

from jaraco.util.itertools import one
from jaraco.util.string import local_format as lf
import jaraco.modb

# suppress the deprecation warning in PyPDF
import warnings
warnings.filterwarnings('ignore', module='pyPdf.pdf', lineno=52)
from pyPdf import PdfFileReader, PdfFileWriter

from . import aws
from . import persistence

todo = """
Site Design
Automatically approve submitted work
E-mail results
E-mail link to status
update faq to mention language issues
Job Naming (maybe use filename, maybe provide user-supplied field)
Add new and pending features page
Sanity checks on submitted work
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
Improved persistence (S3 storage or similar)
Same Job Detection
Typist Rejection (for jobs that are too complex)
Terms and Conditions
Privacy Policy
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

log = logging.getLogger(__name__)

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
	"""
	Conversion Job, a collection of pages to be retyped
	"""

	"$1.95 per page"
	page_cost = DollarAmount(1.95)

	def __init__(self, stream, content_type, server_url, filename=None):
		self.created = datetime.datetime.now()
		self.stream = stream
		self.content_type = content_type
		self.filename = filename
		self.server_url = server_url
		self.do_split_pdf()
		self.authorized = False

	@property
	def cost(self):
		return DollarAmount(self.page_cost * len(self))

	def do_split_pdf(self):
		msg = "Only PDF content is supported (got {content_type} instead)"
		assert self.content_type == 'application/pdf', msg.format(**vars(self))
		self.pages = self.split_pdf(self.stream)
		del self.stream

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
		"""
		Compute the id of this job as the hash of the content.
		"""
		hash = hashlib.md5()
		map(hash.update, self.pages)
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

	def matches(self, other):
		return self.pages == other.pages

	def save_if_new(self):
		"""
		Only save the job if there isn't already a job with the same hash
		"""
		if self.load(self.id): return
		self.save()

	def save(self):
		data = jaraco.modb.encode(self)
		#log.debug("saving {0!r}".format(data))
		data['_id'] = self.id
		self._id = persistence.store.jobs.save(data)

	def remove(self):
		assert self.id is not None
		persistence.store.jobs.remove(self.id)

	@classmethod
	def load(cls, id):
		data = persistence.store.jobs.find_one({'_id': id})
		return cls._restore(data) if data else None

	@classmethod
	def load_all(cls):
		return (cls._restore(data) for data in persistence.store.jobs.find())

	@classmethod
	def _restore(cls, data):
		id = data.pop('_id')
		result = jaraco.modb.decode(data)
		if not result.id == id:
			raise ValueError(lf("ID mutated on load: {id} became "
				"{result.id}"))
		return result

	@classmethod
	def for_hitid(cls, hit_id):
		# the hitID is stored in the database here
		hitid_loc = 'hits.registration_result.py/seq.HITId'
		data = persistence.store.jobs.find_one({hitid_loc: hit_id})
		return cls._restore(data)

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
