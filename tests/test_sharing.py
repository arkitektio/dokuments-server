"""A guest of the organization, granted a collaboration and nothing else: what they read, and what they may not do.

Their token lists their collaborations by key (`collabs`: lok's key, one across the hub), with the
roles they hold in each; the guest token is minted per test. A full member ("test") puts files in a
collaboration under a fresh key (`addManyToCollaboration`, which makes dokuments' row of it): each
brings its bytes and its pages' images, and its documents and their pages are in it with it.
"""

import asyncio
import uuid

import pytest
from arkitekt_service.collaborations.models import Collaboration
from botocore.client import BaseClient
from django.test import AsyncClient
from kante.context import HttpContext
from strawberry.types import ExecutionResult

from dokuments_server.schema import schema
from tests.conftest import GuestFactory, token_context
from tests.seed import Seeded, add_page, seed

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]

#: A GraphQL payload, as strawberry hands it over.
GraphQLData = dict[str, object]

LISTS = """
query {
  files { id store { id } }
  documents { id }
  pages { id }
}
"""
RENDER = """
query ($id: ID!) {
  file(id: $id) {
    id
    store { id }
    documents { id title pages { id index image { id } } }
  }
}
"""
FILE = "query ($id: ID!) { file(id: $id) { id } }"
DOCUMENT = "query ($id: ID!) { document(id: $id) { id } }"
PAGE = "query ($id: ID!) { page(id: $id) { id image { id } } }"
ACCESS = "mutation ($id: String!) { requestMediaAccess(input: {storeId: $id}) { bucket key } }"


async def _run(ctx: HttpContext, query: str, **variables: object) -> ExecutionResult:
    return await schema.execute(
        query, context_value=ctx, variable_values=variables or None
    )


async def _member(query: str, **variables: object) -> GraphQLData:
    """Run ``query`` as the full member, as a request of its own, and hand back its data."""
    result = await _run(token_context("test"), query, **variables)
    assert not result.errors, result.errors
    assert result.data is not None
    return result.data


async def _guest(ctx: HttpContext, query: str, **variables: object) -> GraphQLData:
    result = await _run(ctx, query, **variables)
    assert not result.errors, result.errors
    assert result.data is not None
    return result.data


def _refused(result: ExecutionResult, reason: str) -> None:
    assert result.errors, "it was let through"
    extensions = result.errors[0].extensions
    assert extensions is not None, result.errors
    assert extensions.get("reason") == reason, result.errors


async def _collaboration(ctx: HttpContext, *files: Seeded) -> str:
    """A collaboration of the organization holding ``files``, as a full member puts them in: under a
    fresh key, as lok hands one out, in one ``addManyToCollaboration``. Its key."""
    key = str(uuid.uuid4())
    added = await _member(
        "mutation ($input: AddManyToCollaborationInput!) { addManyToCollaboration(input: $input) { key name } }",
        input={
            "collaboration": key,
            "name": "Shared",
            "objects": [
                {"identifier": "@dokuments/file", "object": str(seeded.file.pk)}
                for seeded in files
            ],
        },
    )
    assert added["addManyToCollaboration"] == {"key": key, "name": "Shared"}
    assert await Collaboration.objects.filter(
        key=key, organization=ctx.request.organization
    ).aexists()
    return key


def _ids(rows: object) -> set[str]:
    assert isinstance(rows, list)
    return {str(row["id"]) for row in rows}


