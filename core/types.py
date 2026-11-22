import strawberry
import strawberry_django
from strawberry import auto
from typing import Optional
from django.db.models import QuerySet
from kante.types import Info
from core import models, filters
import datetime
from enum import Enum
from arkitekt_datalayer import types as dtypes
from authentikate.strawberry.types import User
from core.ocr.object import OCRPageResult, OCRPageResultModel


@strawberry.enum
class ViewKind(str, Enum):
    """The kind of view.

    Views can be of different kinds. For example, a view can be a label view
    that will map a labeleling agent (e.g. an antibody) to a specific image channel.

    Depending on the kind of view, different fields will be available.

    """

    TIMEPOINT = "timepoint_views"


def scope_to_organization(queryset: QuerySet, info: Info, path: str) -> QuerySet:
    """Keep only the rows of the caller's organization, reached through ``path``.

    strawberry_django runs a type's ``get_queryset`` for root lists, single ``x: T = field()``
    fetches and nested relations alike, so routing every type here scopes every read of it.
    """
    return queryset.filter(**{path: info.context.request.organization})


@strawberry_django.type(models.File, filters=filters.FileFilter, pagination=True)
class File:
    id: auto
    name: auto
    store: dtypes.MediaStore | None
    documents: list["Document"] = strawberry_django.field(
        description="The documents that reference this file",
    )

    @classmethod
    def get_queryset(cls, queryset: QuerySet[models.File], info: Info, **kwargs: object) -> QuerySet[models.File]:
        return scope_to_organization(queryset, info, "organization")


@strawberry_django.type(models.Dataset, filters=filters.DatasetFilter, pagination=True)
class Dataset:
    id: auto
    name: auto
    description: auto
    creator: User
    created_at: datetime.datetime
    updated_at: datetime.datetime
    pinned: bool = strawberry.field(description="Whether the dataset is pinned.")


@strawberry_django.type(models.Document, filters=filters.DocumentFilter, pagination=True)
class Document:
    """Document type."""

    id: strawberry.ID
    file: "File"
    title: str
    processed_at: Optional[str]
    pages: list["Page"] = strawberry_django.field(description="The document's pages, in reading order (by index).")

    @strawberry_django.field(description="How many pages the document has.")
    def page_count(self, root: models.Document) -> int:
        return root.pages.count()

    @classmethod
    def get_queryset(cls, queryset: QuerySet[models.Document], info: Info, **kwargs: object) -> QuerySet[models.Document]:
        return scope_to_organization(queryset, info, "file__organization")


@strawberry_django.type(models.Page, filters=filters.PageFilter, pagination=True)
class Page:
    id: strawberry.ID
    document: "Document"
    index: int
    image: dtypes.MediaStore
    content: str | None = strawberry.field(description="The content of the page as a flat string. Null when no text was recognised on it.")

    @strawberry_django.field
    def ocr_result(self) -> OCRPageResult | None:
        """Returns the OCR result for the page, or null when it was not recognised."""
        if self.ocr_result:
            return OCRPageResultModel(**self.ocr_result)
        return None

    @classmethod
    def get_queryset(cls, queryset: QuerySet[models.Page], info: Info, **kwargs: object) -> QuerySet[models.Page]:
        # Reading order: a document's pages by index (nested), and across documents by document.
        return scope_to_organization(queryset, info, "document__file__organization").order_by("document_id", "index", "id")
