from recapturedocs.turk import ConversionJob
import pickle

def test_persist_ConversionJob(sample_stream):
	job = ConversionJob(sample_stream, content_type='application/pdf', server_url=None)
	# a job cannot be pickled before the PDF has been processed
	job.do_split_pdf()
	reconstituted = pickle.loads(pickle.dumps(job))
 