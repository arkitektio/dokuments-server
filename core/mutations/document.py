import hashlib
import json

import strawberry
from kante.types import Info
from koherent.utils import get_or_create_task

from core import models, types


def hash_model(config: object) -> str:
    # Convert to dict, dump as sorted JSON string
    model_json = json.dumps(strawberry.asdict(config), sort_keys=True)
    return hashlib.sha256(model_json.encode("utf-8")).hexdigest()


@strawberry.input()
class CreateDocumentInput:
    file: strawberry.ID | None = None
    title: str


def create_document(
    info: Info,
    input: CreateDocumentInput,
) -> types.Document:
    document = models.Document.objects.create(
        title=input.title,
        file=models.File.objects.get(
            id=input.file, organization=info.context.request.organization
        ),
        created_through=get_or_create_task(),
    )

    return document
