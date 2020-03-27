import pytest
import pkg_resources
import boto.mturk.connection

from recapturedocs import model
from recapturedocs import aws


pytestmark = pytest.mark.skip(reason="mechanical turk sandbox is gone")


class TestRetypePageHIT:
    @classmethod
    def setup_class(cls):
        aws.set_connection_environment()
        aws.ConnectionFactory.production = False

    def test_get_hit_type(self):
        model.RetypePageHIT.get_hit_type()

    def test_register(self):
        hit = model.RetypePageHIT('https://localhost/foo')
        hit.register()
        assert hasattr(hit, 'registration_result')
        assert len(hit.registration_result) == 1
        mturk_hit = hit.registration_result[0]
        assert isinstance(mturk_hit, boto.mturk.connection.HIT)
        assert mturk_hit.IsValid == 'True'
        assert len(mturk_hit.HITId) == 30
        assert mturk_hit.HITId == hit.id
        assert mturk_hit.HITTypeId == hit.get_hit_type()


class TestConversionJob:
    def test_load_pdf(self):
        lorem_ipsum = pkg_resources.resource_stream(
            'recapturedocs', 'static/Lorem ipsum.pdf'
        )
        job = model.ConversionJob(lorem_ipsum, 'application/pdf', 'http://localhost/')
        assert len(job.pages) == 4
