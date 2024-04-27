"""
Routines for installing, staging, and serving jaraco.com on Ubuntu.

To install on an Ubuntu box previously bootstrapped with jaraco.site:
fab bootstrap
"""

import itertools

import keyring
from fabric import task
from jaraco.fabric import files
from jaraco.fabric import certs

flatten = itertools.chain.from_iterable

host = 'kelvin'
hosts = [host]

project = 'recapturedocs'
site = 'recapturedocs.com'
install_root = '/opt/recapturedocs'
python = 'python3'
ubuntu = 'recapturedocs/ubuntu'


@task(hosts=hosts)
def bootstrap(c):
    # assumes jaraco.site has already been run
    install_env(c)
    install_service(c)
    update(c)
    configure_nginx(c)
    install_certs(c)
    enable_nginx(c)


@task(hosts=hosts)
def install_certs(c):
    certs.install(c, 'recapturedocs.com', 'www.recapturedocs.com')


@task(hosts=hosts)
def install_env(c):
    c.run(f'rm -R {install_root} || echo -n')
    c.run(f'{python} -m venv {install_root}')
    c.run(f'{install_root}/bin/python -m pip install -U pip')


def _install_service_recapturedocs(c):
    aws_access_key = '0ZWJV1BMM1Q6GXJ9J2G2'
    aws_secret_key = keyring.get_password('AWS', aws_access_key)
    assert aws_secret_key, "AWS secret key is null"
    dropbox_access_key = 'ld83qebudvbirmj'
    dropbox_secret_key = keyring.get_password(
        'Dropbox RecaptureDocs', dropbox_access_key
    )
    assert dropbox_secret_key, "Dropbox secret key is null"
    new_relic_license_key = keyring.get_password('New Relic License', 'RecaptureDocs')
    globals().update(locals())
    files.upload_template(c, "newrelic.ini", install_root)


@task(hosts=hosts)
def install_service(c):
    _install_service_recapturedocs(c)
    files.upload_template(
        c,
        f"{ubuntu}/{project}.service",
        "/etc/systemd/system",
        context=globals(),
    )
    c.sudo(f'systemctl enable {project}')


@task(hosts=hosts)
def update(c):
    install(c)
    c.sudo(f'systemctl restart {project}')


def install(c):
    """
    Install project to environment at root.
    """
    c.run(
        f'{install_root}/bin/python -m pip install git+https://github.com/jaraco/{project}'
    )


@task(hosts=hosts)
def remove_all(c):
    c.sudo(f'systemctl stop {project} || echo -n')
    c.sudo(f'rm /etc/systemd/system/{project}.service')
    c.sudo(f'rm -Rf {install_root}')


@task(hosts=hosts)
def configure_nginx(c):
    c.sudo('apt install -y nginx')
    source = f"{ubuntu}/nginx config"
    target = f"/etc/nginx/sites-available/{site}"
    files.upload_template(c, src=source, dest=target)
    c.sudo('service nginx restart')


@task(hosts=hosts)
def enable_nginx(c):
    # only enable after certificates are installed
    c.sudo(f'ln -sf ../sites-available/{site} /etc/nginx/sites-enabled/')
    c.sudo('service nginx restart')
