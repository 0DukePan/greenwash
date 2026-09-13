import pytest


@pytest.fixture()
def tmp_config(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text("{}")
    return path