async def test_a_guest_reads_the_shared_file_its_documents_and_pages_and_nothing_else(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    other = await seed(authenticated_context, "Other")  # the oldest: first on a page
    shared = await seed(authenticated_context, "Shared")
    ctx = guest({await _collaboration(authenticated_context, shared): []})

    seen = await _guest(ctx, LISTS)
    first = await _guest(ctx, "{ files(pagination: {limit: 1}) { id } }")
    assert _ids(first["files"]) == {str(shared.file.pk)}, (
        "narrowed before the page is cut, not after"
    )

    assert _ids(seen["files"]) == {str(shared.file.pk)}
    assert _ids(seen["documents"]) == {str(shared.document.pk)}
    assert _ids(seen["pages"]) == {str(page.pk) for page in shared.pages}
    rendered = await _guest(ctx, RENDER, id=str(shared.file.pk))
    file = rendered["file"]
    assert isinstance(file, dict)
    assert file["store"] == {"id": str(shared.file.store_id)}, "its bytes come along"
    [document] = file["documents"]
    assert [p["image"]["id"] for p in document["pages"]] == [
        str(page.image_id) for page in shared.pages
    ], "every page's image comes along"

    for query, obj in (
        (FILE, other.file),
        (DOCUMENT, other.document),
        (PAGE, other.pages[0]),
    ):
        assert (await _run(ctx, query, id=str(obj.pk))).errors, (
            f"{type(obj).__name__} {obj.pk} is in no collaboration of theirs"
        )
    member = await _member(LISTS)
    assert _ids(member["files"]) == {str(shared.file.pk), str(other.file.pk)}, (
        "a full member is not narrowed"
    )


async def test_a_page_added_after_the_share_comes_with_its_image(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    shared = await seed(authenticated_context, "Growing", pages=1)
    ctx = guest({await _collaboration(authenticated_context, shared): []})

    added = await add_page(authenticated_context, shared.document, 1)

    seen = await _guest(ctx, PAGE, id=str(added.pk))
    assert seen["page"] == {"id": str(added.pk), "image": {"id": str(added.image_id)}}
    granted = await _guest(ctx, ACCESS, id=str(added.image_id))
    assert granted["requestMediaAccess"] is not None


async def test_a_guest_reads_the_bytes_of_what_is_shared_and_of_nothing_else(
    authenticated_context: HttpContext,
    guest: GuestFactory,
    s3_client: BaseClient,
    s3_endpoint: str,
) -> None:
    shared = await seed(authenticated_context, "Bytes", pages=1)
    other = await seed(authenticated_context, "Unshared", pages=1)
    assert shared.file.store is not None
    s3_client.put_object(
        Bucket="media", Key=shared.file.store.key, Body=b"%PDF shared bytes"
    )
    ctx = guest({await _collaboration(authenticated_context, shared): []})

    for store in (shared.file.store_id, shared.pages[0].image_id):
        granted = await _guest(ctx, ACCESS, id=str(store))
        assert granted["requestMediaAccess"] is not None

    for store in (other.file.store_id, other.pages[0].image_id):
        assert (await _run(ctx, ACCESS, id=str(store))).errors, (
            f"store {store} is in no collaboration of theirs"
        )
    general = await _run(
        ctx, "mutation { requestGeneralMediaAccess(input: {}) { bucket } }"
    )
    _refused(general, "SCOPED_READ_ONLY")


async def test_a_guest_writes_nothing_and_shares_nothing(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    shared = await seed(authenticated_context, "Shared")
    key = await _collaboration(authenticated_context, shared)
    ctx = guest({key: ["dokuments_editor"]})

    attempts = {
        "a document": (
            'mutation ($file: ID!) { createDocument(input: {file: $file, title: "x"}) { id } }',
            {"file": str(shared.file.pk)},
        ),
        "a file": (
            "mutation ($store: FileLike!) { fromFileLike(input: {file: $store}) { id } }",
            {"store": str(shared.file.store_id)},
        ),
        "a delete": (
            "mutation ($id: ID!) { deleteFile(input: {id: $id}) }",
            {"id": str(shared.file.pk)},
        ),
        "an upload": (
            'mutation { requestMediaUpload(input: {originalFileName: "x.pdf", fileSize: 3}) { store } }',
            {},
        ),
        "a share": (
            "mutation ($input: CollaborationObjectInput!) { addToCollaboration(input: $input) { key } }",
            {
                "input": {
                    "collaboration": key,
                    "identifier": "@dokuments/file",
                    "object": str(shared.file.pk),
                }
            },
        ),
    }
    for what, (mutation, variables) in attempts.items():
        result = await _run(ctx, mutation, **variables)
        assert result.errors, f"{what} was let through"
        _refused(result, "SCOPED_READ_ONLY")


async def test_root_fields_that_hand_out_no_files_are_closed_to_a_guest(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    shared = await seed(authenticated_context, "Shared")
    key = await _collaboration(authenticated_context, shared)
    await _collaboration(
        authenticated_context, await seed(authenticated_context, "Theirs")
    )
    ctx = guest({key: []})

    _refused(
        await _run(ctx, "{ collaborationsStats { count itemCount } }"),
        "COLLABORATION_DOES_NOT_REACH",
    )
    listed = await _guest(ctx, "{ collaborations { key } }")
    assert listed["collaborations"] == [{"key": key}], "only the ones granted to them"


async def test_a_guest_is_refused_the_file_stream(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    """A subscription streams the organization's events, which no queryset narrows (the WebSocket transport)."""
    key = await _collaboration(
        authenticated_context, await seed(authenticated_context, "Shared")
    )

    stream = await schema.subscribe(
        "subscription { files { create { id } } }",
        context_value=guest({key: []}),
    )

    if not isinstance(stream, ExecutionResult):
        # Over a WebSocket the refusal is the stream's first (and only) message.
        stream = await asyncio.wait_for(anext(stream), timeout=5)
    _refused(stream, "SCOPED_READ_ONLY")


async def test_the_service_manifest_takes_no_guest_token(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    """The one route beside GraphQL that answers more than health: signed by rekuest, never by a bearer token."""
    guest({str(uuid.uuid4()): []})

    response = await AsyncClient().get(
        "/_rekuest/service/manifest", headers={"Authorization": "Bearer guest"}
    )

    assert response.status_code in (401, 503), response.status_code
