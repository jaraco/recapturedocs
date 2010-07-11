import os

from recapturedocs.turk import ConversionJob

here = os.path.dirname(__file__)

def pytest_funcarg__sample_stream(request):
	return open(os.path.join(here, 'sample.pdf'), 'rb')

def test_split_pdf(sample_stream):
	files = ConversionJob.split_pdf(sample_stream, 'sample.pdf')