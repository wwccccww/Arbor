from fastapi.testclient import TestClient

from apps.api.main import create_app


def _headers(token="token-a"):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }


LINXIA = "0a000000-0000-4000-a000-000000000010"


def test_import_file_then_get_job():
    client = TestClient(create_app(), raise_server_exceptions=False)
    uploaded = client.post(
        f"/v1/personas/{LINXIA}/imports",
        headers=_headers(),
        files={"file": ("notes.txt", "林夏讨厌香菜".encode(), "text/plain")},
        data={"hint": "taboo"},
    )
    assert uploaded.status_code == 202
    job_id = uploaded.json()["job_id"]
    assert uploaded.json()["status"] == "completed"
    job = client.get(f"/v1/imports/{job_id}", headers=_headers())
    assert job.status_code == 200
    assert job.json()["filename"] == "notes.txt"
    assert job.json()["status"] == "completed"
    assert uploaded.json()["inbox_created"] == 1
    assert job.json()["inbox_created"] == 1


def test_import_hidden_without_write_memory():
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.post(
        f"/v1/personas/{LINXIA}/imports",
        headers=_headers("token-member"),
        files={"file": ("notes.txt", b"secret", "text/plain")},
    )
    assert r.status_code in {403, 404}


def test_import_text_goes_to_inbox_not_memory():
    client = TestClient(create_app(), raise_server_exceptions=False)
    text = "导入后才该确认的新事实xyz"
    before = {
        item["text"]
        for item in client.get(f"/v1/personas/{LINXIA}/memories", headers=_headers()).json()["items"]
    }
    uploaded = client.post(
        f"/v1/personas/{LINXIA}/imports",
        headers=_headers(),
        files={"file": ("notes.txt", text.encode(), "text/plain")},
        data={"hint": "fact"},
    )
    assert uploaded.status_code == 202
    assert uploaded.json()["inbox_created"] == 1
    inbox = client.get(f"/v1/personas/{LINXIA}/inbox", headers=_headers())
    assert inbox.status_code == 200
    payloads = [item["payload"]["text"] for item in inbox.json()["items"]]
    assert text in payloads
    after = {
        item["text"]
        for item in client.get(f"/v1/personas/{LINXIA}/memories", headers=_headers()).json()["items"]
    }
    assert text not in after
    assert after == before
    inbox_id = next(item["id"] for item in inbox.json()["items"] if item["payload"]["text"] == text)
    confirmed = client.post(f"/v1/inbox/{inbox_id}/confirm", headers=_headers())
    assert confirmed.status_code == 200
    remembered = {
        item["text"]
        for item in client.get(f"/v1/personas/{LINXIA}/memories", headers=_headers()).json()["items"]
    }
    assert text in remembered
