import strawberry
from pydantic import BaseModel
from strawberry.experimental import pydantic as strawberry_pydantic


class OCRTextLineModel(BaseModel):
    text: str  # Recognized text string
    score: float  # Confidence score of recognition
    angle: float  # Detected rotation angle of the text line
    bbox: list[tuple[int, int]]  # Bounding box points (polygon of 4 coordinates)


class OCRPageResultModel(BaseModel):
    lines: list[OCRTextLineModel]  # List of recognized text lines


@strawberry_pydantic.input(OCRTextLineModel)
class OCRTextLineInput:
    text: str = strawberry.field(description="Recognized text string")
    score: float = strawberry.field(description="Confidence score of recognition")
    angle: float = strawberry.field(
        description="Detected rotation angle of the text line"
    )
    bbox: list[tuple[int, int]] = strawberry.field(
        description="Bounding box points (polygon of 4 coordinates)"
    )


@strawberry_pydantic.input(OCRPageResultModel)
class OCRPageResultInput:
    lines: list[OCRTextLineInput] = strawberry.field(
        description="List of recognized text lines"
    )
    angle: float = strawberry.field(description="Estimated rotation angle of the page")
