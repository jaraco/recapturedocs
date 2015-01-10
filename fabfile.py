"""
Routines for installing, staging, and serving recapturedocs on Ubuntu.

To install on a clean Ubuntu Trusty box, simply run
fab bootstrap
"""

import socket
import urllib2

import six
import keyring
from fabric.api import sudo, run, settings, task, env
from fabric.contrib import files
from jaraco.fabric import mongodb
from jaraco.fabric import apt
from jaraco.fabric import context
from jaraco.util.string import local_format as lf

__all__ = [
	'install_env', 'update_staging', 'install_upstart_conf',
	'update_production', 'setup_mongodb_firewall', 'mongodb_allow_ip',
	'install_supervisor', 'remove_all', 'bootstrap', 'configure_nginx',
]

if not env.hosts:
	env.hosts = ['elektra']

install_root = '/opt/recapturedocs'

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
	sudo('rm -R {install_root} || echo -n'.format(**globals()))
	sudo('aptitude install -y python-setuptools')
	sudo('aptitude build-dep -y python-lxml')
	mongodb.distro_install()
	setup_mongodb_firewall()
	install_upstart_conf()

@task
def install_upstart_conf(install_root=install_root):
	aws_access_key = '0ZWJV1BMM1Q6GXJ9J2G2'
	aws_secret_key = keyring.get_password('AWS', aws_access_key)
	assert aws_secret_key, "AWS secret key is null"
	dropbox_access_key = 'ld83qebudvbirmj'
	dropbox_secret_key = keyring.get_password('Dropbox RecaptureDocs',
		dropbox_access_key)
	assert dropbox_secret_key, "Dropbox secret key is null"
	new_relic_license_key = six.moves.input('New Relic license> ')
	new_relic_license_key
	sudo(lf('mkdir -p {install_root}'))
	files.upload_template("newrelic.ini", install_root, use_sudo=True)
	files.upload_template("ubuntu/recapture-docs.conf", "/etc/init",
		use_sudo=True, context=vars())

def enable_non_root_bind():
	sudo('aptitude install libcap2-bin')
	sudo('setcap "cap_net_bind_service=+ep" /usr/bin/python')

@task
def update_staging():
	install_to('envs/staging')
	with settings(warn_only=True):
		run('pkill -f staging/bin/recapture-docs')
		run('sleep 3')
	run('mkdir -p envs/staging/var/log')
	run('PYTHONUSERBASE=envs/staging envs/staging/bin/recapture-docs daemon')

@task
def update_production(version=None):
	install_to(install_root, version, use_sudo=True)
	sudo('restart recapture-docs || start recapture-docs')

def install_to(root, version=None, use_sudo=False):
	"""
	Install RecaptureDocs to a PEP-370 environment at root. If version is
	not None, install that version specifically. Otherwise, use the latest.
	"""
	action = sudo if use_sudo else run
	pkg_spec = 'recapturedocs'
	if version:
		pkg_spec += '==' + version
	action('mkdir -p {root}/lib/python2.7/site-packages'.format(**vars()))
	with apt.package_context('python-dev'):
		with context.shell_env(PYTHONUSERBASE=root):
			cmd = [
				'easy_install',
				'--user',
				'-U',
				'-f', 'http://dl.dropbox.com/u/54081/cheeseshop/index.html',
				pkg_spec,
			]
			action(' '.join(cmd))


@task
def setup_mongodb_firewall():
	allowed_ips = (
		'127.0.0.1',
		socket.gethostbyname('elektra'),
		socket.gethostbyname('ichiro'),
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

@task
def configure_nginx():
	sudo('aptitude install -y nginx')
	source = "ubuntu/nginx config"
	target = "/etc/nginx/sites-available/recapturedocs.com"
	files.upload_template(filename=source, destination=target, use_sudo=True)
	sudo(
		'ln -sf '
		'../sites-available/recapturedocs.com '
		'/etc/nginx/sites-enabled/'
	)
	sudo('service nginx restart')
