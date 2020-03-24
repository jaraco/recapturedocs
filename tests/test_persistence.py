from recapturedocs.model import ConversionJob
import pickle


def test_persist_ConversionJob(sample_stream):
    job = ConversionJob(sample_stream, content_type='application/pdf', server_url=None)
    pickle.loads(pickle.dumps(job))


def test_same_job_matches(sample_stream):
    params = dict(stream=sample_stream, content_type='application/pdf', server_url=None)
    job1 = ConversionJob(**params)
    sample_stream.seek(0)
    job2 = ConversionJob(**params)
    assert job1.matches(job2)
