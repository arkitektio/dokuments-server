"""Typed, fully-documented configuration schema for the **dokuments** service.

Owned by this service. Values resolve (highest precedence first) from init
kwargs, environment variables (nested via ``__`` — e.g. ``POSTGRES__PASSWORD``),
then the YAML file (``config.yaml`` where the service runs by default; override with
``ARKITEKT_CONFIG_FILE``). Secret fields have **no default**: loading fails fast
with a ``ValidationError`` if they are not supplied via config or environment.
"""


from pydantic import Field

from arkitekt_datalayer.configuration import DatalayerBucket, DatalayerSettings

from arkitekt_service.server import settings as shared
from arkitekt_service.server.settings import DjangoSettings, PostgresSettings, ServiceSettings
from authentikate.base_models import AuthentikateSettings

class RedisSettings(shared.RedisSettings):
    """Redis connection (channel layer / cache)."""

    channel_prefix: str = Field(default="dokuments", description="Key prefix for the channels_redis channel layer. Must be unique per service: every service on a shared redis used to send under the same prefix, so identically-named groups (e.g. \"files\") delivered one service's events to another's subscribers.")


class DokumentsDatalayerSettings(DatalayerSettings):
    """S3 storage for documents and page images: the media bucket."""

    session_name: str = Field(default="dokuments", description="Prefix of every STS session dokuments assumes, so an object store's audit log names it.")
    media: DatalayerBucket = Field(description="Bucket for documents and page images. Required for this service.")


class Settings(ServiceSettings):
    """Top-level, validated configuration for the dokuments service."""

    django: DjangoSettings = Field(description="Core Django settings.")
    postgres: PostgresSettings = Field(description="PostgreSQL connection.")
    redis: RedisSettings = Field(description="Redis connection.")
    authentikate: AuthentikateSettings = Field(description="Token-verification config (authentikate).")
    datalayer: DokumentsDatalayerSettings = Field(description="S3 storage connection and buckets.")
