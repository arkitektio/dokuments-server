from kante.types import Info
import strawberry
from core import types, models, scalars
from core.mutations.file import organization_store
from core.ocr.inputs import OCRPageResultInput


@strawberry.input()
class CreatePageInput:
    image: scalars.FileLike
    index: int
    document: strawberry.ID
    ocr_result: OCRPageResultInput
    content: str | None = None


def create_page(
    info: Info,
    input: CreatePageInput,
) -> types.Page:
    document = models.Document.objects.get(id=input.document, file__organization=info.context.request.organization)
    page = models.Page.objects.create(index=input.index, document=document, image=organization_store(info, str(input.image)), ocr_result=strawberry.asdict(input.ocr_result), content=input.content)

    return page
