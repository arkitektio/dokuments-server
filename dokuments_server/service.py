"""dokuments as a service of the hub: the models behind what its contract says it hosts.

What exists here is declared once, as data, in ``dokuments_server.contract`` (``hosts``); this module
binds each structure to its model. A structure the contract declares that nothing binds here stops
the service at its start (``service.urls``). Nothing is announced: dokuments declares no signals.

Collaborations: a file is what is put in one. Its documents are part of it (their required, cascading
``file``), and their pages part of them, so they are in the collaboration with it, live. What else a
file needs to be seen is its stored bytes and the image of every page read from it (``depends``).

What a workflow (a root task) created is read off ``created_through``, which the create mutations
stamp from the request's provenance token: every structure here can say.
"""

from arkitekt_datalayer.models import MediaStore
from arkitekt_service.collaborations import items as collaboration_items
from arkitekt_service.service import Service
from django.db.models import Model
from django.db.models.signals import post_save

from core import models
from dokuments_server.contract import contract

service = Service(
    "dokuments",
    hosts=contract.description.hosts,
    description="Documents, their pages and their text.",
)


def _file_needs(file: models.File) -> list[Model | None]:
    """The store holding a file's bytes, and the image of every page of its documents."""
    images = MediaStore.objects.filter(pages__document__file=file).distinct()
    return [file.store, *images]


file = service.structure(models.File, "@dokuments/file", depends=_file_needs)
document = service.structure(models.Document, "@dokuments/document")
page = service.structure(models.Page, "@dokuments/page")

# A page is its document's: its image is what it shows, not a whole it is part of (a store may be
# the image of pages in other documents, or the file itself).
service.not_part_of(models.Page, "image")


def _page_saved(
    sender: type[models.Page], instance: models.Page, raw: bool = False, **_: object
) -> None:
    """A page added to a document of a file in a collaboration brings its image into it."""
    if not raw:
        collaboration_items.refresh(instance.document.file)


post_save.connect(
    _page_saved, sender=models.Page, dispatch_uid="dokuments-collaborations-page"
)
