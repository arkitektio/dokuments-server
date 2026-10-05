"""What this image answers a hub's installer: ``python -m arkitekt_service <verb>`` (see ``arkitekt_service.contract``).

The installer knows the hub; how this release spells its config is written here, with the
settings it is read by. A key renamed in ``configuration.py`` is renamed in :func:`render` in
the same commit, and no installer has to learn of it.
"""

from __future__ import annotations

from arkitekt_service.contract import JSON, Contract, Description, Facts, Needs, Offers, Scope, blocks

from dokuments_server.configuration import Settings

#: What a token may be allowed to do here: defined at the coordination server when the hub enrols.
SCOPES = [
    Scope(key="dokuments_read", description="Read documents, their pages and their text"),
    Scope(key="dokuments_write", description="Add documents and write their pages and text"),
]


def render(facts: Facts) -> dict[str, JSON]:
    """This release's config for the hub ``facts`` describes."""
    document: dict[str, JSON] = blocks.server(facts)
    document["datalayer"] = blocks.datalayer(facts)
    return document


contract = Contract(
    description=Description(
        name="dokuments",
        summary="Documents, their pages and their text.",
        needs=Needs(scopes=SCOPES, storage=["media"]),
        offers=Offers(),
    ),
    settings=Settings,
    render=render,
)
