import re
import subprocess
import os

from jaraco.windows import clipboard
from jaraco.util.string import local_format as lf

proc = subprocess.Popen([
	'python', 'setup.py', 'sdist',
	'--dist-dir', r'C:\Users\jaraco\Dropbox\public\cheeseshop',
	], stdout=subprocess.PIPE, stderr=open(os.path.devnull, 'w'))
stdout, stderr = proc.communicate()
pattern = re.compile("creating '(?P<filename>.*)' and adding .* to it")
filepath = next(pattern.finditer(stdout)).group('filename')
filename = os.path.basename(filepath)
clipboard.set_text(lf('http://dl.dropbox.com/u/54081/cheeseshop/{filename}'))
