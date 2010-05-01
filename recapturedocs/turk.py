from __future__ import print_function
import os
import sys
import subprocess
import socket
from glob import glob
from optparse import OptionParser
from jaraco.filesystem import insert_before_extension
from jaraco.util.string import local_format as lf

def make_turk_recognition_job_from_pdf():
	options, args = OptionParser().parse_args()
	infile = args.pop()

	dest = '/inetpub/wwwroot/pages'
	if not os.path.isdir(dest):
		os.makedirs(dest)

	name = os.path.basename(infile)
	page_fmt = insert_before_extension(name, '-%002d')
	dest_name = os.path.join(dest, page_fmt)

	cmd = ['pdftk', infile, 'burst', 'output', dest_name]
	res = subprocess.Popen(cmd).wait()
	if res != 0:
		print("failed", file=sys.stderr)
		raise SystemExit(res)

	os.remove(os.path.join(dest, 'doc_data.txt'))
	files = glob(os.path.join(dest, insert_before_extension(name, '*')))
	files = map(os.path.basename, files)
	job = open(os.path.join(dest, 'job.txt'), 'w')
	print("PAGE_URL", file=job)
	for file in files:
		hostname = socket.getfqdn()
		print(lf('http://{hostname}/pages/{file}'), file=job)

if __name__ == '__main__':
	make_turk_recognition_job_from_pdf()
