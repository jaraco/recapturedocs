import keyring
import os

import boto3


def get_session(access_key='0ZWJV1BMM1Q6GXJ9J2G2'):
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
    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='us-east',
    )


def save_credentials(access_key, secret_key):
    keyring.set_password('AWS', access_key, secret_key)


class ConnectionFactory:
    @classmethod
    def get_mturk_connection(class_):
        return get_session().client('mturk')
