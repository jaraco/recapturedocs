import pkg_resources

def pytest_funcarg__sample_stream(request):
	req = pkg_resources.Requirement.parse('recapturedocs')
	return pkg_resources.resource_stream(req, 'tests/Lorem ipsum.pdf')
