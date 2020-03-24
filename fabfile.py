"""
Routines for installing, staging, and serving recapturedocs on Ubuntu.

To install on a clean Ubuntu Bionic box, simply run
fab bootstrap
"""

import keyring
from fabric.api import sudo, run, task, env
from fabric.contrib import files

if not env.hosts:
    env.hosts = ['spidey']

install_root = '/opt/recapturedocs'
python = 'python3.8'


@task
def bootstrap():
    install_dependencies()
    install_env()
    install_service()
    update()
    configure_nginx()


@task
def install_dependencies():
    sudo('apt install -y software-properties-common')
    sudo('add-apt-repository -y ppa:deadsnakes/ppa')
    sudo('apt update -y')
    sudo(f'apt install -y {python} {python}-venv')


@task
def install_env():
    user = run('whoami')
    sudo(f'rm -R {install_root} || echo -n')
    sudo(f'mkdir -p {install_root}')
    sudo(f'chown {user} {install_root}')
    run(f'{python} -m venv {install_root}')
    run(f'{install_root}/bin/python -m pip install -U setuptools pip')


@task
def install_service(install_root=install_root):
    aws_access_key = '0ZWJV1BMM1Q6GXJ9J2G2'
    aws_secret_key = keyring.get_password('AWS', aws_access_key)
    assert aws_secret_key, "AWS secret key is null"
    dropbox_access_key = 'ld83qebudvbirmj'
    dropbox_secret_key = keyring.get_password(
        'Dropbox RecaptureDocs', dropbox_access_key
    )
    assert dropbox_secret_key, "Dropbox secret key is null"
    new_relic_license_key = input('New Relic license> ')
    sudo(f'mkdir -p {install_root}')
    files.upload_template("newrelic.ini", install_root, use_sudo=True)
    files.upload_template(
        "ubuntu/recapture-docs.service",
        "/etc/systemd/system",
        use_sudo=True,
        context=locals(),
    )
    sudo('systemctl enable recapture-docs')


@task
def update():
    install()
    sudo('systemctl restart recapture-docs')


def install():
    run('git clone https://github.com/jaraco/recapturedocs || echo -n')
    run('git -C recapturedocs pull')
    run(f'{install_root}/bin/python -m pip install -U ./recapturedocs')


@task
def remove_all():
    sudo('systemctl stop recapture-docs || echo -n')
    sudo('rm /etc/systemd/system/recapture-docs.service || echo -n')
    sudo(f'rm -Rf {install_root}')


@task
def configure_nginx():
    sudo('apt install -y nginx')
    source = "ubuntu/nginx config"
    target = "/etc/nginx/sites-available/recapturedocs.com"
    files.upload_template(filename=source, destination=target, use_sudo=True)
    sudo('ln -sf ' '../sites-available/recapturedocs.com ' '/etc/nginx/sites-enabled/')
    sudo('service nginx restart')
