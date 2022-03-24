"""
Routines for installing, staging, and serving jaraco.com on Ubuntu.

To install on a clean Ubuntu Bionic box, simply run
fab bootstrap
"""

import itertools

from fabric import task
from jaraco.fabric import files

flatten = itertools.chain.from_iterable

host = 'spidey'
hosts = [host]

project = 'jaraco.site'
site = 'jaraco.com'
install_root = '/opt/jaraco.com'
python = 'python3.8'


@task(hosts=hosts)
def bootstrap(c):
    install_dependencies(c)
    install_env(c)
    install_service(c)
    update(c)
    configure_nginx(c)
    install_cert(c)


@task(hosts=hosts)
def install_dependencies(c):
    # fop required by the resume endpoint
    c.sudo('apt install -y fop')
    # certbot for certificates
    c.sudo('apt-add-repository -y ppa:certbot/certbot')
    c.sudo('apt update -y')
    c.sudo('apt install -y python-certbot-nginx')

    c.sudo('apt install -y software-properties-common')
    c.sudo('add-apt-repository -y ppa:deadsnakes/ppa')
    c.sudo('apt update -y')
    c.sudo(f'apt install -y {python} {python}-venv')


@task(hosts=hosts)
def install_env(c):
    user = c.run('whoami')
    c.sudo(f'rm -R {install_root} || echo -n')
    c.sudo(f'mkdir -p {install_root}')
    c.sudo(f'chown {user} {install_root}')
    c.run(f'{python} -m venv {install_root}')
    c.run(f'{install_root}/bin/python -m pip install -U pip')


@task(hosts=hosts)
def install_service(c):
    files.upload_template(
        f"ubuntu/{project}.service",
        "/etc/systemd/system",
        use_sudo=True,
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
    c.run(f'git clone https://github.com/jaraco/{project} || echo -n')
    c.run(f'git -C {project} pull')
    c.run(f'{install_root}/bin/python -m pip install -U ./{project}')


@task(hosts=hosts)
def remove_all(c):
    c.sudo(f'systemctl stop {project} || echo -n')
    c.sudo(f'rm -Rf {install_root}')


@task(hosts=hosts)
def configure_nginx(c):
    c.sudo('apt install -y nginx')
    source = "ubuntu/nginx config"
    target = f"/etc/nginx/sites-available/{site}"
    files.upload_template(c, src=source, dest=target)
    c.sudo(f'ln -sf ../sites-available/{site} /etc/nginx/sites-enabled/')
    c.sudo('service nginx restart')


@task(hosts=hosts)
def install_cert(c):
    cmd = [
        'certbot',
        '--agree-tos',
        '--email',
        'jaraco@jaraco.com',
        '--non-interactive',
        '--nginx',
        'certonly',
    ]
    sites = (
        'jaraco.com',
        'www.jaraco.com',
        'blog.jaraco.com',
        'www.recapturedocs.com',
        'scicomm.pro',
        'www.scicomm.pro',
    )
    cmd += list(flatten(['--domain', name] for name in sites))
    c.sudo(' '.join(cmd))
