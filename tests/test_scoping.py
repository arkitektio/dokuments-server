"""Every read is the caller's organization's, and a page reads whether or not text was found on it.

Two organizations each own a file, a document and its pages; each lists only its own through
the root lists (`files`, `documents`, `pages`) and through the nested ones.
"""

import uuid

import pytest
from asgiref.sync import sync_to_async
from arkitekt_datalayer.models import MediaStore
from kante.context import HttpContext

from core import models
from dokuments_server.schema import schema


@sync_to_async
def _make_document(context: HttpContext, title: str, contents: list[str | None]) -> models.Document:
    organization = context.request.organization
    key = uuid.uuid4().hex
    store = MediaStore.objects.create(
        organization=organization,
        path=f"s3://media/{key}",
        key=key,
        bucket="media",
        original_file_name=f"{title}.pdf",
        content_type="application/pdf",
        populated=True,
    )
    file = models.File.objects.create(name=f"{title}.pdf", store=store, creator=context.request.user, organization=organization)
    document = models.Document.objects.create(file=file, title=title)
    # Created out of order: reading order is the index, not the insertion order.
    for index in reversed(range(len(contents))):
        models.Page.objects.create(document=document, index=index, content=contents[index], image=store)
    return document


async def _data(context: HttpContext, query: str, variables: dict[str, object] | None = None) -> dict[str, object]:
    result = await schema.execute(query, variable_values=variables, context_value=context)
    assert not result.errors, result.errors
    assert result.data is not None
    return result.data


LISTS = """
    query {
        files { name documents { title } }
        documents { title pages { index } }
        pages { content document { title } }
    }
"""


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_lists_hold_only_the_callers_organization(authenticated_context, other_org_context):
    await _make_document(authenticated_context, "mine", ["my page"])
    await _make_document(other_org_context, "theirs", ["their page"])

    mine = await _data(authenticated_context, LISTS)
    assert [f["name"] for f in mine["files"]] == ["mine.pdf"]
    assert [d["title"] for d in mine["documents"]] == ["mine"]
    assert [p["content"] for p in mine["pages"]] == ["my page"]

    theirs = await _data(other_org_context, LISTS)
    assert [f["name"] for f in theirs["files"]] == ["theirs.pdf"]
    assert [d["title"] for d in theirs["documents"]] == ["theirs"]
    assert [p["document"]["title"] for p in theirs["pages"]] == ["theirs"]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_a_page_without_text_does_not_break_its_document(authenticated_context):
    document = await _make_document(authenticated_context, "scan", ["first", None, "third"])

    data = await _data(
        authenticated_context,
        "query($id: ID!) { document(id: $id) { pageCount pages { index content ocrResult { angle } } } }",
        {"id": str(document.id)},
    )

    assert data["document"]["pageCount"] == 3
    assert [p["index"] for p in data["document"]["pages"]] == [0, 1, 2]
    assert [p["content"] for p in data["document"]["pages"]] == ["first", None, "third"]
    assert [p["ocrResult"] for p in data["document"]["pages"]] == [None, None, None]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_documents_are_searched_by_title(authenticated_context, other_org_context):
    await _make_document(authenticated_context, "Annual Report", ["a"])
    await _make_document(authenticated_context, "Invoice", ["b"])
    await _make_document(other_org_context, "Another report", ["c"])

    data = await _data(authenticated_context, 'query { documents(filters: { search: "report" }) { title } }')

    assert [d["title"] for d in data["documents"]] == ["Annual Report"]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_file_events_go_to_the_files_organization(authenticated_context, other_org_context):
    """A file's events reach its organization's group only, never a group every organization joins."""
    from core import channels

    sent: list[tuple[object, list[str]]] = []
    original = channels.file_channel.broadcast
    channels.file_channel.broadcast = lambda message, groups=None: sent.append((message, groups))
    try:
        document = await _make_document(authenticated_context, "mine", ["a"])
    finally:
        channels.file_channel.broadcast = original

    file_id = await sync_to_async(lambda: document.file_id)()
    assert sent and all(groups == [channels.org_files_group(authenticated_context.request.organization.id)] for _, groups in sent)
    assert any(message.create == file_id for message, _ in sent)
    assert channels.org_files_group(other_org_context.request.organization.id) not in {group for _, groups in sent for group in groups}
