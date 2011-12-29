import socket

from fabric.api import sudo, run, settings, task, hosts, env
from fabric.contrib import files

from jaraco.util.string import local_format as lf
import yg.deploy.fabric.python

env.hosts = ['hideaki']

@task
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

@task
def install_env():
	sudo('virtualenv --no-site-packages /recapturedocs')
	# requires libcap2-bin
	#sudo('setcap "cap_net_bind_service=+ep" /recapturedocs/bin/python')

@task
def update_staging():
	run('envs/staging/bin/easy_install -U -f http://dl.dropbox.com/u/54081/cheeseshop/index.html recapturedocs')
	run('./stage-recapturedocs')

@task
def update_production():
	sudo('/recapturedocs/bin/easy_install -U -f http://dl.dropbox.com/u/54081/cheeseshop/index.html recapturedocs')
	sudo('restart recapture-docs')

@task
def setup_mongodb_firewall():
	allowed_ips = '127.0.0.1', '66.92.166.0/24'
	allowed_ips += (socket.gethostbyname('mongs.whit537.org'),)
	with settings(warn_only=True):
		sudo('iptables --new-chain mongodb')
		sudo('iptables -D INPUT -p tcp --dport 27017 -j mongodb')
		sudo('iptables -D INPUT -p tcp --dport 27018 -j mongodb')
	sudo('iptables -A INPUT -p tcp --dport 27017 -j mongodb')
	sudo('iptables -A INPUT -p tcp --dport 28017 -j mongodb')
	sudo('iptables --flush mongodb')
	for ip in allowed_ips:
		sudo(lf('iptables -A mongodb -s {ip} --jump RETURN'))
	sudo('iptables -A mongodb -j REJECT')
