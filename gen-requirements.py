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
	python = os.path.join(env_base, 'python')
	subprocess.check_call([
		python,
		'setup.py',
		'install',
	])

def invoke_pip():
	with open('requirements.txt', 'wb') as req_file:
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
		shutil.rmtree('env')

if __name__ == '__main__':
	generate_requirements()
