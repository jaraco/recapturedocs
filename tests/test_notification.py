import six

import mock
from jaraco.itertools import first

from recapturedocs import server

class TestNotification(object):
	@classmethod
	def setup_class(cls):
		cls.server = server.JobServer()
		cls.server._app = mock.Mock(
			config = dict(
				notification=dict(
					smtp_to='test@example.com',
					smtp_host='smtp.example.com',
			)	)
		)

	@mock.patch('smtplib.SMTP')
	def test_send_notice(self, smtp_class):
		self.server.send_notice('test send message')
		smtp_ob = smtp_class.return_value
		name, args, kwargs = first(smtp_ob.method_calls)
		assert name == 'sendmail'
		assert 'test send message' in six.text_type(args)
		assert isinstance(args[1][0], six.string_types)
