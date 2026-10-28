import pytest
from app.db import SessionLocal
from app import models
from app.auth import hash_password
from app.services.questions import questions_for
from tests.conftest import login


def _setup_test_org(org_name, dept_data):
    """
    dept_data: dict of {dept_name: list of dicts:
        {"email": ..., "role": ..., "job_role": ..., "seniority": ..., "completed": bool, "flags": list}}
    """
    db = SessionLocal()
    org = models.Organization(name=org_name)
    db.add(org)
    db.flush()

    admin_email = f"admin@{org_name.lower().replace(' ', '')}.test"
    admin_user = models.User(name="Admin", email=admin_email, password_hash=hash_password("pulse123"))
    db.add(admin_user)
    db.flush()
    db.add(models.Membership(user_id=admin_user.id, org_id=org.id, role="admin", job_role="manager", seniority="lead"))

    for dept_name, members in dept_data.items():
        dept = models.Department(org_id=org.id, name=dept_name)
        db.add(dept)
        db.flush()

        for m_info in members:
            u = models.User(name=m_info["email"], email=m_info["email"], password_hash=hash_password("pulse123"))
            db.add(u)
            db.flush()
            membership = models.Membership(
                user_id=u.id, org_id=org.id, department_id=dept.id,
                role=m_info.get("role", "employee"),
                job_role=m_info.get("job_role", "engineering"),
                seniority=m_info.get("seniority", "mid"),
            )
            db.add(membership)
            db.flush()

            qs = questions_for(membership.job_role, membership.seniority)
            if m_info.get("completed", False):
                for idx, q in enumerate(qs):
                    flags = m_info.get("flags", []) if idx == 0 else []
                    db.add(models.Response(
                        membership_id=membership.id, question_id=q["id"],
                        answer="Sensitive employee raw answer with secret token xyz.",
                        score=3.5, flags=flags,
                    ))

    db.commit()
    db.close()
    return admin_email, org_name


def test_insights_requires_admin_authorization(client):
    # Non-admin employee receives 403 Forbidden
    headers_emp, _ = login(client, "vikram@northwind.test", "Northwind Logistics")
    r_emp = client.get("/insights", headers=headers_emp)
    assert r_emp.status_code == 403

    # Admin receives 200 OK
    headers_admin, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    r_admin = client.get("/insights", headers=headers_admin)
    assert r_admin.status_code == 200


def test_insights_tenant_isolation(client):
    # Admin of Northwind Logistics cannot view Bluepeak Retail insights
    headers_admin, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    r = client.get("/insights?org_id=2", headers=headers_admin)
    assert r.status_code in (200, 403)
    if r.status_code == 200:
        # Organization must be strictly scoped to the token's active org
        assert r.json()["organization"] == "Northwind Logistics"


def test_insights_input_minimization(client, monkeypatch):
    # Verify that the LLM/insights generation service receives ONLY approved aggregate data
    # and NEVER receives raw text, employee names, emails, or membership IDs.
    captured_payloads = []

    from app.services import insights_service

    orig_generate = insights_service.generate_insights
    def spy_generate(visible_data):
        captured_payloads.append(visible_data)
        return orig_generate(visible_data)

    monkeypatch.setattr(insights_service, "generate_insights", spy_generate)

    from app import seed
    seed.run(expanded=True)
    try:
        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get("/insights", headers=headers)
        assert r.status_code == 200

        assert len(captured_payloads) == 1
        payload = captured_payloads[0]
        # Payload must be a list of aggregate department dicts
        for dept in payload:
            # Must NOT contain raw employee data or IDs
            assert "raw_answers" not in dept
            assert "answers" not in dept
            assert "user_id" not in dept
            assert "membership_id" not in dept
            assert "email" not in dept
            assert "name" not in dept
            # Must only contain safe aggregate fields
            assert "department" in dept
            assert "average_score" in dept
            assert "level" in dept
            assert "risk_counts" in dept

        # Check payload string representation doesn't leak raw text or emails
        payload_str = str(payload)
        assert "@" not in payload_str
        assert "Sensitive employee" not in payload_str
        assert "Copilot" not in payload_str
    finally:
        seed.run(expanded=False)


def test_insights_suppressed_department_exclusion(client):
    # Suppressed departments (< 5 completed members) must never appear in insights or leak their risks
    admin_email, org_name = _setup_test_org("InsightsKAnonOrg", {
        "VisibleEngineering": [
            {"email": f"vis{i}@test.com", "completed": True, "flags": ["unreviewed_output"]}
            for i in range(5)
        ],
        "SuppressedSecretDept": [
            {"email": f"sup{i}@test.com", "completed": True, "flags": ["confidential_data_shared"]}
            for i in range(2)
        ]
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/insights", headers=headers)
    assert r.status_code == 200
    data = r.json()

    departments_in_insights = {item["department"] for item in data["insights"]}
    assert "SuppressedSecretDept" not in departments_in_insights

    # Risks exclusive to suppressed departments must NOT appear in any recommendation
    patterns_and_actions = " ".join([
        item["observed_pattern"] + " " + item["recommended_action"] + " " + item["reason"]
        for item in data["insights"]
    ])
    assert "confidential_data_shared" not in patterns_and_actions
    assert "Confidential" not in patterns_and_actions


def test_insights_output_validation(client):
    # Validates schema structure, bounded string lengths, and whitelist priorities
    from app import seed
    seed.run(expanded=True)
    try:
        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get("/insights", headers=headers)
        assert r.status_code == 200
        data = r.json()

        assert "organization" in data
        assert "insights" in data
        assert "source" in data
        assert isinstance(data["insights"], list)

        for item in data["insights"]:
            assert isinstance(item["department"], str)
            assert isinstance(item["observed_pattern"], str)
            assert isinstance(item["recommended_action"], str)
            assert isinstance(item["reason"], str)
            assert item["priority"] in {"high", "medium", "low"}
            assert 0 < len(item["observed_pattern"]) <= 500
            assert 0 < len(item["recommended_action"]) <= 500
            assert 0 < len(item["reason"]) <= 500
    finally:
        seed.run(expanded=False)


def test_insights_llm_failure_handling(client, monkeypatch):
    # Proves system falls back to deterministic rule-based insights without crashing on LLM errors
    from app.services import llm
    def broken_llm(*args, **kwargs):
        raise RuntimeError("External AI provider timeout 504")

    monkeypatch.setattr(llm, "score_answer", broken_llm)

    from app import seed
    seed.run(expanded=True)
    try:
        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get("/insights", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data["insights"]) > 0
        assert data["source"] == "rules"
    finally:
        seed.run(expanded=False)

