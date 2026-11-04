from app.database.seed import DEMO_PASSWORD
from app.services.chat import get_chat_client


def _login(client, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class QuietChat:
    def complete(self, messages):
        return '{"query": "salary bands"}'


def test_audit_records_login_without_the_password(client):
    failed = client.post("/auth/login", json={"email": "admin@northwind.example", "password": "wrong-password"})
    assert failed.status_code == 401
    admin = _login(client, "admin@northwind.example")
    rows = client.get("/audit", headers=_auth(admin))
    assert rows.status_code == 200
    denied = next(row for row in rows.json() if row["action"] == "login" and row["outcome"] == "denied")
    assert denied["actor_email"] == "admin@northwind.example"
    assert "wrong-password" not in str(denied)
    assert any(row["action"] == "login" and row["outcome"] == "allowed" for row in rows.json())


def test_employee_cannot_read_the_audit_log(client):
    engineer = _login(client, "eng.employee@northwind.example")
    assert client.get("/audit", headers=_auth(engineer)).status_code == 403


def test_search_and_assistant_rows_omit_document_text(client):
    admin = _login(client, "admin@northwind.example")
    searched = client.get("/search", params={"q": "salary bands"}, headers=_auth(admin))
    assert searched.status_code == 200
    client.app.dependency_overrides[get_chat_client] = lambda: QuietChat()
    created = client.post("/conversations", headers=_auth(admin), json={})
    posted = client.post(
        f"/conversations/{created.json()['id']}/messages",
        headers=_auth(admin),
        json={"content": "What are the salary bands?"},
    )
    assert posted.status_code == 200
    rows = client.get("/audit", headers=_auth(admin)).json()
    search_row = next(row for row in rows if row["action"] == "search")
    answer_row = next(row for row in rows if row["action"] == "assistant_response")
    assert search_row["detail"]["query"] == "salary bands"
    assert "snippet" not in search_row["detail"]
    assert "content" not in answer_row["detail"]
    assert posted.json()["content"] not in str(answer_row["detail"])
