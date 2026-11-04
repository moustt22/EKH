"""Upload the fictional Northwind library through the API.

Usage: python scripts/load_dataset.py
"""

import json
import os
from pathlib import Path

import httpx
import pymupdf

API = os.environ.get("EKH_API_URL", "http://localhost:8000")
PASSWORD = "ChangeMe123!"
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "dataset" / "manifest.json"


def main() -> None:
    with httpx.Client(base_url=API, timeout=60) as client:
        departments = _departments(client, _login(client, "admin@northwind.example"))
        hr = _login(client, "hr.manager@northwind.example")
        admin = _login(client, "admin@northwind.example")
        documents = [
            _upload(
                client,
                hr,
                title="Salary bands",
                department_id=departments["HR"],
                classification="confidential",
                access_scope="department",
                filename="salary-bands.pdf",
                text=(
                    "Confidential salary bands for annual compensation. "
                    "Engineering band E3 is 90000 to 120000. "
                    "This document is visible to HR only."
                ),
            ),
            _upload(
                client,
                hr,
                title="Leave policy",
                department_id=departments["HR"],
                classification="internal",
                access_scope="department",
                filename="leave-policy.pdf",
                text="Employees accrue 20 days of leave. Unused leave does not roll past 5 days.",
            ),
            _upload(
                client,
                admin,
                title="On-call guide",
                department_id=departments["Engineering"],
                classification="internal",
                access_scope="department",
                filename="on-call.pdf",
                text="The engineering on-call rotation is weekly. The primary responder acknowledges pages within 15 minutes.",
            ),
            _upload(
                client,
                admin,
                title="Office hours",
                department_id=departments["Engineering"],
                classification="internal",
                access_scope="department",
                filename="office-hours.pdf",
                text="The engineering office opens at 9. The quiet hours for incident work are 18 to 20.",
            ),
        ]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(documents, indent=2), encoding="utf-8")
    print(json.dumps(documents, indent=2))


def _login(client: httpx.Client, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    response.raise_for_status()
    return response.json()["access_token"]


def _departments(client: httpx.Client, token: str) -> dict[str, str]:
    response = client.get("/departments", headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return {item["name"]: item["id"] for item in response.json()}


def _upload(client: httpx.Client, token: str, **fields: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    existing = client.get("/documents", headers=headers)
    existing.raise_for_status()
    for document in existing.json():
        if document["title"] == fields["title"]:
            return {"title": fields["title"], "document_id": document["id"], "status": document["status"]}
    response = client.post(
        "/documents",
        headers=headers,
        data={
            "title": fields["title"],
            "department_id": fields["department_id"],
            "classification": fields["classification"],
            "access_scope": fields["access_scope"],
        },
        files={"file": (fields["filename"], _pdf(fields["text"]), "application/pdf")},
    )
    response.raise_for_status()
    body = response.json()
    return {"title": fields["title"], "document_id": body["document_id"], "status": body["status"]}


def _pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    data = document.tobytes()
    document.close()
    return data


if __name__ == "__main__":
    main()
