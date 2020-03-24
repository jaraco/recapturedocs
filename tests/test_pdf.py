import os

from recapturedocs.model import ConversionJob

here = os.path.dirname(__file__)


def test_split_pdf(sample_stream):
    ConversionJob.split_pdf(sample_stream)
