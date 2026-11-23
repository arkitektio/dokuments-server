"""Domain fixtures for the suite. The backing services come from the repo-root
``conftest.py`` so that ``core/tests/`` gets them too.
"""

from collections.abc import Callable, Iterator, Mapping

import pytest
from authentikate import settings as authentikate_settings
from kante.context import HttpContext, UniversalRequest
from pytest_django.fixtures import Settings as SettingsWrapper
from strawberry.http.temporal_response import TemporalResponse

#: ``guest({key: roles})``: a request presenting a guest granted those collaborations.
GuestFactory = Callable[[Mapping[str, list[str]]], HttpContext]


def token_context(token: str, task: str | None = None) -> HttpContext:
    """A request presenting the static token ``token``, as a client sends it: nothing resolved yet.

    ``task`` is a provenance token, sent in the ``Rekuest-Task`` header as an agent does for the
    task it runs.
    """
    headers = {"Authorization": f"Bearer {token}"}
    if task is not None:
        headers["Rekuest-Task"] = task
    return HttpContext(
        request=UniversalRequest(_extensions={}),
        response=TemporalResponse(),
        headers=headers,
        type="http",
    )


@pytest.fixture
def guest(
    db: None, authenticated_context: HttpContext, settings: SettingsWrapper
) -> Iterator[GuestFactory]:
    """``guest({key: roles})``: a context presenting a guest of the test organization (sub 20),
    granted those collaborations by their key, as lok lists them in the token's ``collabs``."""

    def mint(collaborations: Mapping[str, list[str]]) -> HttpContext:
        settings.AUTHENTIKATE = {
            **settings.AUTHENTIKATE,
            "static_tokens": {
                **settings.AUTHENTIKATE["static_tokens"],
                "guest": {
                    "sub": "20",
                    "roles": [],
                    "collabs": dict(collaborations),
                    "scope": "openid dokuments_all",
                },
            },
        }
        authentikate_settings.cached_settings = None
        return token_context("guest")

    yield mint
    authentikate_settings.cached_settings = None


def _context(token: str, sub: str, org_slug: str) -> HttpContext:
    from authentikate.models import Client, Membership, Organization, User
    from kante.context import HttpContext, UniversalRequest
    from strawberry.http.temporal_response import TemporalResponse

    user, _ = User.objects.get_or_create(
        sub=sub, iss="static_issuer", defaults={"username": f"static_issuer_{sub}"}
    )
    client, _ = Client.objects.get_or_create(client_id="dokuments-test")
    org, _ = Organization.objects.get_or_create(identifier=f"static_issuer#{org_slug}")
    membership, _ = Membership.objects.update_or_create(
        user=user, organization=org, defaults={"roles": ["dokuments_editor"]}
    )
    request = UniversalRequest(
        _extensions={"token": token},
        _client=client,  # type: ignore[arg-type]
        _user=user,  # type: ignore[arg-type]
        _organization=org,  # type: ignore[arg-type]
    )
    request.set_membership(membership)  # type: ignore[arg-type]
    return HttpContext(
        request=request,
        response=TemporalResponse(),
        headers={"Authorization": f"Bearer {token}"},
        type="http",
    )


@pytest.fixture(scope="function")
def other_org_context(db: None, backend_stack: tuple[int, int]) -> HttpContext:
    """An editor of ``other_org``: the static ``othertest`` token's identity."""
    return _context("othertest", "9", "other_org")


@pytest.fixture(scope="function")
def authenticated_context(db: None, backend_stack: tuple[int, int]) -> HttpContext:
    """A context whose identity matches what the static "test" token resolves to.

    The schema's authentikate extension authenticates as that identity at resolve
    time, so an ad-hoc user here would leave organization-scoped queries seeing no
    data. dokuments' Dataset and File both carry a non-null organization, so the
    membership matters.
    """
    from authentikate.models import Client, Membership, Organization, User
    from kante.context import HttpContext, UniversalRequest
    from strawberry.http.temporal_response import TemporalResponse

    user, _ = User.objects.get_or_create(
        sub="1", iss="static_issuer", defaults={"username": "static_issuer_1"}
    )
    client, _ = Client.objects.get_or_create(client_id="dokuments-test")
    org, _ = Organization.objects.get_or_create(identifier="static_issuer#static_org")
    membership, _ = Membership.objects.get_or_create(user=user, organization=org)

    request = UniversalRequest(
        _extensions={"token": "test"},
        _client=client,  # type: ignore[arg-type]
        _user=user,  # type: ignore[arg-type]
        _organization=org,  # type: ignore[arg-type]
    )
    request.set_membership(membership)  # type: ignore[arg-type]

    return HttpContext(
        request=request,
        response=TemporalResponse(),
        headers={"Authorization": "Bearer test"},
        type="http",
    )
