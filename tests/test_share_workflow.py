"""Sharing a workflow: what a root task created in dokuments, put in a collaboration as it is now.

A workflow is a root task (koherent's ``Task.root_task_id``). A file, a document and a page record the
task they were created through (``created_through``) from the provenance token an agent sends with
``fromFileLike`` / ``createDocument`` / ``createPage`` (the ``Rekuest-Task`` header, signed by the test
rekuest key in ``tests/fixtures/provenance_key.json``). So every structure here can say what made it:
no workflow share reports one as ``unknown``.

The collaboration is lok's, named by a key: a full member shares under a fresh one, and a guest's
token names the same key.
"""

import datetime
import json
import pathlib
import uuid
from dataclasses import dataclass

import pytest
from arkitekt_service.collaborations.models import Collaboration, CollaborationItem
from asgiref.sync import sync_to_async
from joserfc import jwt
from joserfc.jwk import OKPKey
from kante.context import HttpContext
from strawberry.types import ExecutionResult

from core import models
from dokuments_server.schema import schema
from tests.conftest import GuestFactory, token_context
from tests.seed import Seeded, seed, store

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]

#: A GraphQL payload, as strawberry hands it over.
GraphQLData = dict[str, object]

KEY = OKPKey.import_key(
    json.loads(
        (pathlib.Path(__file__).parent / "fixtures" / "provenance_key.json").read_text()
    )
)

FROM_FILE_LIKE = (
    "mutation ($store: FileLike!) { fromFileLike(input: {file: $store}) { id } }"
)
CREATE_DOCUMENT = "mutation ($file: ID!, $title: String!) { createDocument(input: {file: $file, title: $title}) { id } }"
CREATE_PAGE = """
mutation ($document: ID!, $image: FileLike!) {
  createPage(input: {document: $document, image: $image, index: 0, content: "made", ocrResult: {lines: [], angle: 0}}) { id }
}
"""
SHARE = """
mutation ($input: ShareWorkflowInput!) {
  shareWorkflow(input: $input) {
    collaboration
    dryRun
    added { identifier object }
    covered
    skipped { identifier object wholeIdentifier whole }
    unknown
  }
}
"""
ADD = "mutation ($input: CollaborationObjectInput!) { addToCollaboration(input: $input) { key } }"
LISTS = """
query ($files: FileFilter, $documents: DocumentFilter, $pages: PageFilter) {
  files(filters: $files) { id }
  documents(filters: $documents) { id }
  pages(filters: $pages) { id }
}
"""


def task_token(task: str, root: str) -> str:
    """A task token as rekuest signs it for the static test user ("1"): the task ``task`` of the workflow ``root``."""
    now = int(datetime.datetime.now(datetime.UTC).timestamp())
    return jwt.encode(
        {"alg": "Ed25519", "kid": "dokuments-test-provenance"},
        {
            "iss": "rekuest",
            "aud": ["dokuments"],
            "sub": "1",
            "act": {"sub": "1", "cid": "static", "iss": "static_issuer"},
            "iat": now,
            "exp": now + 300,
            "jti": uuid.uuid4().hex,
            "tsk": task,
            "ptk": root if task != root else None,
            "rtk": root,
            "rcb": "1",
            "ahs": "e3b0c44298fc1c14",
            "aha": "sha256-canonical-v1",
        },
        KEY,
        algorithms=["Ed25519"],
    )


async def _run(ctx: HttpContext, query: str, **variables: object) -> ExecutionResult:
    return await schema.execute(
        query, context_value=ctx, variable_values=variables or None
    )


async def _member(
    query: str, task: str | None = None, **variables: object
) -> GraphQLData:
    """Run ``query`` as the full member, as a request of its own (under the task token ``task``)."""
    result = await _run(token_context("test", task=task), query, **variables)
    assert not result.errors, result.errors
    assert result.data is not None
    return result.data


def _created(data: GraphQLData, field: str) -> str:
    made = data[field]
    assert isinstance(made, dict)
    return str(made["id"])


@dataclass(frozen=True)
class Workflow:
    """A workflow's root task and what it made, beside what it did not."""

    root: str
    file: models.File
    document: models.Document
    page: models.Page
    #: Made before the workflow, and not shared; the workflow only read a document from it.
    older: Seeded
    document_of_older: models.Document
    #: Made in the organization without a provenance token.
    unrecorded: models.File


