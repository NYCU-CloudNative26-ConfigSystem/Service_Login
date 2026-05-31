"""Tests for the internal service-to-service endpoint."""
import pytest
from app.core.config import settings

ENDPOINT = "/internal/users/emails"


class TestInternalEndpoint:
    def test_returns_503_when_key_not_configured(self, client, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_key", "")
        res = client.post(ENDPOINT, json={"user_ids": []}, headers={"x-internal-key": ""})
        assert res.status_code == 503

    def test_returns_401_on_wrong_key(self, client, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_key", "correct-key")
        res = client.post(ENDPOINT, json={"user_ids": []}, headers={"x-internal-key": "wrong-key"})
        assert res.status_code == 401

    def test_returns_empty_list_for_unknown_users(self, client, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_key", "test-key")
        res = client.post(ENDPOINT,
            json={"user_ids": ["nobody"]},
            headers={"x-internal-key": "test-key"})
        assert res.status_code == 200
        assert res.json() == []

    def test_returns_empty_list_for_no_user_ids(self, client, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_key", "test-key")
        res = client.post(ENDPOINT,
            json={"user_ids": []},
            headers={"x-internal-key": "test-key"})
        assert res.status_code == 200
        assert res.json() == []

    def test_returns_email_for_registered_user(self, client, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_key", "test-key")
        client.post("/api/v1/auth/register", json={
            "email": "internal@example.com",
            "username": "internaluser",
            "password": "securepass123",
            "company": "TestCo",
        })
        res = client.post(ENDPOINT,
            json={"user_ids": ["internaluser"]},
            headers={"x-internal-key": "test-key"})
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["user_id"] == "internaluser"
        assert data[0]["email"] == "internal@example.com"

    def test_returns_multiple_users(self, client, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_key", "test-key")
        for i in range(3):
            client.post("/api/v1/auth/register", json={
                "email": f"multi{i}@example.com",
                "username": f"multiuser{i}",
                "password": "securepass123",
                "company": "TestCo",
            })
        res = client.post(ENDPOINT,
            json={"user_ids": ["multiuser0", "multiuser1", "multiuser2"]},
            headers={"x-internal-key": "test-key"})
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 3
        returned_ids = {d["user_id"] for d in data}
        assert returned_ids == {"multiuser0", "multiuser1", "multiuser2"}
