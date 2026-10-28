"""What an app may do here is what its token's scopes say: every root field asks for one of dokuments'
own (the ``@auth`` directive publishes it, a generated client gathers it), and `dokuments_all` stands
for all of them."""

import pytest
from kante.context import HttpContext, UniversalRequest
from strawberry.http.temporal_response import TemporalResponse

from arkitekt_service.graphql import scope_gaps
from dokuments_server.schema import schema

REQUEST_UPLOAD = 'mutation { requestMediaUpload(input: {originalFileName: "scoped.pdf", fileSize: 3}) { store } }'
FILES = "query { files { id } }"


def _as(token: str) -> HttpContext:
    return HttpContext(request=UniversalRequest(_extensions={}), response=TemporalResponse(), headers={"Authorization": f"Bearer {token}"}, type="http")


def _reason(result) -> str | None:  # noqa: ANN001
    return result.errors[0].extensions.get("reason") if result.errors else None


def test_every_root_field_asks_for_a_scope_dokuments_declares():
    assert scope_gaps(schema) == []


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_an_app_granted_reads_reads_and_writes_nothing(backend_stack):
    assert (await schema.execute(FILES, context_value=_as("readertest"))).errors is None
    refused = await schema.execute(REQUEST_UPLOAD, context_value=_as("readertest"))
    assert _reason(refused) == "INSUFFICIENT_SCOPE"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_editor_through_the_all_scope_uploads(s3_endpoint):
    """``test`` is an editor: no ``upload_roles`` are configured, so uploads fall back to ``dokuments_editor``."""
    made = await schema.execute(REQUEST_UPLOAD, context_value=_as("test"))
    assert made.errors is None, made.errors
