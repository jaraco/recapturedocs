import itertools
import mimetypes
import hashlib
import datetime
import io
import logging
import math

from jaraco.itertools import one, first
from jaraco.text import indent
import jaraco.modb
import boto.mturk.connection
from PyPDF2 import PdfFileReader, PdfFileWriter

from . import aws
from . import persistence
from . import errors

log = logging.getLogger(__name__)


class ConversionError(BaseException):
    pass


class DollarAmount(float):
    def __str__(self):
        return '$' + super(DollarAmount, self).__str__()


class RetypePageHIT:
    reward_per_page = DollarAmount(1)

    type_params = dict(
        title="Type a Page",
        description="You will read a scanned page and retype its textual " "contents.",
        keywords='typing page rekey retype'.split(),
        reward=float(reward_per_page),
        duration=datetime.timedelta(hours=2),
    )

    def __init__(self, server_url):
        self.server_url = server_url

    @classmethod
    def _local_hits(cls):
        """
        Return all HITs that match this HIT type
        """
        conn = aws.ConnectionFactory.get_mturk_connection()
        all_hits = conn.get_all_hits()
        hit_type = cls.get_hit_type()

        def is_local_hit(h):
            return h.HITTypeId == hit_type

        return filter(is_local_hit, all_hits)

    @classmethod
    def disable_all(cls):
        """
        Disable all hits that match this hit type
        """
        local_hits = list(cls._local_hits())
        conn = aws.ConnectionFactory.get_mturk_connection()
        for hit in local_hits:
            conn.disable_hit(hit.HITId)
        return len(local_hits)

    @classmethod
    def load_all(cls):
        return [cls._from_existing(hit) for hit in cls._local_hits()]

    @classmethod
    def _from_existing(cls, res):
        hit = cls(None)
        hit.registration_result = [res]
        return hit

    @classmethod
    def get_hit_type(cls):
        conn = aws.ConnectionFactory.get_mturk_connection()
        result = one(conn.register_hit_type(**cls.type_params))
        return result.HITTypeId

    def register(self):
        conn = aws.ConnectionFactory.get_mturk_connection()
        try:
            res = conn.create_hit(
                question=self.get_external_question(), **self.type_params
            )
        except boto.mturk.connection.MTurkRequestError as error:
            if not error.error_code == 'AWS.MechanicalTurk.InsufficientFunds':
                raise
            raise errors.InsufficientFunds()
        self.registration_result = res
        return res

    @property
    def id(self):
        if len(self.registration_result) != 1:
            return None
        return self.registration_result[0].HITId

    @property
    def status(self):
        conn = aws.ConnectionFactory.get_mturk_connection()
        return one(conn.get_hit(self.id)).HITStatus

    def load_assignments(self):
        conn = aws.ConnectionFactory.get_mturk_connection()
        return conn.get_assignments(self.id)

    def max_assignments(self):
        res = getattr(self.registration_result[0], 'MaxAssignments', None)
        return int(res) if res else 1

    def is_complete(self):
        if not self.id:
            return False
        assignments = self.load_assignments()
        some_results = int(assignments.NumResults) >= 1
        complete_status = ('Submitted', 'Approved')
        self.assignments_cache = assignments
        return some_results and all(
            assignment.AssignmentStatus in complete_status for assignment in assignments
        )

    def get_data(self):
        assert self.is_complete()
        assignments = self.assignments_cache
        assignment = first(assignments)
        answers_set = one(assignment.answers)
        answer = dict((answer.qid, one(answer.fields)) for answer in answers_set)
        return answer['content']

    def matches(self, id):
        "Returns true if this HIT matches the supplied hit id"
        return self.id == id

    def get_external_question(self):
        from boto.mturk.question import ExternalQuestion

        return ExternalQuestion(external_url=self.server_url, frame_height=600)

    def _report(self):
        yield f'hit {self.id} ({self.status})'
        for assignment in self.load_assignments():
            yield indent(str(assignment))


class ConversionJob:
    """
    Conversion Job, a collection of pages to be retyped
    """

    can_authorize = True
    page_cost = DollarAmount(1.95)
    "Price per page charged to the customer"

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

    @property
    def id(self):
        """
        Compute the id of this job as the hash of the content.
        """
        hash = hashlib.md5()
        list(map(hash.update, self.pages))
        return hash.hexdigest()

    @staticmethod
    def split_pdf(source_stream):
        input = PdfFileReader(source_stream)

        def get_page_data(page):
            output = PdfFileWriter()
            output.addPage(page)
            stream = io.BytesIO()
            output.write(stream)
            return stream.getvalue()

        return list(map(get_page_data, input.pages))

    def __len__(self):
        return len(self.pages)

    def matches(self, other):
        return self.pages == other.pages

    def save_if_new(self):
        """
        Only save the job if there isn't already a job with the same hash
        """
        query = dict(_id=self.id)
        persistence.store.jobs.find(query).count() or self.save()

    def save(self):
        data = jaraco.modb.encode(self)
        # log.debug("saving {0!r}".format(data))
        data['_id'] = self.id
        self._id = persistence.store.jobs.save(data, safe=True)

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
            raise ValueError(f"ID mutated on load: {id} became {result.id}")
        return result


class MTurkConversionJob(ConversionJob):
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
        assert all(hit.registration_result.status is True for hit in self.hits)

    @property
    def can_authorize(self):
        """
        A job cannot be authorized if the balance in the Mechanical Turk
        account is not sufficient to service the job.
        """
        conn = aws.ConnectionFactory.get_mturk_connection()
        balance = conn.get_account_balance()[0].amount
        return RetypePageHIT.reward_per_page * len(self) <= balance

    def is_complete(self):
        return all(hit.is_complete() for hit in self.hits)

    def get_data(self):
        return '\n\n\n'.join(hit.get_data() for hit in self.hits if hit.is_complete())

    def get_hit(self, hit_id):
        return next(hit for hit in self.hits if hit.id == hit_id)

    def page_for_hit(self, hit_id):
        pages = dict((hit.id, page) for hit, page in zip(self.hits, self.pages))
        return pages[hit_id]

    @classmethod
    def for_hitid(cls, hit_id):
        # the hitID is stored in the database here
        hitid_loc = 'hits.registration_result.py/seq.HITId'
        data = persistence.store.jobs.find_one({hitid_loc: hit_id})
        return cls._restore(data)

    def dump_pages(self):
        for hit, page in zip(self.hits, self.pages):
            with open(hit.id + '.pdf', 'wb') as f:
                f.write(page)

    def _report(self):
        yield f'Job {self.id}'
        for hit in self.hits:
            for line in hit._report():
                yield indent(line)

    def __str__(self):
        return '\n'.join(self._report())


def get_all_hits(conn):
    page_size = 100
    search_rs = conn.search_hits(page_size=page_size)
    total_records = int(search_rs.TotalNumResults)

    def get_page_hits(page):
        search_rs = conn.search_hits(page_size=page_size, page_number=page)
        if not search_rs.status:
            raise Exception(
                f'Error performing search, code:{search_rs.Code}, '
                'message:{search_rs.Message}'
            )
        return search_rs

    def get_page_numbers(page_size, total_records):
        # TODO, is this zero-based or 1-based? If it's zero, based, change
        #  start to 0.
        limit = math.ceil(total_records / page_size)
        return itertools.islice(itertools.count(start=1), limit)

    hit_sets = map(get_page_hits, get_page_numbers(page_size, total_records))
    return list(itertools.chain.from_iterable(hit_sets))
