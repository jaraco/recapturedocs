import cherrypy
import pytest
import pkg_resources

import recapturedocs.server
from recapturedocs import model
from recapturedocs import aws

class TestServer(recapturedocs.server.JobServer):
	def _get_job_for_id(self, id):
		assert id == 'test'
		lorem_ipsum = pkg_resources.resource_stream('recapturedocs',
			'static/Lorem Ipsum.pdf')
		job = model.ConversionJob(lorem_ipsum, 'application/pdf',
			'http://localhost/')
		return job

class TestPayments(object):
	@classmethod
	def setup_class(cls):
		aws.ConnectionFactory.production = False
		aws.set_connection_environment()
		cls.server = TestServer()

	def test_setup_payment(self):
		with pytest.raises(cherrypy.HTTPRedirect) as exc:
			self.server.initiate_payment('test')
