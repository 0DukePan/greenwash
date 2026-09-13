from unittest.mock import patch

from src.client import fetch


@patch('src.client.requests.get')
def test_fetch_uses_timeout(get):
    fetch('https://example.invalid')
    assert get.call_args.kwargs['timeout'] == 5
