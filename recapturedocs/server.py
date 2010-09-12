from __future__ import absolute_import

import os
import sys
import optparse
import functools
import itertools
from collections import namedtuple
from contextlib import contextmanager
import pkg_resources
from textwrap import dedent
import socket
import urlparse

import cherrypy
from genshi.template import TemplateLoader, loader
from jaraco.util.string import local_format as lf

from .turk import ConversionJob, RetypePageHIT, set_connection_environment
from . import persistence

local_resource = functools.partial(pkg_resources.resource_stream, __name__)

class JobServer(list):
	tl = TemplateLoader([loader.package(__name__, 'view')])

	@cherrypy.expose
	def index(self):
		tmpl = self.tl.load('main.xhtml')
		message = 'Welcome to RecaptureDocs'
		return tmpl.generate(message=message).render('xhtml')

	@staticmethod
	def construct_url(path):
		return urlparse.urljoin(cherrypy.request.base, path)

	@cherrypy.expose
	def upload(self, file):
		server_url = self.construct_url('/process')
		job = ConversionJob(
			file.file, str(file.content_type), server_url, file.filename,
			)
		self.append(job)
		persistence.save('server', self)
		raise cherrypy.HTTPRedirect(lf("status/{job.id}"))

	@cherrypy.expose
	def status(self, job_id):
		job = self._get_job_for_id(job_id)
		n_pages = len(job)
		fmt = lambda s: lf(dedent(s.lstrip()))
		yield lf(dedent("""
			<div>Recapture job was created {n_pages} pages.</div>
			""".lstrip()))
		if not job.authorized:
			msg = """
				<div>This job will cost {job.cost} to complete. <a href="/initiate_payment/{job.id}">Click here</a> to pay to pay for the job.</div>
				"""
			yield lf(dedent(msg.lstrip()))
			return
		# for development purposes
		type_id = job.hits[0].registration_result[0].HITTypeId
		yield lf(dedent("""
			<div>Workers can <a target="_blank" href="https://workersandbox.mturk.com/mturk/preview?groupId={type_id}">complete the hits here</a>.</div>
			""".lstrip()))
		if not job.is_complete():
			msg = """
			<div>Your job is authorized and being processed. Please, check back later.</div>
			"""
		else:
			msg = """
			<div>Your job is complete. You may now <a target="_blank" href="/get_results?job_id={job.id}">get the results from here</a>.</div>
			"""
		yield lf(dedent(msg.lstrip()))

	@cherrypy.expose
	def pay(self, job_id):
		job = self._get_job_for_id(job_id)
		# stubbed - jobs are automatically authorized
		job.authorized = True
		job.register_hits()
		return lf('<a href="/status/{job_id}">Payment simulated; click here to continue.</a>')

	@cherrypy.expose
	def initiate_payment(self, job_id):
		from boto.fps.connection import FPSConnection
		set_connection_environment()
		conn = FPSConnection()
		caller_token = conn.install_caller_instruction()
		recipient_token = conn.install_recipient_instruction()
		job = self._get_job_for_id(job_id)
		raise cherrypy.HTTPRedirect(
			self.construct_payment_url(job, conn, recipient_token)
			)

	@staticmethod
	def construct_payment_url(job, conn, recipient_token):
		n_pages = len(job)
		params = dict(
			callerKey = os.environ['AWS_ACCESS_KEY_ID'], # My access key
			pipelineName = 'SingleUse',
			returnURL = JobServer.construct_url(lf('/complete_payment/{job.id}')),
			callerReference = job.id,
			paymentReason = lf('RecaptureDocs conversion - {n_pages} pages'),
			transactionAmount = float(job.cost),
			recipientToken = recipient_token,
			)
		url = conn.make_url(**params)
		return url
		
	@cherrypy.expose
	def complete_payment(self, job_id, status, **params):
		if not status == 'SC':
			return lf('<div>payment was declined with status {status}. <a href="/initiate_payment/{job_id}>Click here</a> to try again.</div><div>{params}</div>')
		self.verify_URL_signature(params)
		job = self._get_job_for_id(job_id)
		job.authorized = True
		job.register_hits()
		raise cherrypy.HTTPRedirect(lf('/status/{job_id}'))

	def verify_URL_signature(self, params):
		pass

	@cherrypy.expose
	def process(self, hitId, assignmentId, workerId=None, turkSubmitTo=None, **kwargs):
		"""
		Fulfill a request of a client who's been sent from AMT. This
		will be rendered in an iFrame, so don't use the template.
		"""
		page_url = lf('/image/{hitId}')
		return lf(local_resource('view/retype page.xhtml').read())

	def _get_job_for_id(self, job_id):
		jobs = dict((job.id, job) for job in self)
		return jobs[job_id]

	@cherrypy.expose
	def get_results(self, job_id):
		job = self._get_job_for_id(job_id)
		if not job.is_complete():
			return '<div>Job not complete</div>'
		return job.get_data()

	def _jobs_by_hit_id(self):
		def _hits_for(job):
			hits = getattr(job, 'hits', [])
			return ((hit.id, job) for hit in hits)
		job_hits = itertools.imap(_hits_for, self)
		items = itertools.chain.from_iterable(job_hits)
		#items = list(items); print items
		return dict(items)

	@cherrypy.expose
	def image(self, hit_id):
		# find the appropriate image
		job = self._jobs_by_hit_id()[hit_id]
		if not job: raise cherrypy.NotFound
		cherrypy.response.headers['Content-Type'] = job.content_type
		return job.page_for_hit(hit_id)

	def __getstate__(self):
		return list(self)

	def __setstate__(self, items):
		self[:] = items

