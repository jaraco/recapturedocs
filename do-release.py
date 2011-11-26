import subprocess
import os
import sys

import pkg_resources

pkg_resources.require('dropbox-index>=0.4.3')
import dropbox_index

target = r'C:\Users\jaraco\Dropbox\public\cheeseshop'
proc = subprocess.Popen([
	sys.executable, 'setup.py', 'sdist',
	'--dist-dir', target,
	], stdout=subprocess.PIPE, stderr=open(os.path.devnull, 'w'))
stdout, stderr = proc.communicate()
dropbox_index.crawl(target)
