import httpagentparser
import cherrypy


class AgentHelper(dict):
    def IE_lt(self, ver):
        """
        Is the User Agent IE and earlier than the version specified?
        """
        return (
            'browser' in self
            and self['browser']['name'] == 'Microsoft Internet Explorer'
            and self['browser']['version'] < ver
        )


def detect_agent():
    ua = cherrypy.request.headers.get('User-Agent', '')
    cherrypy.request.user_agent = AgentHelper(httpagentparser.detect(ua))


cherrypy.tools.agent_parser = cherrypy.Tool('on_start_resource', detect_agent)
