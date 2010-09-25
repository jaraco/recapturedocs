import pkg_resources

def pytest_funcarg__sample_stream(request):
	return pkg_resources.resource_stream('recapturedocs', 'static/Lorem ipsum.pdf')
