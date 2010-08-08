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

import cherrypy
from genshi.template import TemplateLoader, loader
from jaraco.util.string import local_format as lf

from .turk import ConversionJob, RetypePageHIT
from . import persistence

local_resource = functools.partial(pkg_resources.resource_stream, __name__)

class JobServer(list):
	tl = TemplateLoader([loader.package(__name__, 'view')])

	@cherrypy.expose
	def index(self):
		tmpl = self.tl.load('main.xhtml')
		message = 'Coming soon...'
		function_descr = namedtuple('function_descr', 'name href')
		functions = [
			function_descr('Submit Document(s)', 'submit_form'),
			function_descr('Check Document Status', 'check_status'),
			function_descr('Add Money to Balance', 'make_payment'),
			]
		return tmpl.generate(message=message, functions=functions).render('xhtml')

	@cherrypy.expose
	def test_upload(self):
		return dedent("""
			<form method='POST' enctype='multipart/form-data'
				action='upload'>
			File to upload: <input type="file" name="file"></input><br />
			<br />
			<input type="submit" value="Press"></input> to upload the file!
			</form>
			""").strip()

	@cherrypy.expose
	def upload(self, file):
		hostname = socket.getfqdn()
		port_number = cherrypy.server.socket_port
		server_url = lf('http://{hostname}:{port_number}/process')

		job = ConversionJob(
			file.file, str(file.content_type), server_url, file.filename,
			)
		job.run()
		self.append(job)
		nhits = len(job.hits)
		type_id = job.hits[0].registration_result[0].HITTypeId
		return lf(dedent("""
			<div>File was uploaded and created {nhits} hits.</div>
			<div><a target="_blank" href="https://workersandbox.mturk.com/mturk/preview?groupId={type_id}">Work this hit now</a></div>
			<div>When done, you should be able to <a target="_blank" href="get_results?job_id={job.id}">get the results from here</a>.</div>
			""").lstrip())

	@cherrypy.expose
	def process(self, hitId, assignmentId, workerId=None, turkSubmitTo=None, **kwargs):
		"""
		Fulfill a request of a client who's been sent from AMT. This
		will be rendered in an iFrame, so don't use the template.
		"""
		page_url = lf('/image/{hitId}')
		return lf(local_resource('view/retype page.xhtml').read())

	@cherrypy.expose
	def get_results(self, job_id):
		jobs = dict((job.id, job) for job in self)
		job = jobs[job_id]
		if not job.is_complete():
			return '<div>Job not complete</div>'
		return job.get_data()

	@cherrypy.expose
	def image(self, hitId):
		# find the appropriate image
		for job in self:
			for file, hit in zip(job.files, job.hits):
				if hit.matches(hitId):
					cherrypy.response.headers['Content-Type'] = 'application/pdf'
					return file
		return lf('<div>File not found for hitId {hitId}</div>')

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
			pages = len(job.files)
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
	def clean(self):
		for job in server:
			job.remove()

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
