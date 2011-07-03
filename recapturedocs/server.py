from __future__ import absolute_import

import os
import sys
import functools
import itertools
import argparse
from collections import namedtuple
from contextlib import contextmanager
import pkg_resources
from textwrap import dedent
import socket
import urlparse
import inspect
import docutils.io, docutils.core
import logging

import cherrypy
from genshi.template import TemplateLoader, loader
import genshi
from jaraco.util.string import local_format as lf
from jaraco.util.meta import LeafClassesMeta
import jaraco.util.logging
import boto

from . import model
from . import persistence
from . import aws
from . import config

class JobServer(object):
	"""
	The job server is both a CherryPy server and a list of jobs
	"""
	tl = TemplateLoader([loader.package(__name__, 'view')])

	@cherrypy.expose
	def index(self):
		tmpl = self.tl.load('main.xhtml')
		message = "Welcome to RecaptureDocs"
		return tmpl.generate(
			message=message,
			page_cost=model.ConversionJob.page_cost,
			).render('xhtml')

	@staticmethod
	def construct_url(path):
		return urlparse.urljoin(cherrypy.request.base, path)

	@staticmethod
	def is_production():
		return cherrypy.config.get('server.production', False)

	@cherrypy.expose
	def upload(self, file):
		server_url = self.construct_url('/process')
		if not unicode(file.content_type) == 'application/pdf':
			msg = "Got content other than PDF: {content_type}"
			cherrypy.log(msg.format(**vars(file)), severity=logging.WARNING)
		job = model.ConversionJob(
			file.file, unicode(file.content_type), server_url, file.filename,
		)
		job.save_if_new()
		raise cherrypy.HTTPRedirect(lf("status/{job.id}"))

	@cherrypy.expose
	def status(self, job_id):
		tmpl = self.tl.load('status.xhtml')
		job = self._get_job_for_id(job_id)
		return tmpl.generate(job=job, production=self.is_production()
			).render('xhtml')

	@cherrypy.expose
	def initiate_payment(self, job_id):
		conn = aws.ConnectionFactory.get_fps_connection()
		job = self._get_job_for_id(job_id)
		job.caller_token = conn.install_caller_instruction()
		job.recipient_token = conn.install_recipient_instruction()
		job.save()
		raise cherrypy.HTTPRedirect(
			self.construct_payment_url(job, conn, job.recipient_token)
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
			transactionAmount = str(float(job.cost)),
			recipientToken = recipient_token,
			)
		url = conn.make_url(**params)
		return url

	@cherrypy.expose
	def complete_payment(self, job_id, status, tokenID=None, **params):
		job = self._get_job_for_id(job_id)
		if not status == 'SC':
			tmpl = self.tl.load('declined.xhtml')
			params = genshi.Markup(lf('<!-- {params} -->'))
			res = tmpl.generate(status=status, job=job, params=params)
			return res.render('xhtml')
		end_point_url = JobServer.construct_url(lf('/complete_payment/{job_id}'))
		self.verify_URL_signature(end_point_url, params)
		job.sender_token = tokenID
		conn = aws.ConnectionFactory.get_fps_connection()
		conn.pay(float(job.cost), job.sender_token, job.recipient_token,
			job.caller_token)
		job.authorized = True
		job.register_hits()
		job.save()
		raise cherrypy.HTTPRedirect(lf('/status/{job_id}'))

	def verify_URL_signature(self, end_point_url, params):
		assert params['signatureVersion'] == '2'
		assert params['signatureMethod'] == 'RSA-SHA1'
		#key = self.get_key_from_cert(params['certificateURL'])
		# http://laughingmeme.org/2008/12/30/new-amazon-aws-signature-version-2-is-oauth-compatible/
		# http://github.com/simplegeo/python-oauth2
		# http://lists.dlitz.net/pipermail/pycrypto/2009q3/000112.html

		conn = aws.ConnectionFactory.get_fps_connection()
		conn.verify_signature(end_point_url, cherrypy.request.query_string)

	@cherrypy.expose
	def process(self, hitId, assignmentId, workerId=None, turkSubmitTo=None, **kwargs):
		"""
		Fulfill a request of a client who's been sent from AMT. This
		will be rendered in an iFrame, so don't use the template.
		"""
		# rename a few variables to use the PEP-8 syntax
		assignment_id = assignmentId
		hit_id = hitId
		worker_id = workerId
		turk_submit_to = turkSubmitTo
		preview = assignment_id == 'ASSIGNMENT_ID_NOT_AVAILABLE'
		page_url = lf('/image/{hit_id}') if not preview else '/static/Lorem ipsum.pdf'
		tmpl = self.tl.load('retype page.xhtml')
		params = dict(vars())
		del params['self']
		return tmpl.generate(**params).render('xhtml')

	def _get_job_for_id(self, job_id):
		return model.ConversionJob.load(job_id)

	@cherrypy.expose
	def get_results(self, job_id):
		job = self._get_job_for_id(job_id)
		if not job.is_complete():
			return '<div>Job not complete</div>'
		cherrypy.response.headers['Content-Type'] = 'text/plain'
		return job.get_data()

	@cherrypy.expose
	def image(self, hit_id):
		# find the appropriate image
		job = model.ConversionJob.for_hitid(hit_id)
		if not job: raise cherrypy.NotFound
		cherrypy.response.headers['Content-Type'] = job.content_type
		return job.page_for_hit(hit_id)

	@cherrypy.expose
	def design(self):
		return self.tl.load('design goals.xhtml').generate().render('xhtml')

	@cherrypy.expose
	def text(self, name):
		path = 'text/' + name + '.rst'
		rst = pkg_resources.resource_stream('recapturedocs', path)
		icls = docutils.io.FileInput
		parts = docutils.core.publish_parts(source=rst,
			source_class=docutils.io.FileInput, writer_name='html',)
		html = genshi.HTML(parts['html_body'])
		return self.tl.load('simple.xhtml').generate(content=html).render('xhtml')

	def __iter__(self):
		return model.ConversionJob.load_all()

	def __delitem__(self, key):
		jobs = list(iter(self))
		for job in jobs[key]:
			job.remove()

