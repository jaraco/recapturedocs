from recapturedocs import model
from recapturedocs import aws

class TestRetypePageHIT(object):
	@classmethod
	def setup_class(cls):
		aws.set_connection_environment()
		aws.ConnectionFactory.production = False

	def test_register(self):
		hit = model.RetypePageHIT('http://localhost/foo')
		hit.register()
		assert hasattr(hit, 'registration_result')
