from fabric.operations import sudo, run
from fabric.contrib import files

import yg.deploy.fabric.python

def install_ppa_python():
	yg.deploy.fabric.python.install_ppa_python()
	sudo('aptitude install python2.7-dev')
	sudo('aptitude install python-distribute-deadsnakes')
	sudo('/usr/bin/easy_install-2.7 virtualenv')

def create_user():
	"Create a user under which recapturedocs will run"
	#sudo('adduser --system --disabled-password --no-create-home recapturedocs')
	#sudo('mkdir -m 700 -p ~recapturedocs/.ssh')
	#files.append('~recapturedocs/.ssh/authorized_keys', [jaraco_pub], use_sudo=True)
	#sudo('chown -R recapturedocs:nogroup ~recapturedocs/.ssh')

def install_env():
	sudo('virtualenv --no-site-packages /recapturedocs')
	# requires libcap2-bin
	#sudo('setcap "cap_net_bind_service=+ep" /recapturedocs/bin/python')

def update_staging():
	run('envs/staging/bin/easy_install -U -f http://dl.dropbox.com/u/54081/cheeseshop/index.html recapturedocs')
	run('./stage-recapturedocs')

def update_production():
	sudo('/recapturedocs/bin/easy_install -U -f http://dl.dropbox.com/u/54081/cheeseshop/index.html recapturedocs')
	sudo('restart recapture-docs')
