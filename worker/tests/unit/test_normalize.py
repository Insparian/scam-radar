from __future__ import annotations

import pytest

from scam_radar.normalize.text import normalize_text
from scam_radar.normalize.url import canonicalize_url


def test_url_removes_fragment_tracking_and_sorts_query() -> None:
    assert (
        canonicalize_url("HTTPS://Example.COM:443/a//b/?z=2&utm_source=x&a=1#part")
        == "https://example.com/a/b?a=1&z=2"
    )


def test_url_preserves_only_declared_meaningful_parameters() -> None:
    assert (
        canonicalize_url(
            "https://example.com/list?page=2&from=home&type=notice",
            {"page", "type"},
        )
        == "https://example.com/list?page=2&type=notice"
    )


def test_url_rejects_relative_value() -> None:
    with pytest.raises(ValueError, match="absolute"):
        canonicalize_url("/relative")


def test_text_normalizes_unicode_whitespace_and_masks_pii() -> None:
    result = normalize_text("ＡＢＣ   测试\n\n\n电话 13800138000，身份证 11010519491231002X")
    assert result.text.startswith("ABC 测试\n\n电话")
    assert "13800138000" not in result.text
    assert "11010519491231002X" not in result.text
    assert result.pii_masked


def test_text_caps_and_defangs_urls() -> None:
    result = normalize_text(
        "访问 https://bad.example/path " + "x" * 200, max_chars=80, defang_urls=True
    )
    assert result.truncated
    assert "hxxps://bad[.]example/path" in result.text
