from __future__ import annotations

import pytest
from scripts.check_reviewer_access import validate_access_redirect


def test_accepts_cloudflare_access_login_redirect() -> None:
    validate_access_redirect(
        302,
        "https://insparian.cloudflareaccess.com/cdn-cgi/access/login/app-id?token=x",
        "insparian.cloudflareaccess.com",
    )


@pytest.mark.parametrize(
    ("status", "location"),
    [
        (200, None),
        (302, "https://reviewer.example.com/login"),
        (302, "https://evil-cloudflareaccess.com/cdn-cgi/access/login/app"),
        (302, "https://other.cloudflareaccess.com/cdn-cgi/access/login/app"),
    ],
)
def test_rejects_public_or_untrusted_response(status: int, location: str | None) -> None:
    with pytest.raises(RuntimeError):
        validate_access_redirect(status, location, "insparian.cloudflareaccess.com")


def test_rejects_invalid_expected_team_host() -> None:
    with pytest.raises(RuntimeError):
        validate_access_redirect(
            302,
            "https://insparian.cloudflareaccess.com/cdn-cgi/access/login/app-id",
            "https://insparian.cloudflareaccess.com",
        )
