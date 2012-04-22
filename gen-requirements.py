import os
import subprocess
import platform
import shutil

is_windows = platform.system() == 'Windows'
env_base = 'env/Scripts' if is_windows else 'env/bin'

def make_env():
	"""
	Make a clean environment for building requirements.txt
	"""
	if os.path.exists('env'):
		raise RuntimeError("env already exists")
	subprocess.check_call([
		'virtualenv', '--distribute', 'env',
	])

def install_project():
	ei_cmd = os.path.join(env_base, 'easy_install')
	subprocess.check_call([
		ei_cmd,
		'-f', 'http://dl.dropbox.com/u/54081/cheeseshop/index.html',
		'recapturedocs>=0',
	])

def invoke_pip():
	with open('requirements.txt', 'wb') as req_file:
		req_file.write(
			'-f http://dl.dropbox.com/u/54081/cheeseshop/index.html\n'
		)
		subprocess.check_call([
			os.path.join(env_base, 'pip'),
			'freeze'
		], stdout=req_file)


def generate_requirements():
	make_env()
	try:
		install_project()
		invoke_pip()
	finally:
		if platform.system() == 'Windows':
			# shutil will traverse symlinks (such as env/Lib/encodings
			#  and env/include), deleting the files in the main Python
			#  installation, so use another technique.
			subprocess.check_call('cmd /c rmdir /s /q env')
		else:
			shutil.rmtree('env')

if __name__ == '__main__':
	generate_requirements()
