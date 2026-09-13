from src.config import default_port


def test_default_port_hidden():
    assert default_port('dev') == 8080
    assert default_port('test') == 8080
