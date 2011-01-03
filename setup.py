from setuptools import find_packages

name = 'recapturedocs'

setup_params = dict(
	name = name,
	use_hg_version=True,
	description = 'Library for RecaptureDocs.com',
	author = 'Jason R. Coombs',
	author_email = 'jaraco@jaraco.com',
	url = 'http://www.recapturedocs.com/',
	packages = find_packages(),
	include_package_data=True,
	license = 'proprietary',
	classifiers = [
		"Development Status :: 4 - Beta",
		"Programming Language :: Python",
		"Programming Language :: Python :: 3",
	],
	entry_points = {
		'console_scripts': [
			'recapture-docs = recapturedocs.server:handle_command_line',
			],
	},
	install_requires=[
		'cherrypy==3.2.0rc1',
		# install with easy_install http://svn.cherrypy.org/trunk/
		'genshi',
		'boto == 2.0b3', # easy_install http://github.com/jaraco/boto/tarball/master
		'PyPDF >= 1.12',
		'keyring',
		'jaraco.util',
		'path.py',
		'docutils',
	],
	extras_require = {
	},
	dependency_links = [
	],
	tests_require=[
		'py >= 1.3.2',
	],
	test_suite='py.test',
	setup_requires=[
		'hgtools',
	],
)

if __name__ == '__main__':
	from setuptools import setup
	setup(**setup_params)
