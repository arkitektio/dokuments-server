import strawberry
import strawberry_django
from strawberry import auto
from typing import Optional
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


@strawberry_django.type(models.File, filters=filters.FileFilter, pagination=True)
class File:
    id: auto
    name: auto
    store: dtypes.MediaStore | None
    documents: list["Document"] = strawberry_django.field(
        description="The documents that reference this file",
    )


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
    page_count: Optional[int]
    ocr_engine: str
    processed_at: Optional[str]
    pages: list["Page"]


@strawberry_django.type(models.Page, filters=filters.PageFilter, pagination=True)
class Page:
    id: strawberry.ID
    document: "Document"
    index: int
    image: dtypes.MediaStore
    content: str = strawberry.field(description="The content of the page as a flat string.")

    @strawberry_django.field
    def ocr_result(self) -> OCRPageResult:
        """Returns the OCR result for the page."""
        if self.ocr_result:
            return OCRPageResultModel(**self.ocr_result)
        return None
