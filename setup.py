#!/usr/bin/env python

# Project skeleton maintained at https://github.com/jaraco/skeleton

import io
import sys

import setuptools

with io.open('README.rst', encoding='utf-8') as readme:
	long_description = readme.read()

needs_wheel = {'release', 'bdist_wheel', 'dists'}.intersection(sys.argv)
wheel = ['wheel'] if needs_wheel else []

name = 'recapturedocs'
description = 'Library for RecaptureDocs.com'

setup_params = dict(
	name=name,
	use_scm_version=True,
	author="Jason R. Coombs",
	author_email="jaraco@jaraco.com",
	description=description or name,
	long_description=long_description,
	url="https://github.com/jaraco/" + name,
	packages=setuptools.find_packages(),
	include_package_data=True,
	namespace_packages=name.split('.')[:-1],
	install_requires=[
		'cherrypy >= 3.2.3',
		'genshi >= 0.6',
		'boto >= 2.4',
		'PyPDF2',
		'keyring >= 0.7.1',
		'path.py',
		'docutils',
		'jaraco.modb >= 3.2',
		'pymongo >= 1.9',
		'httpagentparser >= 1.0.1',
		'dropbox >= 1.5',
		'newrelic',
		'six',
		'jaraco.text',
		'jaraco.itertools',
		'jaraco.logging',
		'jaraco.collections',
		'jaraco.classes',
		'jaraco.functools>=1.2',
		'jaraco.email',
		'jaraco.mongodb',
	],
	extras_require={
	},
	setup_requires=[
		'setuptools_scm>=1.15.0',
	] + wheel,
	classifiers=[
		"Development Status :: 5 - Production/Stable",
		"Intended Audience :: Developers",
		"License :: Other/Proprietary License",
		"Programming Language :: Python :: 2.7",
		"Programming Language :: Python :: 3",
	],
	entry_points={
		'console_scripts': [
			'recapture-docs = recapturedocs.server:handle_command_line',
		],
	},
)
if __name__ == '__main__':
	setuptools.setup(**setup_params)
