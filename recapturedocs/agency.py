from __future__ import unicode_literals

import httpagentparser
import cherrypy

def detect_agent():
	ua = cherrypy.request.headers.get('User-Agent', '')
	cherrypy.request.user_agent = httpagentparser.detect(ua)
cherrypy.tools.agent_parser = cherrypy.Tool('on_start_resource', detect_agent)
