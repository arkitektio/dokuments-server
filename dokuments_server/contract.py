"""What this image answers a hub's installer: ``arkitekt-service <verb>`` (see ``arkitekt_service.contract``).

The installer knows the hub; how this release spells its config is written here, with the
settings it is read by. A key renamed in ``configuration.py`` is renamed in :func:`render` in
the same commit, and no installer has to learn of it.
"""

from __future__ import annotations

from arkitekt_service.contract import JSON, Contract, Description, Facts, Job, Needs, Offers, Role, Scope, Start, blocks

from dokuments_server.configuration import Settings

#: What an app may do here on a user's behalf: defined at the coordination server when the hub
#: enrols. Every root field of the schema asks for one of them (`AuthExtension(scopes=...)`).
SCOPES = [
    Scope(key="dokuments_read", description="Read documents, their pages and their extracted text."),
    Scope(key="dokuments_write", description="Upload documents and add or change their pages and text."),
    Scope(key="dokuments_all", description="Do everything in Dokuments on your behalf.", is_all_scope=True),
]

#: What a member of an organization may do here.
ROLES = [
    Role(key="dokuments_admin", description="Full control of Dokuments in this organization.", is_admin_role=True),
    Role(key="dokuments_editor", description="Upload and change documents.", is_default_role=True),
]

#: The role every write asks for.
EDITOR = "dokuments_editor"
ADMIN = "dokuments_admin"


def render(facts: Facts) -> dict[str, JSON]:
    """This release's config for the hub ``facts`` describes."""
    document: dict[str, JSON] = blocks.server(facts)
    document["datalayer"] = blocks.datalayer(facts)
    return document


contract = Contract(
    description=Description(
        name="dokuments",
        identifier="live.arkitekt.dokuments",
        summary="Documents, their pages and their text.",
        needs=Needs(scopes=SCOPES, roles=ROLES, storage=["media"]),
        offers=Offers(),
    ),
    settings=Settings,
    render=render,
    # How this service is started: there is no script beside it. `arkitekt-service serve`
    # (and `debug`) become these, so they get the container's signals themselves.
    serve=Start(("daphne", "-b", "0.0.0.0", "-p", "80", "--websocket_timeout", "-1", "dokuments_server.asgi:application")),
    debug=Start(("python", "manage.py", "runserver", "0.0.0.0:80")),
    jobs={
        "ensureadmin": Job(("ensureadmin",), "Create the operator account the config names"),
    },
    setup=("ensureadmin",),
)
