from src.config import default_port


def test_default_port():
    assert default_port('prod') == 443
