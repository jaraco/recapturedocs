"""
Routines for installing, staging, and serving recapturedocs on Ubuntu.

To install on a clean Ubuntu Xenial box, simply run
fab bootstrap
"""

import socket
import shutil
import subprocess
import os
import sys

import six
import keyring
import requests
from fabric.api import sudo, run, settings, task, env
from fabric.contrib import files
from jaraco.fabric import mongodb
from jaraco.text import local_format as lf

if not env.hosts:
	env.hosts = ['punisher']

install_root = '/opt/recapturedocs'


@task
def bootstrap():
	install_dependencies()
	install_env()
	install_mongodb()
	update()
	install_service()


@task
def install_dependencies():
	sudo('apt install -y software-properties-common')
	sudo('add-apt-repository -y ppa:deadsnakes/ppa')
	sudo('apt update -y')
	sudo('apt install -y python3.6 python3.6-venv')


@task
def install_env():
	user = run('whoami')
	sudo(f'rm -R {install_root} || echo -n')
	sudo(f'mkdir -p {install_root}')
	sudo(f'chown {user} {install_root}')
	run(f'python3.6 -m venv {install_root}')
	run(f'{install_root}/bin/python -m pip install -U setuptools pip')


@task
def install_mongodb():
	mongodb.distro_install('3.2')
	setup_mongodb_firewall()


@task
def install_service(install_root=install_root):
	aws_access_key = '0ZWJV1BMM1Q6GXJ9J2G2'
	aws_secret_key = keyring.get_password('AWS', aws_access_key)
	assert aws_secret_key, "AWS secret key is null"
	dropbox_access_key = 'ld83qebudvbirmj'
	dropbox_secret_key = keyring.get_password(
		'Dropbox RecaptureDocs',
		dropbox_access_key)
	assert dropbox_secret_key, "Dropbox secret key is null"
	new_relic_license_key = six.moves.input('New Relic license> ')
	new_relic_license_key
	sudo(lf('mkdir -p {install_root}'))
	files.upload_template("newrelic.ini", install_root, use_sudo=True)
	files.upload_template(
		"ubuntu/recapture-docs.service", "/etc/systemd/system",
		use_sudo=True, context=vars())
	sudo('systemctl enable recapture-docs')


def enable_non_root_bind():
	sudo('aptitude install libcap2-bin')
	sudo('setcap "cap_net_bind_service=+ep" /usr/bin/python')


@task
def update():
	install()
	sudo('systemctl restart recapture-docs')


def install():
	shutil.rmtree('dist')
	subprocess.run([sys.executable, 'setup.py', 'bdist_wheel'])
	dist, = os.listdir('dist')
	run('mkdir -p install')
	files.put(f'dist/{dist}', 'install/')
	run(f'{install_root}/bin/pip install ~/install/{dist}')


@task
def setup_mongodb_firewall():
	allowed_ips = (
		'127.0.0.1',
		socket.gethostbyname('punisher'),
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
		url = 'https://api.ipify.org'
		ip = requests.get(url).text
	else:
		ip = socket.gethostbyname(ip)
	sudo(lf('iptables -I mongodb -s {ip} --jump RETURN'))


@task
def remove_all():
	sudo('systemctl stop recapture-docs || echo -n')
	sudo('rm /etc/systemd/system/recapture-docs.service || echo -n')
	sudo(f'rm -Rf {install_root}')


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
