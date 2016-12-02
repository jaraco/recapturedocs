"""
Routines for installing, staging, and serving recapturedocs on Ubuntu.

To install on a clean Ubuntu Xenial box, simply run
fab bootstrap
"""

import socket
import urllib.request

import six
import keyring
from fabric.api import sudo, run, settings, task, env
from fabric.contrib import files
from jaraco.fabric import mongodb
from jaraco.text import local_format as lf
from jaraco.fabric import apt

__all__ = [
	'install_env', 'update_staging', 'install_service',
	'update_production', 'setup_mongodb_firewall', 'mongodb_allow_ip',
	'remove_all', 'bootstrap', 'configure_nginx',
]

if not env.hosts:
	env.hosts = ['punisher']

install_root = '/opt/recapturedocs'


@task
def bootstrap():
	install_env()
	update_production()

@task
def install_env():
	sudo('rm -R {install_root} || echo -n'.format(**globals()))
	sudo('aptitude -q install -y python-setuptools python-lxml')
	mongodb.distro_install('3.2')
	setup_mongodb_firewall()
	install_service()

@task
def install_service(install_root=install_root):
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
	files.upload_template("ubuntu/recapture-docs.service", "/etc/systemd/system",
		use_sudo=True, context=vars())
	sudo('systemctl enable recapture-docs')

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
	run('envs/staging/bin/recapture-docs daemon')

@task
def update_production(version=None):
	install_to(install_root, version, action=sudo)
	sudo('systemctl restart recapture-docs')

def install_to(root, version=None, action=run):
	"""
	Install RecaptureDocs to root. If version is
	not None, install that version specifically. Otherwise, use the latest.
	"""
	pkg_spec = 'recapturedocs'
	if version:
		pkg_spec += '==' + version
	run('python3 -m pip install --user -U rwt')
	action('python3 -m rwt virtualenv -- -m virtualenv --python python2.7 ' + root)
	pkgs = 'python-dev', 'libffi-dev', 'libssl-dev'
	with apt.package_context(pkgs):
		cmd = [
			root + '/bin/pip',
			'install',
			'-U',
			pkg_spec,
		]
		action(' '.join(cmd))


@task
def setup_mongodb_firewall():
	allowed_ips = (
		'127.0.0.1',
		socket.gethostbyname('punisher'),
		socket.gethostbyname('elektra'),
	)
	with settings(warn_only=True):
		sudo('iptables --new-chain mongodb')
		sudo('iptables -D INPUT -p tcp --dport 27017 -j mongodb')
		sudo('iptables -D INPUT -p tcp --dport 27018 -j mongodb')
	sudo('iptables -A INPUT -p tcp --dport 27017 -j mongodb')
	sudo('iptables -A INPUT -p tcp --dport 28017 -j mongodb')
	sudo('iptables --flush mongodb')
	sudo('iptables -A mongodb -j REJECT')
	list(map(mongodb_allow_ip, allowed_ips))

@task
def mongodb_allow_ip(ip=None):
	if ip is None:
		url = 'http://automation.whatismyip.com/n09230945.asp'
		resp = urllib.request.urlopen(url)
		ip = resp.read()
	else:
		ip = socket.gethostbyname(ip)
	sudo(lf('iptables -I mongodb -s {ip} --jump RETURN'))

@task
def remove_all():
	sudo('systemctl stop recapture-docs || echo -n')
	sudo('rm /etc/systemd/system/recapture-docs.service || echo -n')
	sudo('rm -Rf /opt/recapturedocs')

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
