import importlib_resources
import pytest


@pytest.fixture
def sample_stream():
    files = importlib_resources.files('recapturedocs')
    return files.joinpath('static/Lorem ipsum.pdf').open(mode='rb')
