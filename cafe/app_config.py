import os


def owner_password(environment=None):
    """Return the configured owner password, defaulting to the shop PIN."""
    values = os.environ if environment is None else environment
    return values.get("CAFE_OWNER_PASSWORD", "1986")
