"""Guard on who may talk to the local API.

Loopback is always allowed. LOLVOICE_TRUSTED_HOSTS widens that for the Docker
setup, where the browser arrives through the gateway address. Nothing else
should ever get through, and the token stays mandatory in every case.
"""

from __future__ import annotations

import pytest

from server import api


class _Client:
    def __init__(self, host: str) -> None:
        self.host = host


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"])
def test_loopback_is_allowed_without_configuration(monkeypatch, host):
    monkeypatch.delenv("LOLVOICE_TRUSTED_HOSTS", raising=False)
    assert api._is_loopback(_Client(host)) is True


@pytest.mark.parametrize("host", ["172.17.0.1", "192.168.1.50", "10.0.0.7", "8.8.8.8"])
def test_everything_else_is_refused_by_default(monkeypatch, host):
    monkeypatch.delenv("LOLVOICE_TRUSTED_HOSTS", raising=False)
    assert api._is_loopback(_Client(host)) is False


@pytest.mark.parametrize(
    ("host", "allowed"),
    [
        ("172.17.0.1", True),
        ("172.19.0.5", True),
        ("172.31.255.254", True),
        ("192.168.65.1", True),
        ("172.15.0.1", False),
        ("192.168.1.50", False),
        ("8.8.8.8", False),
    ],
)
def test_cidr_ranges_from_the_environment(monkeypatch, host, allowed):
    monkeypatch.setenv("LOLVOICE_TRUSTED_HOSTS", "172.16.0.0/12,192.168.65.0/24")
    assert api._is_loopback(_Client(host)) is allowed


def test_single_addresses_and_junk_entries(monkeypatch):
    monkeypatch.setenv("LOLVOICE_TRUSTED_HOSTS", " 10.1.2.3 , , not-an-address, 999.0.0.1/8 ")
    assert api._is_loopback(_Client("10.1.2.3")) is True
    assert api._is_loopback(_Client("10.1.2.4")) is False
    assert api._is_loopback(_Client("127.0.0.1")) is True


def test_widening_the_guard_does_not_waive_the_token(monkeypatch):
    monkeypatch.setenv("LOLVOICE_TRUSTED_HOSTS", "172.16.0.0/12")
    application = api.create_app(port=21500, token="secret-token")

    from fastapi.testclient import TestClient

    with TestClient(application) as client:
        assert client.get("/api/v1/status").status_code == 401
        assert client.get("/api/v1/status", headers={"X-Auth-Token": "nope"}).status_code == 401
        assert client.get("/api/v1/status", headers={"X-Auth-Token": "secret-token"}).status_code == 200
