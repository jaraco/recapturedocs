from setuptools import setup, find_packages

name = 'recapturedocs'

setup(name = name,
		version = '1.0',
		description = 'Library for RecaptureDocs.com',
		author = 'Jason R. Coombs',
		author_email = 'jaraco@jaraco.com',
		url = 'http://www.recapturedocs.com/',
		packages = find_packages(exclude=['tests']),
		license = 'propriatary',
		classifiers = [
			"Development Status :: 4 - Beta",
			"Programming Language :: Python",
			"Programming Language :: Python :: 3",
		],
		entry_points = {
			'console_scripts': [
				'recapture-docs = recapturedocs.turk:handle_command_line',
				],
		},
		install_requires=[
			#'PyPDF >= 1.12',
		],
		extras_require = {
		},
		dependency_links = [
		],
		tests_require=[
		],
	)
