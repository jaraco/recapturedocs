import os

from recapturedocs.turk import ConversionJob

here = os.path.dirname(__file__)

def test_split_pdf(sample_stream):
	files = ConversionJob.split_pdf(sample_stream, 'sample.pdf')