import os
import sys
import optparse
import functools
import itertools
from contextlib import contextmanager
import pkg_resources
from textwrap import dedent
import socket

import cherrypy
from genshi.template import TemplateLoader, loader
from jaraco.util.string import local_format as lf

from turk import ConversionJob

local_resource = functools.partial(pkg_resources.resource_stream, __name__)

class JobServer(list):
	tl = TemplateLoader([loader.package(__name__, 'view')])

	def index(self):
		tmpl = self.tl.load('main.xhtml')
		return tmpl.generate(message='Coming soon...').render('xhtml')
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
	upload.exposed = True

	def process(self, hitId, assignmentId, workerId=None, turkSubmitTo=None, **kwargs):
		"""
		Fulfill a request of a client who's been sent from AMT. This
		will be rendered in an iFrame, so don't use the template.
		"""
		page_url = lf('/image/{hitId}')
		return lf(local_resource('view/retype page.xhtml').read())
	process.exposed = True

	def get_results(self, job_id):
		jobs = dict((job.id, job) for job in self)
		job = jobs[job_id]
		if not job.is_complete():
			return '<div>Job not complete</div>'
		return job.get_data()
	get_results.exposed = True

	def image(self, hitId):
		# find the appropriate image
		for job in self:
			for file, hit in zip(job.files, job.hits):
				if hit.matches(hitId):
					cherrypy.response.headers['Content-Type'] = 'application/pdf'
					return file
		return lf('<div>File not found for hitId {hitId}</div>')
	image.exposed = True

@contextmanager
def start_server(*configs):
	global cherrypy, server
	import cherrypy
	# set the socket host, but let other configs override
	host_config = {'server.socket_host': '::0'}
	configs = itertools.chain([host_config],configs)
	map(cherrypy.config.update, configs)
	server = JobServer()
	if hasattr(cherrypy.engine, "signal_handler"):
		cherrypy.engine.signal_handler.subscribe()
	if hasattr(cherrypy.engine, "console_control_handler"):
		cherrypy.engine.console_control_handler.subscribe()
	app = cherrypy.tree.mount(server, '/')
	map(app.merge, configs)
	cherrypy.engine.start()
	yield server
	cherrypy.engine.exit()

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
