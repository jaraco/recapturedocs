import keyring
import os

import boto.mturk.connection


def set_connection_environment(access_key='0ZWJV1BMM1Q6GXJ9J2G2'):
    """
    boto requires the credentials to be either passed to the connection,
    stored in a unix-like config file unencrypted, or available in
    the environment, so pull the encrypted key out and put it in the
    environment.
    """
    if 'AWS_SECRET_ACCESS_KEY' in os.environ:
        return
    secret_key = keyring.get_password('AWS', access_key)
    assert secret_key, "Secret key is null"
    os.environ['AWS_ACCESS_KEY_ID'] = access_key
    os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key


def save_credentials(access_key, secret_key):
    keyring.set_password('AWS', access_key, secret_key)


class ConnectionFactory:
    production = True

    @classmethod
    def get_mturk_connection(class_):
        host = ['mechanicalturk.sandbox.amazonaws.com', 'mechanicalturk.amazonaws.com'][
            class_.production
        ]
        return boto.mturk.connection.MTurkConnection(host=host)
