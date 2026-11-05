"""Upload the fictional Northwind library through the API.

Each file is a multi-section handbook. Re-running replaces a document
that already has the same title.

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

LIBRARY = [
    {
        "title": "Salary bands",
        "department": "HR",
        "actor": "hr",
        "classification": "confidential",
        "access_scope": "department",
        "filename": "salary-bands.pdf",
        "sections": [
            (
                "Purpose",
                [
                    "Confidential salary bands for annual compensation. This handbook is the source HR uses when a manager asks where a role sits. It is not a promise of a raise, and it is not shared outside HR.",
                    "Figures are annual base pay in US dollars. They exclude bonus, commission, and the retirement match. A manager who quotes a number from memory should check this document first.",
                ],
            ),
            (
                "Engineering bands",
                [
                    "Engineering band E1 is 65000 to 80000 and is used for new graduates in their first year. Engineering band E2 is 78000 to 98000 for engineers who ship work with light review.",
                    "Engineering band E3 is 90000 to 120000. Most product engineers are hired into E3. A move from E2 to E3 requires two quarters of independent delivery and a written recommendation from the engineering manager.",
                    "Engineering band E4 is 115000 to 145000 for staff engineers who lead a system. Engineering band E5 is 140000 to 175000 and is reserved for people who set direction across more than one team.",
                ],
            ),
            (
                "Other departments",
                [
                    "HR band H2 is 70000 to 90000. Finance band F2 is 72000 to 95000, and finance band F3 is 94000 to 125000. Sales band S2 on-target earnings are 80000, split as 50000 base and 30000 variable.",
                    "Operations band O2 is 60000 to 78000. Management band M3, used for department managers, is 130000 to 160000. The chief of staff role in Management is paid on band M2, 105000 to 135000.",
                ],
            ),
            (
                "Review and bonus",
                [
                    "Compensation is reviewed every March. An employee already at the top of a band receives a bonus instead of a base increase. The standard bonus is 8 percent of base. Exceptional ratings can reach 12 percent, and that exception is signed by the HR director.",
                    "A promotion changes the band on the first day of the next month. It does not restart the March review. Offers more than 10 percent above the band midpoint need the administrator's approval before HR sends the letter.",
                ],
            ),
        ],
    },
    {
        "title": "Leave policy",
        "department": "HR",
        "actor": "hr",
        "classification": "internal",
        "access_scope": "department",
        "filename": "leave-policy.pdf",
        "sections": [
            (
                "Annual leave",
                [
                    "Employees accrue 20 days of leave. Accrual starts on the first day of work and is added each month as 1.67 days. New hires may use leave after 30 days.",
                    "Unused leave does not roll past 5 days. Anything above 5 days is cleared on 31 December. HR sends a balance to each manager in the first week of November so people can plan the remainder of the year.",
                ],
            ),
            (
                "Sick leave and family leave",
                [
                    "Sick leave is a separate balance of 10 days. It is not deducted from the 20 days of annual leave. A absence longer than 3 consecutive sick days needs a note from a clinician, sent to HR rather than to the manager.",
                    "Primary caregivers receive 16 weeks of paid parental leave. Secondary caregivers receive 6 weeks. Parental leave can start up to two weeks before the expected date and must be requested at least 30 days ahead when the date is known.",
                ],
            ),
            (
                "Holidays and how to ask",
                [
                    "Northwind closes on New Year's Day, Memorial Day, Independence Day, Labor Day, Thanksgiving and the Friday after it, and Christmas Day. These closures are not taken from the annual balance.",
                    "Leave of 1 or 2 days is approved by the department manager. Leave of 3 or more days is requested in the HR system at least 10 days ahead. HR confirms the balance before the manager approves a request that would take the balance below zero.",
                ],
            ),
        ],
    },
    {
        "title": "On-call guide",
        "department": "Engineering",
        "actor": "admin",
        "classification": "internal",
        "access_scope": "department",
        "filename": "on-call.pdf",
        "sections": [
            (
                "Rotation",
                [
                    "The engineering on-call rotation is weekly. It starts Monday at 10:00 local time and ends the following Monday at 10:00. The roster is published two weeks ahead in the engineering channel.",
                    "Each week has a primary and a secondary. The secondary is the person who was primary the week before. Swaps are allowed when both people agree and the engineering manager is told before Friday.",
                ],
            ),
            (
                "Response targets",
                [
                    "The primary responder acknowledges pages within 15 minutes. Acknowledgement means a reply in the incident channel, not a fix. If the primary has not replied in 15 minutes, the paging system calls the secondary.",
                    "Severity 1 is a customer-facing outage or data loss. Work starts immediately and the engineering manager is called within 30 minutes. Severity 2 is a degraded feature with a workaround, and a status note is posted within 1 hour. Severity 3 waits until the next business morning.",
                ],
            ),
            (
                "Escalation and handover",
                [
                    "The primary may page the service owner after 20 minutes of investigation. Database incidents also page the finance engineer on duty because the ledger service shares that cluster. Do not page the whole department.",
                    "Monday handover is a 15-minute call. The outgoing primary lists open incidents, noisy alerts that were silenced, and any password or certificate that expires in the next 14 days. The incoming primary reads that list before accepting the pager.",
                ],
            ),
        ],
    },
    {
        "title": "Office hours",
        "department": "Engineering",
        "actor": "admin",
        "classification": "internal",
        "access_scope": "department",
        "filename": "office-hours.pdf",
        "sections": [
            (
                "Building hours",
                [
                    "The engineering office opens at 9. The reception desk closes at 18:00, and the badge readers stay active until 21:00. Visitors sign in at reception and cannot be in the lab without an engineer.",
                    "The quiet hours for incident work are 18 to 20. During those two hours the incident room is reserved for the on-call pair. Other meetings move to the west hall or happen the next morning.",
                ],
            ),
            (
                "Focus and meetings",
                [
                    "Tuesday and Thursday afternoons are focus time. No recurring meeting is scheduled after 13:00 on those days. Stand-up stays at 9:30 and is 15 minutes. Design reviews are Wednesday at 11:00 and last 45 minutes.",
                    "A meeting with more than six people needs an agenda in the invite. Notes go in the engineering folder the same day. The author of a proposal, not the most senior person in the room, records the decision.",
                ],
            ),
            (
                "Remote days",
                [
                    "Engineers may work from home on Wednesday and Friday. Monday is an in-office day because the on-call handover is in person. Home-office equipment is a laptop, a headset, and one external display, requested through Operations.",
                    "Someone who will miss an in-office day tells the engineering manager by the previous afternoon. The lab cannot be used remotely. Production access from home still goes through the company VPN.",
                ],
            ),
        ],
    },
    {
        "title": "Expense policy",
        "department": "Finance",
        "actor": "admin",
        "classification": "internal",
        "access_scope": "department",
        "filename": "expense-policy.pdf",
        "sections": [
            (
                "Company cards",
                [
                    "Finance issues a company card to each department manager and to engineers who travel more than twice a quarter. Personal cards are reimbursed only when the company card was declined. The receipt is required either way.",
                    "A card charge over 500 is reviewed by Finance before the monthly statement closes. Charges without a receipt after 30 days are deducted from the next expense report and the cardholder is asked to explain them.",
                ],
            ),
            (
                "Meals and travel",
                [
                    "A client meal is capped at 75 per person. Alcohol is not reimbursed. Team meals in the office are capped at 25 per person and need the department manager's name on the receipt.",
                    "Flights under 5 hours are economy. Flights of 5 hours or more may be premium economy if the ticket is booked 14 days ahead. Hotels are capped at 220 per night before tax. A rental car needs a same-day client visit that is not reachable by train.",
                ],
            ),
            (
                "Approval",
                [
                    "Reports under 1000 are approved by the department manager. Reports of 1000 or more also need Finance. A report that includes a gift for a client is refused unless the general counsel has approved the gift in writing first.",
                    "Submit reports by the fifth business day of the next month. Finance pays approved reports on the following Friday. A report sent after the deadline waits until the next cycle.",
                ],
            ),
        ],
    },
    {
        "title": "Discount authority",
        "department": "Sales",
        "actor": "admin",
        "classification": "confidential",
        "access_scope": "department",
        "filename": "discount-authority.pdf",
        "sections": [
            (
                "Standard quotes",
                [
                    "List price is the price in the current rate card. A sales representative may discount up to 10 percent without approval. The discount is recorded on the quote, and the reason is one sentence.",
                    "Discounts are taken off the license fee. They are not taken off implementation, and they are not taken off the support plan. A quote that hides a discount inside a lower list price is sent back.",
                ],
            ),
            (
                "Approvals",
                [
                    "A discount from 11 percent to 20 percent needs the sales manager. A discount from 21 percent to 30 percent needs Finance as well. Anything above 30 percent is refused unless the administrator signs it, and that signature is rare.",
                    "Multi-year deals can add 2 percent for a two-year term and 4 percent for a three-year term. Those term discounts stack on top of the approved discount, but the combined figure still has to sit inside the same approval band.",
                ],
            ),
            (
                "What sales cannot offer",
                [
                    "Sales cannot promise a feature date, a custom security review, or free on-call coverage. Those requests go to Engineering in writing. A verbal promise in a call is not a commitment the company will honor.",
                    "Pilot projects last 30 days and are billed at 50 percent of the license fee. A pilot does not include a production migration. Extending a pilot past 30 days needs the sales manager.",
                ],
            ),
        ],
    },
    {
        "title": "Vendor intake",
        "department": "Operations",
        "actor": "admin",
        "classification": "internal",
        "access_scope": "department",
        "filename": "vendor-intake.pdf",
        "sections": [
            (
                "When a vendor is required",
                [
                    "A new vendor is required when Northwind will pay a company that is not already in the vendor list. Renewing an existing contract does not start a new intake. Buying a tool on a company card under 500 uses the expense policy instead.",
                    "The requesting department names an owner. The owner stays responsible for the vendor after the contract is signed, including the renewal date and the list of people who have accounts.",
                ],
            ),
            (
                "Review",
                [
                    "Operations checks the vendor's legal name, tax form, and bank details. A vendor that will see customer data also needs a security review. The security review takes 10 business days and is started by Operations, not by the requester.",
                    "Vendors with a contract value above 25000 need Finance and the department manager. Vendors above 100000 also need the administrator. Work does not start before the contract number is issued.",
                ],
            ),
            (
                "Payment and renewal",
                [
                    "Standard payment terms are net 30. A vendor that asks for payment on delivery is accepted only for goods, not for services. Operations enters the vendor in the ledger within 2 business days of the signed contract.",
                    "Renewal reminders go to the owner 60 days before the end date. If the owner does not reply within 15 days, Operations tells the department manager. A contract that auto-renews is marked in the vendor list in bold.",
                ],
            ),
        ],
    },
]


def main() -> None:
    with httpx.Client(base_url=API, timeout=120) as client:
        admin = _login(client, "admin@northwind.example")
        hr = _login(client, "hr.manager@northwind.example")
        departments = _departments(client, admin)
        tokens = {"admin": admin, "hr": hr}
        documents = [
            _replace(
                client,
                tokens[item["actor"]],
                title=item["title"],
                department_id=departments[item["department"]],
                classification=item["classification"],
                access_scope=item["access_scope"],
                filename=item["filename"],
                sections=item["sections"],
            )
            for item in LIBRARY
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


def _replace(client: httpx.Client, token: str, **fields: object) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    existing = client.get("/documents", headers=headers)
    existing.raise_for_status()
    for document in existing.json():
        if document["title"] == fields["title"]:
            deleted = client.delete(f"/documents/{document['id']}", headers=headers)
            deleted.raise_for_status()
    response = client.post(
        "/documents",
        headers=headers,
        data={
            "title": fields["title"],
            "department_id": fields["department_id"],
            "classification": fields["classification"],
            "access_scope": fields["access_scope"],
        },
        files={
            "file": (
                fields["filename"],
                _pdf(str(fields["title"]), fields["sections"]),
                "application/pdf",
            )
        },
    )
    response.raise_for_status()
    body = response.json()
    return {"title": str(fields["title"]), "document_id": body["document_id"], "status": body["status"]}


def _pdf(title: str, sections: list[tuple[str, list[str]]]) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    y = 72.0
    body = pymupdf.Font("helv")
    heading = pymupdf.Font("hebo")

    def new_page() -> None:
        nonlocal page, y
        page = document.new_page()
        y = 72.0

    def draw(text: str, font: pymupdf.Font, size: float, gap: float) -> None:
        nonlocal y
        for line in _wrap(text, font, size):
            if y > 760:
                new_page()
            page.insert_text((72, y), line, fontsize=size, fontname=font.name)
            y += gap

    draw(title, heading, 18, 28)
    for name, paragraphs in sections:
        y += 8
        draw(name, heading, 14, 20)
        for paragraph in paragraphs:
            draw(paragraph, body, 11, 15)
            y += 8
    data = document.tobytes()
    document.close()
    return data


def _wrap(text: str, font: pymupdf.Font, size: float, width: float = 460) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = word if not current else f"{current} {word}"
        if font.text_length(trial, fontsize=size) <= width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


if __name__ == "__main__":
    main()
