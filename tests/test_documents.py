from app.database.seed import DEMO_PASSWORD

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
OTHER_PDF = b"%PDF-1.4\n2 0 obj\n<<>>\nendobj\n%%EOF"
DOCX = b"PK\x03\x04docx-bytes"


def _login(client, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _department_id(client, token: str, name: str) -> str:
    response = client.get("/departments", headers=_auth(token))
    assert response.status_code == 200
    return next(item["id"] for item in response.json() if item["name"] == name)


def _upload(client, token: str, department_id: str, filename: str, content: bytes, **fields):
    data = {
        "department_id": department_id,
        "classification": fields.get("classification", "confidential"),
        "access_scope": fields.get("access_scope", "department"),
    }
    if "title" in fields:
        data["title"] = fields["title"]
    return client.post(
        "/documents",
        headers=_auth(token),
        data=data,
        files={"file": (filename, content, "application/octet-stream")},
    )


def test_upload_uses_filename_when_title_is_omitted(client):
    manager = _login(client, "hr.manager@northwind.example")
    hr_id = _department_id(client, manager, "HR")
    created = _upload(client, manager, hr_id, "leave_policy-v2.pdf", PDF)

    assert created.status_code == 202
    document = client.get(
        f"/documents/{created.json()['document_id']}",
        headers=_auth(manager),
    )
    assert document.status_code == 200
    assert document.json()["title"] == "leave policy v2"


def test_engineer_cannot_download_hr_document_but_owner_and_admin_can(client):
    manager = _login(client, "hr.manager@northwind.example")
    hr_id = _department_id(client, manager, "HR")
    created = _upload(client, manager, hr_id, "salary.pdf", PDF)
    assert created.status_code == 202
    body = created.json()
    assert body["status"] == "processing"
    assert body["version"] == 1
    document_id = body["document_id"]

    engineer = _login(client, "eng.employee@northwind.example")
    denied = client.get(f"/documents/{document_id}/download", headers=_auth(engineer))
    assert denied.status_code == 403
    assert denied.content == b'{"detail":"Not allowed"}'
    hidden = client.get("/documents", headers=_auth(engineer))
    assert hidden.status_code == 200
    assert all(item["id"] != document_id for item in hidden.json())

    owner_download = client.get(f"/documents/{document_id}/download", headers=_auth(manager))
    assert owner_download.status_code == 200
    assert owner_download.content == PDF

    admin = _login(client, "admin@northwind.example")
    admin_download = client.get(f"/documents/{document_id}/download", headers=_auth(admin))
    assert admin_download.status_code == 200
    assert admin_download.content == PDF


def test_employee_cannot_upload_and_manager_cannot_upload_outside_department(client):
    engineer = _login(client, "eng.employee@northwind.example")
    engineering_id = _department_id(client, engineer, "Engineering")
    rejected = _upload(client, engineer, engineering_id, "notes.pdf", PDF, title="Notes")
    assert rejected.status_code == 403

    manager = _login(client, "hr.manager@northwind.example")
    outside = _upload(client, manager, engineering_id, "notes.pdf", PDF, title="Notes")
    assert outside.status_code == 403


def test_duplicate_invalid_type_default_visibility_and_delete(client):
    manager = _login(client, "hr.manager@northwind.example")
    hr_id = _department_id(client, manager, "HR")
    first = _upload(client, manager, hr_id, "policy.docx", DOCX, title="Leave policy")
    assert first.status_code == 202
    duplicate = _upload(client, manager, hr_id, "policy-copy.docx", DOCX, title="Leave policy copy")
    assert duplicate.status_code == 409
    invalid = _upload(client, manager, hr_id, "notes.txt", b"hello", title="Notes")
    assert invalid.status_code == 400

    document_id = first.json()["document_id"]
    engineer = _login(client, "eng.employee@northwind.example")
    denied = client.get(f"/documents/{document_id}/download", headers=_auth(engineer))
    assert denied.status_code == 403

    assert client.delete(f"/documents/{document_id}", headers=_auth(engineer)).status_code == 403
    assert client.delete(f"/documents/{document_id}", headers=_auth(manager)).status_code == 204
    assert client.get(f"/documents/{document_id}", headers=_auth(manager)).status_code == 404


def test_new_version_replaces_the_download(client):
    admin = _login(client, "admin@northwind.example")
    finance_id = _department_id(client, admin, "Finance")
    created = _upload(client, admin, finance_id, "budget.pdf", PDF, title="Budget", classification="internal")
    assert created.status_code == 202
    document_id = created.json()["document_id"]
    updated = client.post(
        f"/documents/{document_id}/versions",
        headers=_auth(admin),
        files={"file": ("budget-v2.pdf", OTHER_PDF, "application/pdf")},
    )
    assert updated.status_code == 202
    assert updated.json()["version"] == 2
    download = client.get(f"/documents/{document_id}/download", headers=_auth(admin))
    assert download.status_code == 200
    assert download.content == OTHER_PDF
