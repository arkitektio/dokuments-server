from enum import Enum

import strawberry


@strawberry.enum
class RenderNodeKind(str, Enum):
    CONTEXT = "context"
    OVERLAY = "overlay"
    GRID = "grid"
    SPIT = "split"