class Devel(object):
	tl = TemplateLoader([
		loader.package(__name__, 'view/devel'),
		loader.package(__name__, 'view'),
		])
	def __init__(self, server):
		self.server = server

	@cherrypy.expose
	def status(self):
		tmpl = self.tl.load('status.xhtml')
		return tmpl.generate(jobs=list(self.server)).render('xhtml')

	@cherrypy.expose
	def disable_all(self):
		"""
		Disable of all recapture-docs hits (even those not recognized by this
		server).
		"""
		disabled = model.RetypePageHIT.disable_all()
		del server[:]
		msg = 'Disabled {disabled} HITs (do not forget to remove them from other servers).'
		return lf(msg)

	@cherrypy.expose
	def pay(self, job_id):
		"""
		Force payment for a given job.
		"""
		job = self.server._get_job_for_id(job_id)
		job.authorized = True
		job.register_hits()
		return lf('<a href="/status/{job_id}">Payment simulated; click here for status.</a>')

@contextmanager
def start_server(configs):
	"""
	The main entry point for the service, regardless of how it's used.
	Takes any number of filename or dictionary objects suitable for
	cherrypy.config.update.
	"""
	global server
	server = JobServer()
	if hasattr(cherrypy.engine, "signal_handler"):
		cherrypy.engine.signal_handler.subscribe()
	if hasattr(cherrypy.engine, "console_control_handler"):
		cherrypy.engine.console_control_handler.subscribe()
	app = cherrypy.tree.mount(server, '/')
	map(app.merge, configs)
	if not cherrypy.config.get('server.production', False):
		dev_app = cherrypy.tree.mount(Devel(server), '/devel')
		map(dev_app.merge, configs)
		boto.set_stream_logger('recapturedocs')
		aws.ConnectionFactory.production=False
	cherrypy.engine.start()
	yield server
	cherrypy.engine.exit()

class Command(object):
	__metaclass__ = LeafClassesMeta
	def __init__(self, *configs):
		self.configs = configs
		self.configure()

	def configure(self):
		"""
		Initialize the cherrypy context and other configuration options
		based on the cherrypy config items supplied.
		"""
		# set the socket host, but let other configs override
		host_config = {
			'global': {
				'server.socket_host': '::0',
				'log.screen': False,
			}
		}
		static_dir = pkg_resources.resource_filename('recapturedocs', 'static')
		static_config = {'/static':
			{
				'tools.staticdir.on': True,
				'tools.staticdir.dir': static_dir,
			},
		}
		self.configs = list(
			itertools.chain([host_config, static_config], self.configs))
		map(cherrypy.config.update, self.configs)
		persistence.init()

	@classmethod
	def add_subparsers(cls, parser):
		subparsers = parser.add_subparsers()
		[cmd_class.add_parser(subparsers) for cmd_class in cls._leaf_classes]

	@classmethod
	def add_parser(cls, subparsers):
		parser = subparsers.add_parser(cls.__name__.lower())
		parser.set_defaults(action=cls)
		parser.add_argument('-C', '--package-config', dest="package_configs",
			default=[], action="append",
			help="Add config recipe as found in the package (e.g. prod)",)
		parser.add_argument('configs', nargs='*', default=[],
			help='Config filename')

class Serve(Command):
	def run(self):
		with start_server(self.configs):
			cherrypy.engine.block()
		raise SystemExit(0)

class Interact(Command):
	def configure(self):
		# change some config that's problemmatic in interactive mode
		config = {
			'global':
				{
				'autoreload.on': False,
				'log.screen': False,
				},
			}
		self.configs = list(itertools.chain([config], self.configs))
		super(Interact, self).configure()

	def run(self):
		with start_server(self.configs):
			import code; code.interact(local=globals())

class Daemon(Command):
	def run(self):
		from cherrypy.process.plugins import Daemonizer
		d = Daemonizer(cherrypy.engine, stdout=config.get_log_file(),
			stderr=config.get_error_file())
		d.subscribe()
		with start_server(self.configs):
			cherrypy.engine.block()

def get_package_configs(args):
	names = [
		name if name.endswith('.conf') else name + '.conf'
		for name in args.package_configs
	]
	pkg_res = functools.partial(pkg_resources.resource_filename, 'recapturedocs')
	return map(pkg_res, names)

def handle_command_line():
	usage = inspect.getdoc(handle_command_line)
	parser = argparse.ArgumentParser()
	jaraco.util.logging.add_arguments(parser)
	Command.add_subparsers(parser)
	args = parser.parse_args()
	jaraco.util.logging.setup(args)
	user_configs = args.configs + get_package_configs(args)
	command = args.action(*user_configs)
	command.run()

if __name__ == '__main__':
	handle_command_line()
