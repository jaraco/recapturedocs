import subprocess
import os
import sys

target = r'C:\Users\jaraco\Dropbox\public\cheeseshop'
proc = subprocess.Popen([
	sys.executable, 'setup.py', 'sdist',
	'--dist-dir', target,
	], stdout=subprocess.PIPE, stderr=open(os.path.devnull, 'w'))
stdout, stderr = proc.communicate()
subprocess.Popen(['dropbox-index', target]).wait()
