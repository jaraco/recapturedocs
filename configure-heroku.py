import json
import pprint
import urllib.parse

import requests
import keyring.http

app_name = 'recapturedocs'

session = requests.Session()


def configure_AWS():
    access_key = '0ZWJV1BMM1Q6GXJ9J2G2'
    secret_key = keyring.get_password('AWS', access_key)
    assert secret_key, "secret key is null"
    set_env_vars(
        AWS_ACCESS_KEY_ID=access_key,
        AWS_SECRET_ACCESS_KEY=secret_key,
    )


def set_env_vars(*args, **kwargs):
    do(path='config_vars', data=dict(*args, **kwargs), method='PUT')


def check_MongoHQ():
    do('addons')


def add_MongoHQ():
    install_addon('mongohq:free')


def get_auth():
    username = 'jaraco@jaraco.com'
    password = keyring.get_password('Heroku', username)
    if not password:
        tmpl = "Need to set password for Heroku / {username}"
        raise ValueError(tmpl.format(**locals()))
    return username, password


def do(path, method='GET', **kwargs):
    headers = {
        'Accept': 'application/json',
    }
    auth = get_auth()
    headers.update(kwargs.pop('headers', {}))
    if 'data' in kwargs and isinstance(kwargs['data'], dict):
        kwargs['data'] = json.dumps(kwargs['data'])
    base = 'https://api.heroku.com/apps/{app_name}/'.format(**globals())
    url = urllib.parse.urljoin(base, path)
    resp = session.request(method, url, headers=headers, auth=auth, **kwargs)
    resp.raise_for_status()
    data = resp.json()
    pprint.pprint(data)
    return data


def install_addon(name):
    path = 'addons/{name}'.format(name=name)
    do(path, method='POST')


def set_production():
    set_env_vars(COMMAND_LINE_ARGS='-C prod')


def create_app():
    data = {
        'app[name]': app_name,
        'app[stack]': 'cedar',
    }
    do('/apps', method='POST', data=urllib.parse.urlencode(data))


if __name__ == '__main__':
    create_app()
    configure_AWS()
    check_MongoHQ()
    add_MongoHQ()
    if app_name == 'recapturedocs':
        set_production()
