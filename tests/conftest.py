"""Domain fixtures for the suite. The backing services come from the repo-root
``conftest.py`` so that ``core/tests/`` gets them too.
"""

import pytest


def _context(token: str, sub: str, org_slug: str):  # noqa: ANN202
    from authentikate.models import Client, Membership, Organization, User
    from kante.context import HttpContext, UniversalRequest
    from strawberry.http.temporal_response import TemporalResponse

    user, _ = User.objects.get_or_create(sub=sub, iss="static_issuer", defaults={"username": f"static_issuer_{sub}"})
    client, _ = Client.objects.get_or_create(client_id="dokuments-test")
    org, _ = Organization.objects.get_or_create(identifier=f"static_issuer#{org_slug}")
    membership, _ = Membership.objects.update_or_create(user=user, organization=org, defaults={"roles": ["editor"]})
    request = UniversalRequest(_extensions={"token": token}, _client=client, _user=user, _organization=org)  # type: ignore[arg-type]
    request.set_membership(membership)  # type: ignore[arg-type]
    return HttpContext(request=request, response=TemporalResponse(), headers={"Authorization": f"Bearer {token}"}, type="http")


@pytest.fixture(scope="function")
def other_org_context(db, backend_stack):
    """An editor of ``other_org``: the static ``othertest`` token's identity."""
    return _context("othertest", "9", "other_org")


@pytest.fixture(scope="function")
def authenticated_context(db, backend_stack):
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
