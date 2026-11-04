from app.database.seed import DEMO_PASSWORD


def _login(client, email: str, password: str = DEMO_PASSWORD) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_read_profile(client):
    token = _login(client, "admin@northwind.example")
    response = client.get("/auth/me", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "administrator"
    assert body["department_name"] == "Management"
    assert body["is_active"] is True


def test_login_rejects_unknown_and_wrong_password(client):
    unknown = client.post(
        "/auth/login",
        json={"email": "nobody@northwind.example", "password": DEMO_PASSWORD},
    )
    wrong = client.post(
        "/auth/login",
        json={"email": "admin@northwind.example", "password": "not-the-password"},
    )
    assert unknown.status_code == 401
    assert wrong.status_code == 401


def test_employee_cannot_manage_users(client):
    token = _login(client, "eng.employee@northwind.example")
    response = client.post(
        "/users",
        headers=_auth(token),
        json={
            "name": "Blocked",
            "email": "blocked@northwind.example",
            "password": DEMO_PASSWORD,
            "department_id": "00000000-0000-0000-0000-000000000000",
            "role": "employee",
        },
    )
    assert response.status_code == 403


def test_admin_creates_user_and_deactivation_blocks_login(client):
    token = _login(client, "admin@northwind.example")
    headers = _auth(token)
    departments = client.get("/departments", headers=headers)
    assert departments.status_code == 200
    finance = next(item for item in departments.json() if item["name"] == "Finance")

    created = client.post(
        "/users",
        headers=headers,
        json={
            "name": "Finance Analyst",
            "email": "finance.analyst@northwind.example",
            "password": DEMO_PASSWORD,
            "department_id": finance["id"],
            "role": "employee",
        },
    )
    assert created.status_code == 201
    assert created.json()["department_name"] == "Finance"

    duplicate = client.post(
        "/users",
        headers=headers,
        json={
            "name": "Finance Analyst",
            "email": "finance.analyst@northwind.example",
            "password": DEMO_PASSWORD,
            "department_id": finance["id"],
            "role": "employee",
        },
    )
    assert duplicate.status_code == 409

    user_id = created.json()["id"]
    updated = client.patch(f"/users/{user_id}", headers=headers, json={"is_active": False})
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    blocked = client.post(
        "/auth/login",
        json={"email": "finance.analyst@northwind.example", "password": DEMO_PASSWORD},
    )
    assert blocked.status_code == 401


def test_logout_requires_a_token(client):
    token = _login(client, "hr.manager@northwind.example")
    assert client.post("/auth/logout", headers=_auth(token)).status_code == 204
    assert client.post("/auth/logout").status_code == 401


def test_ready_uses_the_database(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}
