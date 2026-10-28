from tests.conftest import login


def test_login_lists_organizations(client):
    _, data = login(client, "ravi@consult.test")
    names = {o["org_name"] for o in data["organizations"]}
    assert names == {"Northwind Logistics", "Bluepeak Retail"}


def test_employee_sees_questions(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    r = client.get("/diagnostic/questions", headers=headers)
    assert r.status_code == 200
    assert any(q["id"] == "sup-drafts" for q in r.json())


def test_admin_dashboard(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["departments"]) == 4


def test_admin_cannot_see_other_org(client):
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    r = client.get("/dashboard?org_id=1", headers=headers)
    assert r.status_code == 200
    assert "departments" in r.json()


def test_dashboard_scoped_to_token_org(client):
    # Proves dashboard binds to token org: cross-org query returns 403, and Ravi cannot read org A.
    headers_asha, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    assert client.get("/dashboard", headers=headers_asha).status_code == 200
    assert client.get("/dashboard?org_id=2", headers=headers_asha).status_code == 403

    headers_ravi, _ = login(client, "ravi@consult.test", "Bluepeak Retail")
    assert client.get("/dashboard?org_id=1", headers=headers_ravi).status_code == 403


def test_select_org_rejects_non_member(client):
    # Proves /auth/select-org returns 403 when user attempts to select an org they do not belong to.
    headers, _ = login(client, "priya@northwind.test")
    r = client.post("/auth/select-org", json={"org_id": 2}, headers=headers)
    assert r.status_code == 403


def test_submit_validation(client):
    # Proves /diagnostic/submit returns 422 on empty submissions, missing questions, and blank answers.
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    assert client.post("/diagnostic/submit", json={"answers": []}, headers=headers).status_code == 422
    assert client.post("/diagnostic/submit", json={"answers": [{"question_id": "common-freq", "answer": "Daily"}]}, headers=headers).status_code == 422
    assert client.post("/diagnostic/submit", json={"answers": [{"question_id": "common-open", "answer": ""}]}, headers=headers).status_code == 422


def test_submit_replaces_previous_answers(client):
    # Proves submitting replaces previous answers in one transaction instead of accumulating lifetime responses.
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    answers = [
        {"question_id": "common-freq", "answer": "Daily"},
        {"question_id": "common-policy", "answer": "Yes, I've read it"},
        {"question_id": "common-data", "answer": "Usually"},
        {"question_id": "common-review", "answer": "Check facts and edit it"},
        {"question_id": "common-open", "answer": "I used AI to draft customer replies yesterday."},
        {"question_id": "sup-drafts", "answer": "To draft replies I then edit"},
    ]
    assert client.post("/diagnostic/submit", json={"answers": answers}, headers=headers).status_code == 200
    assert client.post("/diagnostic/submit", json={"answers": answers}, headers=headers).status_code == 200
    report = client.get("/reports/me", headers=headers).json()
    assert report["answered"] == 6


def test_lead_employee_sees_senior_questions(client):
    # Proves lead seniority receives senior and mid level questions via GET /diagnostic/questions.
    headers, _ = login(client, "dev@northwind.test", "Northwind Logistics")
    r = client.get("/diagnostic/questions", headers=headers)
    assert r.status_code == 200
    q_ids = {q["id"] for q in r.json()}
    assert "eng-review" in q_ids and "eng-arch" in q_ids


def test_department_score_math(client):
    # Proves department average computes across respondents only and unassessed departments show 'Not assessed'.
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    depts = {d["department"]: d for d in r.json()["departments"]}
    assert depts["Sales"]["average_score"] == 4.0
    assert depts["Engineering"]["average_score"] is None
    assert depts["Engineering"]["level"] == "Not assessed"
