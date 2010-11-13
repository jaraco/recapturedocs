from recapturedocs.turk import ConversionJob
import pickle

def test_persist_ConversionJob(sample_stream):
	job = ConversionJob(sample_stream, content_type='application/pdf', server_url=None)
	reconstituted = pickle.loads(pickle.dumps(job))
 