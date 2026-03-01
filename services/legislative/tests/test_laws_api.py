"""
立法サービス: 法・法体系参照 API のテスト（Issue #20）。
GENESIS 投入後、LAWSET-AMATERRACE@1 と CONST@1 が参照可能であることを検証する。
"""
import pytest
from rest_framework.test import APIClient

from laws.models import LAW_ID_CONST, LAWSET_ID_AMATERRACE


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_law_detail_const_exists(api_client):
    """GET /laws/CONST/ で憲法が取得できる（GENESIS）。"""
    response = api_client.get(f"/laws/{LAW_ID_CONST}/")
    assert response.status_code == 200
    data = response.json()
    assert data["law_id"] == LAW_ID_CONST
    assert data["law_version"] == 1
    assert "憲法" in data["title"] or "GENESIS" in data["title"]
    assert "text" in data


@pytest.mark.django_db
def test_law_detail_with_version_param(api_client):
    """GET /laws/CONST/?version=1 で version 指定で取得できる。"""
    response = api_client.get(f"/laws/{LAW_ID_CONST}/", {"version": "1"})
    assert response.status_code == 200
    assert response.json()["law_version"] == 1


@pytest.mark.django_db
def test_law_detail_not_found(api_client):
    """存在しない law_id は 404。"""
    response = api_client.get("/laws/NONEXISTENT/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_lawset_current_returns_amateras(api_client):
    """GET /lawsets/current/ で LAWSET-AMATERRACE の最新版が取得できる。"""
    response = api_client.get("/lawsets/current/")
    assert response.status_code == 200
    data = response.json()
    assert data["lawset_id"] == LAWSET_ID_AMATERRACE
    assert data["version"] >= 1
    assert "digest_hash" in data
    assert "laws" in data
    assert any(l["law_id"] == LAW_ID_CONST for l in data["laws"])
