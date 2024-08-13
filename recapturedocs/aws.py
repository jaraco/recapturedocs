import os

import boto3
import keyring


def get_session(access_key='0ZWJV1BMM1Q6GXJ9J2G2'):
    """
    Construct a boto session for the given access key.
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
