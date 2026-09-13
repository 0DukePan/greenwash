import json


def load(s):
    try:
        value = json.loads(s)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}
