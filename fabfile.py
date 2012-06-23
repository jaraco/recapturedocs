"""
Routines for installing, staging, and serving recapturedocs on Ubuntu.

To install on a clean Ubuntu Precise box, simply run
fab bootstrap
"""

import socket
import urllib2

import keyring
from fabric.api import sudo, run, settings, task, env
from fabric.contrib import files
import yg.deploy.fabric.mongodb as mongodb
import yg.deploy.fabric.aptitude as aptitude
import yg.deploy.fabric.util as ygutil
from jaraco.util.string import local_format as lf

__all__ = ['install_env', 'update_staging',
	'update_production', 'setup_mongodb_firewall', 'mongodb_allow_ip',
	'install_supervisor', 'remove_all', 'bootstrap',
]

if not env.hosts:
	env.hosts = ['ichiro']

def create_user():
	"Create a user under which recapturedocs will run"
	#sudo('adduser --system --disabled-password --no-create-home recapturedocs')
	#sudo('mkdir -m 700 -p ~recapturedocs/.ssh')
	#files.append('~recapturedocs/.ssh/authorized_keys', [jaraco_pub], use_sudo=True)
	#sudo('chown -R recapturedocs:nogroup ~recapturedocs/.ssh')

@task
def bootstrap():
	install_env()
	update_production()

@task
def install_env():
	sudo('rm -R /opt/recapturedocs || echo -n')
	sudo('aptitude install -y python-setuptools')
	mongodb.distro_install()
	setup_mongodb_firewall()
	access_key = '0ZWJV1BMM1Q6GXJ9J2G2'
	secret_key = keyring.get_password('AWS', access_key)
	install_root = '/opt/recapturedocs'
	assert secret_key, "secret key is null"
	files.upload_template("ubuntu/recapture-docs.conf", "/etc/init",
		use_sudo=True, context=vars())

def enable_non_root_bind():
	sudo('aptitude install libcap2-bin')
	sudo('setcap "cap_net_bind_service=+ep" /recapturedocs/bin/python')

@task
def update_staging():
	run('envs/staging/bin/easy_install -U -f http://dl.dropbox.com/u/54081/cheeseshop/index.html recapturedocs')
	with settings(warn_only=True):
		run('pkill -f staging/bin/python')
		run('sleep 3')
	run('mkdir -p envs/staging/var/log')
	run('envs/staging/bin/recapture-docs daemon')

@task
def update_production(version=None):
	pkg_spec = 'recapturedocs'
	if version:
		pkg_spec += '==' + version
	sudo('mkdir -p /opt/recapturedocs/lib/python2.7/site-packages')
	with aptitude.package_context('python-dev'):
		with ygutil.shell_env(PYTHONUSERBASE='/opt/recapturedocs'):
			sudo('easy_install --user -U -f '
				'http://dl.dropbox.com/u/54081/cheeseshop/index.html {pkg_spec}'
				.format(**vars()))
	sudo('restart recapture-docs || start recapture-docs')

@task
def setup_mongodb_firewall():
	allowed_ips = ('127.0.0.1', '66.92.166.0/24',
		socket.gethostbyname('mongs.whit537.org'),
	)
	with settings(warn_only=True):
		sudo('iptables --new-chain mongodb')
		sudo('iptables -D INPUT -p tcp --dport 27017 -j mongodb')
		sudo('iptables -D INPUT -p tcp --dport 27018 -j mongodb')
	sudo('iptables -A INPUT -p tcp --dport 27017 -j mongodb')
	sudo('iptables -A INPUT -p tcp --dport 28017 -j mongodb')
	sudo('iptables --flush mongodb')
	sudo('iptables -A mongodb -j REJECT')
	map(mongodb_allow_ip, allowed_ips)

@task
def mongodb_allow_ip(ip=None):
	if ip is None:
		url = 'http://automation.whatismyip.com/n09230945.asp'
		resp = urllib2.urlopen(url)
		ip = resp.read()
	else:
		ip = socket.gethostbyname(ip)
	sudo(lf('iptables -I mongodb -s {ip} --jump RETURN'))

@task
def install_supervisor():
	sudo('easy_install-2.7 -U supervisor')

@task
def remove_all():
	sudo('stop recapture-docs || echo -n')
	sudo('rm /etc/init/recapture-docs.conf || echo -n')
	sudo('rm -Rf /opt/recapturedocs')
	# consider also removing MongoDB