async def _workflow(ctx: HttpContext) -> Workflow:
    """A workflow (three tasks under one root) that filed a file, read a document from it with one
    page, and read a document from an older file; plus a file it did not make."""
    older = await seed(ctx, "Older")
    unrecorded_store = await sync_to_async(store)(ctx, "unrecorded.pdf")
    unrecorded = _created(
        await _member(FROM_FILE_LIKE, store=str(unrecorded_store.pk)), "fromFileLike"
    )
    root = f"root-{uuid.uuid4().hex}"
    upload, read, recognise = (
        task_token(f"task-{uuid.uuid4().hex}", root) for _ in range(3)
    )

    made_store = await sync_to_async(store)(ctx, "made.pdf")
    file = _created(
        await _member(FROM_FILE_LIKE, task=upload, store=str(made_store.pk)),
        "fromFileLike",
    )
    document = _created(
        await _member(CREATE_DOCUMENT, task=read, file=file, title="Made"),
        "createDocument",
    )
    image = await sync_to_async(store)(ctx, "made-0.png")
    page = _created(
        await _member(
            CREATE_PAGE, task=recognise, document=document, image=str(image.pk)
        ),
        "createPage",
    )
    document_of_older = _created(
        await _member(
            CREATE_DOCUMENT, task=read, file=str(older.file.pk), title="Of older"
        ),
        "createDocument",
    )
    return Workflow(
        root=root,
        file=await models.File.objects.aget(pk=file),
        document=await models.Document.objects.aget(pk=document),
        page=await models.Page.objects.aget(pk=page),
        older=older,
        document_of_older=await models.Document.objects.aget(pk=document_of_older),
        unrecorded=await models.File.objects.aget(pk=unrecorded),
    )


def _ids(data: GraphQLData, field: str) -> set[str]:
    rows = data[field]
    assert isinstance(rows, list)
    return {str(row["id"]) for row in rows}


def _report(workflow: Workflow, key: str, *, dry_run: bool) -> GraphQLData:
    """What sharing ``workflow`` reports: its file put in, its document and page covered by it, the
    document of the older file left out, nothing unknown."""
    return {
        "collaboration": key,
        "dryRun": dry_run,
        "added": [{"identifier": "@dokuments/file", "object": str(workflow.file.pk)}],
        "covered": 2,
        "skipped": [
            {
                "identifier": "@dokuments/document",
                "object": str(workflow.document_of_older.pk),
                "wholeIdentifier": "@dokuments/file",
                "whole": str(workflow.older.file.pk),
            }
        ],
        "unknown": [],
    }


async def test_what_a_workflow_creates_records_the_task_it_was_created_through(
    authenticated_context: HttpContext,
) -> None:
    workflow = await _workflow(authenticated_context)

    @sync_to_async
    def roots() -> list[str | None]:
        made = [
            workflow.file,
            workflow.document,
            workflow.page,
            workflow.document_of_older,
        ]
        return [
            type(obj)
            ._base_manager.select_related("created_through")
            .get(pk=obj.pk)
            .created_through.root_task_id  # type: ignore[union-attr]
            for obj in made
        ]

    assert await roots() == [workflow.root] * 4
    assert workflow.unrecorded.created_through_id is None, "no token, no task"


async def test_a_dry_run_says_what_sharing_a_workflow_puts_in_and_writes_nothing(
    authenticated_context: HttpContext,
) -> None:
    workflow = await _workflow(authenticated_context)
    key = str(uuid.uuid4())

    tried = await _member(
        SHARE, input={"collaboration": key, "rootTask": workflow.root, "dryRun": True}
    )

    assert tried["shareWorkflow"] == _report(workflow, key, dry_run=True)
    assert not await Collaboration.objects.filter(key=key).aexists(), (
        "a dry run makes no row of the collaboration here"
    )
    assert await CollaborationItem.objects.acount() == 0


