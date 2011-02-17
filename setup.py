import sys
from setuptools import find_packages

name = 'recapturedocs'

def py_ver_dependencies():
	if sys.version_info < (2,7):
		yield 'argparse'

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
		'boto == 2.0b4', # easy_install http://github.com/jaraco/boto/tarball/master
		'PyPDF >= 1.12',
		'keyring',
		'jaraco.util',
		'path.py',
		'docutils',
	] + list(py_ver_dependencies()),
	extras_require = {
	},
	dependency_links = [
	],
	tests_require=[
		'pytest',
	],
	test_suite='py.test',
	setup_requires=[
		'hgtools',
	],
)

if __name__ == '__main__':
	from setuptools import setup
	setup(**setup_params)
