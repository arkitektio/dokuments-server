"""The GraphQL schema over a real database and a real object store.

Replaces the previous tests/test.py, which queried `core.models.Image` and a
`dataset { name }` field on File -- neither exists in dokuments (Image is mikro's
model, and Dataset is not exposed in this schema at all). It had been copied across
from mikro and never run.

Queries go through `await schema.execute(...)`, not `execute_sync`: the koherent
provenance extension's `on_operation` hook is async, and a sync execution fails with
"SchemaExtension hook ... failed to complete synchronously".
"""

import uuid

import pytest
from asgiref.sync import sync_to_async

from arkitekt_datalayer.models import MediaStore

from core import models
from dokuments_server.schema import schema

FILE_QUERY = """
    query File($id: ID!) {
        file(id: $id) {
            id
            name
            store { id key bucket path }
        }
    }
"""


@pytest.fixture
def make_file(authenticated_context):
    """Create a File backed by a media store of the caller's organization, returning (file, store)."""

    @sync_to_async
    def _make(key: str, body: bytes | None = None):
        store = MediaStore.objects.create(
            organization=authenticated_context.request.organization,
            path=f"s3://media/{key}",
            key=key,
            bucket="media",
            original_file_name="a.pdf",
            content_type="application/pdf",
            populated=True,
        )
        file = models.File.objects.create(
            name="a.pdf",
            store=store,
            creator=authenticated_context.request.user,
            organization=authenticated_context.request.organization,
        )
        return file, store

    return _make


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_file_query_resolves_its_store(authenticated_context, make_file):
    """A File created through the ORM is readable through the schema."""
    key = uuid.uuid4().hex
    file, store = await make_file(key)

    result = await schema.execute(
        FILE_QUERY, variable_values={"id": str(file.id)}, context_value=authenticated_context
    )

    assert not result.errors, result.errors
    assert result.data["file"]["name"] == "a.pdf"
    assert result.data["file"]["store"]["key"] == key
    assert result.data["file"]["store"]["bucket"] == "media"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_document_and_pages_traverse_back_to_the_file(
    authenticated_context, make_file
):
    """Document -> pages -> image walks the relations the OCR pipeline writes."""
    file, store = await make_file(uuid.uuid4().hex)

    @sync_to_async
    def _make_doc():
        document = models.Document.objects.create(file=file, title="Scanned report")
        models.Page.objects.create(document=document, index=0, content="page one", image=store)
        models.Page.objects.create(document=document, index=1, content="page two", image=store)
        return document

    document = await _make_doc()

    result = await schema.execute(
        """
        query Document($id: ID!) {
            document(id: $id) {
                title
                file { name }
                pages { index content image { key } }
            }
        }
        """,
        variable_values={"id": str(document.id)},
        context_value=authenticated_context,
    )

    assert not result.errors, result.errors
    doc = result.data["document"]
    assert doc["title"] == "Scanned report"
    assert doc["file"]["name"] == "a.pdf"
    assert [p["index"] for p in doc["pages"]] == [0, 1]
    assert [p["content"] for p in doc["pages"]] == ["page one", "page two"]
    assert doc["pages"][0]["image"]["key"] == store.key
