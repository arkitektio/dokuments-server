"""Test settings: a real postgres and a real object store, both from
``tests/integration/docker-compose.yaml``.

Neither host port is pinned. Docker assigns them per run and ``tests/conftest.py``
asks the running stack which it got, then writes them in here -- ``DATABASES`` via
``django_db_modify_db_settings`` and ``DATALAYER["port"]`` via the ``s3_endpoint``
fixture. The placeholders below only matter if you point the suite at a stack you
started by hand.
"""

from .settings import *  # noqa
from .settings import DATABASES, AUTHENTIKATE
import logging

DATABASES["default"] = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "testdb",
    "USER": "test",
    "PASSWORD": "test",
    "HOST": "localhost",
    # Placeholder -- conftest overwrites this with the port docker actually assigned.
    "PORT": "5432",
}

# Django forces DEBUG=False under the test runner, and authentikate 3.0 refuses static
# tokens when DEBUG is False. These are deliberate test fixtures, so opt in explicitly.
#: What a test token is unless it says otherwise: dokuments' admin, through an app granted all of dokuments.
ADMIN_WITH_EVERY_SCOPE = {"roles": ["dokuments_admin"], "scope": "openid dokuments_all"}

AUTHENTIKATE = {
    **AUTHENTIKATE,
    "allow_static_tokens_in_production": True,
    "static_tokens": {
        name: {**ADMIN_WITH_EVERY_SCOPE, **token}
        for name, token in {
            "test": {"sub": "1", "roles": ["dokuments_editor"]},
            # A user in a different organization, for cross-tenant scoping tests.
            "othertest": {"sub": "9", "org": "other_org", "roles": ["dokuments_editor"]},
            # An app granted only what it reads, for the scope tests (tests/test_scopes.py).
            "readertest": {"sub": "1", "scope": "openid dokuments_read"},
        }.items()
    },
}

# --- object storage -------------------------------------------------------------
# The credentials are the scoped user `initc` provisions (see
# tests/integration/configs/rustfs.yaml), not the RustFS root pair: the suite should
# exercise the same kind of identity the service uses in production. The port is a
# placeholder -- the `s3_endpoint` fixture sets the mapped one.
DATALAYER = {
    "access_key": "dokuments_access_key",
    "secret_key": "dokuments_secret_key",
    "host": "localhost",
    "port": 9000,
    "protocol": "http",
    "region": "us-east-1",
    "role_arn": "arn:aws:iam::000000000000:role/datalayer",
    "session_name": "dokuments-tests",
    "media": {"bucket": "media"},
}


# Disable migrations for faster tests: the schema is built with run-syncdb.
class DisableMigrations:
    """Disable migrations during testing for faster test execution."""

    def __contains__(self, item: str) -> bool:
        return True

    def __getitem__(self, item: str) -> None:
        return None


MIGRATION_MODULES = DisableMigrations()

logging.disable(logging.CRITICAL)

# Redis is in the stack but the suite does not need a broker.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# An in-process cache keeps tests independent of a shared redis.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
