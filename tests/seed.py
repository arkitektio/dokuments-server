"""Files, documents and pages of the test organization, made directly in the database."""

import uuid
from dataclasses import dataclass

from arkitekt_datalayer.models import MediaStore
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from core import models


def store(context: HttpContext, name: str) -> MediaStore:
    """A finished media store of the context's organization (no object behind it)."""
    key = uuid.uuid4().hex
    return MediaStore.objects.create(
        organization=context.request.organization,
        path=f"s3://media/{key}",
        key=key,
        bucket="media",
        original_file_name=name,
        content_type="application/pdf",
        populated=True,
    )


@dataclass(frozen=True)
class Seeded:
    """A file, one document read from it, and that document's pages, each with its own image."""

    file: models.File
    document: models.Document
    pages: list[models.Page]


def _seed(context: HttpContext, title: str, pages: int) -> Seeded:
    file = models.File.objects.create(
        name=f"{title}.pdf",
        store=store(context, f"{title}.pdf"),
        creator=context.request.user,
        organization=context.request.organization,
    )
    document = models.Document.objects.create(file=file, title=title)
    made = [
        models.Page.objects.create(
            document=document,
            index=index,
            content=f"{title} page {index}",
            image=store(context, f"{title}-{index}.png"),
        )
        for index in range(pages)
    ]
    return Seeded(file=file, document=document, pages=made)


@sync_to_async
def seed(context: HttpContext, title: str, pages: int = 2) -> Seeded:
    """A file named ``title`` with one document of ``pages`` pages."""
    return _seed(context, title, pages)


@sync_to_async
def add_page(
    context: HttpContext, document: models.Document, index: int
) -> models.Page:
    """A page added to ``document``, with an image of its own."""
    return models.Page.objects.create(
        document=document,
        index=index,
        content=f"added page {index}",
        image=store(context, f"added-{index}.png"),
    )
