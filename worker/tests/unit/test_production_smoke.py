from __future__ import annotations

import urllib.error

import pytest
from scripts import production_smoke


def test_production_smoke_retries_transient_pages_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[object] = [
        urllib.error.HTTPError("https://preview.example/release.json", 522, "transient", {}, None),
        {"release_id": "fixture-release"},
    ]
    sleeps: list[float] = []

    def fake_get_json(_url: str) -> dict[str, object]:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, dict)
        return response

    monkeypatch.setattr(production_smoke, "get_json", fake_get_json)
    monkeypatch.setattr(production_smoke.time, "sleep", sleeps.append)

    result = production_smoke.get_json_with_retry(
        "https://preview.example/release.json",
        attempts=3,
        initial_delay_seconds=0.25,
    )

    assert result == {"release_id": "fixture-release"}
    assert sleeps == [0.25]


def test_production_smoke_stops_after_retry_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_url: str) -> dict[str, object]:
        raise TimeoutError("not ready")

    monkeypatch.setattr(production_smoke, "get_json", fail)
    monkeypatch.setattr(production_smoke.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="could not be reached"):
        production_smoke.get_json_with_retry(
            "https://preview.example/release.json",
            attempts=2,
            initial_delay_seconds=0,
        )