async def test_sharing_a_workflow_puts_in_what_it_made_and_a_guest_sees_exactly_that(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    workflow = await _workflow(authenticated_context)
    key = str(uuid.uuid4())
    before = await _run(guest({key: []}), LISTS)
    assert not before.errors, before.errors
    assert before.data == {"files": [], "documents": [], "pages": []}, (
        "a key granted before anything is put in here holds nothing"
    )

    shared = await _member(
        SHARE, input={"collaboration": key, "rootTask": workflow.root, "name": "Pilot"}
    )

    assert shared["shareWorkflow"] == _report(workflow, key, dry_run=False)
    assert (await Collaboration.objects.aget(key=key)).name == "Pilot"
    seen = await _run(guest({key: []}), LISTS)
    assert not seen.errors, seen.errors
    assert seen.data is not None
    assert _ids(seen.data, "files") == {str(workflow.file.pk)}
    assert _ids(seen.data, "documents") == {str(workflow.document.pk)}, (
        "not the document read from the older file"
    )
    assert _ids(seen.data, "pages") == {str(workflow.page.pk)}

    stranger = await _run(guest({str(uuid.uuid4()): []}), LISTS)
    assert stranger.data == {"files": [], "documents": [], "pages": []}, (
        "another key sees nothing of it"
    )


async def test_a_document_of_an_older_file_comes_along_once_that_file_is_shared(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    workflow = await _workflow(authenticated_context)
    key = str(uuid.uuid4())
    await _member(SHARE, input={"collaboration": key, "rootTask": workflow.root})

    await _member(
        ADD,
        input={
            "collaboration": key,
            "identifier": "@dokuments/file",
            "object": str(workflow.older.file.pk),
        },
    )
    again = await _member(
        SHARE, input={"collaboration": key, "rootTask": workflow.root}
    )

    report = again["shareWorkflow"]
    assert isinstance(report, dict)
    assert report["skipped"] == []
    assert report["covered"] == 3, "both documents and the page, with their files"
    seen = await _run(guest({key: []}), LISTS)
    assert seen.data is not None
    assert _ids(seen.data, "documents") == {
        str(workflow.document.pk),
        str(workflow.document_of_older.pk),
        str(workflow.older.document.pk),
    }


async def test_lists_filter_by_the_workflow_that_made_them_and_by_collaboration(
    authenticated_context: HttpContext,
) -> None:
    workflow = await _workflow(authenticated_context)
    key = str(uuid.uuid4())
    under = {"createdUnder": workflow.root}

    made = await _member(LISTS, files=under, documents=under, pages=under)

    assert _ids(made, "files") == {str(workflow.file.pk)}
    assert _ids(made, "documents") == {
        str(workflow.document.pk),
        str(workflow.document_of_older.pk),
    }
    assert _ids(made, "pages") == {str(workflow.page.pk)}

    inside = {"inCollaboration": key}
    nothing_yet = await _member(LISTS, files=inside, documents=inside, pages=inside)
    assert all(nothing_yet[f] == [] for f in ("files", "documents", "pages"))

    await _member(SHARE, input={"collaboration": key, "rootTask": workflow.root})
    shared = await _member(LISTS, files=inside, documents=inside, pages=inside)

    assert _ids(shared, "files") == {str(workflow.file.pk)}
    assert _ids(shared, "documents") == {str(workflow.document.pk)}, (
        "a part of what was put in is in it, live"
    )
    assert _ids(shared, "pages") == {str(workflow.page.pk)}
    both = await _member(
        LISTS,
        files={"createdUnder": workflow.root, "inCollaboration": key},
        documents={"inCollaboration": key, "ids": [str(workflow.document_of_older.pk)]},
    )
    assert _ids(both, "files") == {str(workflow.file.pk)}
    assert both["documents"] == []


async def test_another_organization_shares_nothing_of_this_workflow(
    authenticated_context: HttpContext,
) -> None:
    workflow = await _workflow(authenticated_context)

    tried = await _run(
        token_context("othertest"),
        SHARE,
        input={
            "collaboration": str(uuid.uuid4()),
            "rootTask": workflow.root,
            "dryRun": True,
        },
    )

    assert not tried.errors, tried.errors
    assert tried.data is not None
    report = tried.data["shareWorkflow"]
    assert report["added"] == [] and report["skipped"] == []


async def test_what_dokuments_does_not_host_is_never_shared(
    authenticated_context: HttpContext,
) -> None:
    """The dataset a file is filed in (a default one is made with it) is no structure: a workflow
    share leaves it out, and nobody can put it in by hand."""
    workflow = await _workflow(authenticated_context)
    assert workflow.file.dataset_id is not None
    key = str(uuid.uuid4())

    await _member(SHARE, input={"collaboration": key, "rootTask": workflow.root})
    put = await _run(
        token_context("test"),
        ADD,
        input={
            "collaboration": key,
            "identifier": "@dokuments/dataset",
            "object": str(workflow.file.dataset_id),
        },
    )

    assert put.errors, "a dataset was put in a collaboration"
    held = {
        identifier
        async for identifier in CollaborationItem.objects.filter(
            collaboration__key=key
        ).values_list("content_type__model", flat=True)
    }
    assert held == {"file", "mediastore"}, held