class Devel(object):
	def __init__(self, server):
		self.server = server

	@cherrypy.expose
	def status(self):
		yield '<div>'
		for job in self.server:
			yield '<div>'
			filename = job.filename
			pages = len(job)
			yield '<div>Job Filename: {filename} ({pages} pages)'.format(**vars())
			yield '<div style="margin-left:1em;">Hits'
			for hit in job.hits:
				yield '<div>'
				yield hit.id
				yield '</div>'
			yield '</div>'
			yield '</div>'
		yield '</div>'

	@cherrypy.expose
	def disable_all(self):
		"""
		Disable of all recapture-docs hits (even those not recognized by this
		server).
		"""
		disabled = RetypePageHIT.disable_all()
		del server[:]
		msg = 'Disabled {disabled} HITs (do not forget to remove them from other servers).'
		return msg.format(**vars())

@contextmanager
def start_server(*configs):
	global cherrypy, server
	import cherrypy
	persistence.init()
	# set the socket host, but let other configs override
	host_config = {'global':{'server.socket_host': '::0'}}
	configs = list(itertools.chain([host_config],configs))
	map(cherrypy.config.update, configs)
	server = persistence.load('server') or JobServer()
	if hasattr(cherrypy.engine, "signal_handler"):
		cherrypy.engine.signal_handler.subscribe()
	if hasattr(cherrypy.engine, "console_control_handler"):
		cherrypy.engine.console_control_handler.subscribe()
	app = cherrypy.tree.mount(server, '/')
	map(app.merge, configs)
	if not cherrypy.config.get('server.production', False):
		dev_app = cherrypy.tree.mount(Devel(server), '/devel')
		map(dev_app.merge, configs)
	cherrypy.engine.start()
	yield server
	cherrypy.engine.exit()
	persistence.save('server', server)

def serve(*configs):
	with start_server(*configs):
		cherrypy.engine.block()
	raise SystemExit(0)

def interact(*configs):
	# change some config that's problemmatic in interactive mode
	config = {
		'global':
			{
			'autoreload.on': False,
			'log.screen': False,
			}
		}
	with start_server(config, *configs):
		import code; code.interact(local=globals())

def get_log_directory(appname):
	candidate = os.path.join(sys.prefix, 'var')
	if os.path.isdir(candidate):
		return candidate
	def ensure_exists(func):
		@functools.wraps(func)
		def make_if_not_present():
			dir = func()
			if not os.path.isdir(dir):
				os.makedirs(dir)
			return dir
		return make_if_not_present
	@ensure_exists
	def get_log_root_win32():
		return os.path.join(os.environ['SYSTEMROOT'], 'System32', 'LogFiles', appname)
	@ensure_exists
	def get_log_root_linux2():
		return '/var/' + appname.lower()
	getter = locals()['get_log_root_'+sys.platform]
	return getter()

def daemon(*configs):
	from cherrypy.process.plugins import Daemonizer
	appname = 'RecaptureDocs'
	log = os.path.join(get_log_directory(appname), 'log.txt')
	error = os.path.join(get_log_directory(appname), 'error.txt')
	d = Daemonizer(cherrypy.engine, stdout=log, stderr=error)
	d.subscribe()
	with start_server(*configs):
		cherrypy.engine.block()
	
def handle_command_line():
	parser = optparse.OptionParser()
	options, args = parser.parse_args()
	cmd = args.pop(0)
	configs = args
	if cmd in globals():
		globals()[cmd](*configs)

if __name__ == '__main__':
	handle_command_line()
