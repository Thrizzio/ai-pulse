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


def test_insights_unauthenticated_request_rejected(client):
    # Proves unauthenticated request is rejected with 401 Unauthorized
    r = client.get("/insights")
    assert r.status_code == 401


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


def test_insights_insufficient_eligible_data_produces_empty_result(client):
    # Standard seed has only small teams (< 5 completed respondents), resulting in empty insights and hidden_small_groups True
    headers_asha, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    r = client.get("/insights", headers=headers_asha)
    assert r.status_code == 200
    data = r.json()
    assert data["insights"] == []
    assert data["hidden_small_groups"] is True


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


def test_insights_malformed_and_invalid_priority_rejected(client, monkeypatch):
    # Proves malformed items or unsupported priorities (e.g. "critical") are rejected without fabricating findings
    from app.services import insights_service
    import httpx

    class FakeResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": '{"insights": ['
                                   '{"department": "Engineering", "observed_pattern": "Valid pattern", "recommended_action": "Valid action", "reason": "Valid reason", "priority": "critical"},'
                                   '{"department": "Engineering", "observed_pattern": "Another pattern", "recommended_action": "Another action", "reason": "Another reason", "priority": "high"}'
                                   ']}'
                    }
                }]
            }

    monkeypatch.setattr(insights_service, "AI_MODE", "live")
    monkeypatch.setattr(insights_service, "LLM_API_KEY", "fake-key")
    monkeypatch.setattr(insights_service, "LLM_API_URL", "https://fake.llm/v1")
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeResponse())

    from app import seed
    seed.run(expanded=True)
    try:
        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get("/insights", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "ai"
        # The item with invalid priority "critical" was rejected, leaving only the "high" priority item
        assert len(data["insights"]) == 1
        assert data["insights"][0]["priority"] == "high"
    finally:
        seed.run(expanded=False)


def test_insights_llm_failure_handling(client, monkeypatch):
    # Proves system falls back to deterministic rule-based insights without crashing on LLM errors
    from app.services import insights_service
    import httpx

    def broken_post(*args, **kwargs):
        raise httpx.ConnectTimeout("External AI provider timeout 504")

    monkeypatch.setattr(insights_service, "AI_MODE", "live")
    monkeypatch.setattr(insights_service, "LLM_API_KEY", "fake-key")
    monkeypatch.setattr(insights_service, "LLM_API_URL", "https://fake.llm/v1")
    monkeypatch.setattr(httpx, "post", broken_post)

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


def test_admin_can_access_insights_for_eligible_department(client):
    # Proves admin can fetch department-specific insights for an eligible (k >= 5) department
    from app import seed
    seed.run(expanded=True)
    try:
        db = SessionLocal()
        eng_dept = db.query(models.Department).filter_by(name="Engineering").first()
        dept_id = eng_dept.id
        db.close()

        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get(f"/insights?department_id={dept_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["department_id"] == dept_id
        assert data["department"] == "Engineering"
        assert len(data["insights"]) > 0
        for it in data["insights"]:
            assert it["department"] == "Engineering"
    finally:
        seed.run(expanded=False)


def test_admin_cannot_access_insights_for_suppressed_department(client):
    # Proves suppressed departments (< 5 completed respondents) cannot retrieve insights (403 Forbidden)
    from app import seed
    seed.run(expanded=True)
    try:
        db = SessionLocal()
        # Customer Success at Apex has only 2 completed respondents (< 5)
        cs_dept = db.query(models.Department).filter_by(name="Customer Success").first()
        cs_id = cs_dept.id
        db.close()

        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get(f"/insights?department_id={cs_id}", headers=headers)
        assert r.status_code == 403
        assert "suppressed" in r.json()["detail"].lower() or "not eligible" in r.json()["detail"].lower()
    finally:
        seed.run(expanded=False)


def test_admin_cannot_access_cross_tenant_department_insights(client):
    # Proves admin of Apex Global cannot access department insights for Crestline Health
    from app import seed
    seed.run(expanded=True)
    try:
        db = SessionLocal()
        crest_dept = db.query(models.Department).filter_by(name="Clinical Operations").first()
        crest_dept_id = crest_dept.id
        db.close()

        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get(f"/insights?department_id={crest_dept_id}", headers=headers)
        assert r.status_code == 403
        assert "another organization" in r.json()["detail"].lower()
    finally:
        seed.run(expanded=False)


def test_non_admin_cannot_access_department_insights(client):
    # Proves employee cannot access department insights endpoint
    from app import seed
    seed.run(expanded=True)
    try:
        db = SessionLocal()
        eng_dept = db.query(models.Department).filter_by(name="Engineering").first()
        dept_id = eng_dept.id
        db.close()

        headers, _ = login(client, "priyanka@apex.test", "Apex Global")
        r = client.get(f"/insights?department_id={dept_id}", headers=headers)
        assert r.status_code == 403
        assert "admins only" in r.json()["detail"].lower()
    finally:
        seed.run(expanded=False)


def test_department_insights_receives_only_requested_department_data(client, monkeypatch):
    # Proves LLM / service receives ONLY the requested department's aggregate data, not other departments
    captured_payloads = []
    from app.services import insights_service
    orig_gen = insights_service.generate_insights

    def spy_gen(depts):
        captured_payloads.append(depts)
        return orig_gen(depts)

    monkeypatch.setattr(insights_service, "generate_insights", spy_gen)

    from app import seed
    seed.run(expanded=True)
    try:
        db = SessionLocal()
        eng_dept = db.query(models.Department).filter_by(name="Engineering").first()
        dept_id = eng_dept.id
        db.close()

        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get(f"/insights?department_id={dept_id}", headers=headers)
        assert r.status_code == 200

        assert len(captured_payloads) == 1
        payload = captured_payloads[0]
        # Must contain ONLY 1 department, and it must be Engineering
        assert len(payload) == 1
        assert payload[0]["department"] == "Engineering"
        assert "Product" not in [d["department"] for d in payload]
    finally:
        seed.run(expanded=False)


def test_department_insights_malformed_llm_response_falls_back(client, monkeypatch):
    # Proves that unparseable non-JSON LLM responses safely fallback to rule-based insights
    from app.services import insights_service
    import httpx

    class FakeGarbageResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "Sorry, I cannot produce valid JSON today."}}]}

    monkeypatch.setattr(insights_service, "AI_MODE", "live")
    monkeypatch.setattr(insights_service, "LLM_API_KEY", "fake-key")
    monkeypatch.setattr(insights_service, "LLM_API_URL", "https://fake.llm/v1")
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeGarbageResponse())

    from app import seed
    seed.run(expanded=True)
    try:
        db = SessionLocal()
        eng_dept = db.query(models.Department).filter_by(name="Engineering").first()
        dept_id = eng_dept.id
        db.close()

        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get(f"/insights?department_id={dept_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "rules"
        assert len(data["insights"]) > 0
        assert data["department"] == "Engineering"
    finally:
        seed.run(expanded=False)


def test_other_teams_insights_suppresses_rare_risks_for_sparse_groups(client):
    # Proves that for Other teams with < 5 respondents, rare risks (count < 2) are suppressed,
    # while shared risks (count >= 2) generate privacy-safe aggregate recommendations.
    admin_email, org_name = _setup_test_org("OtherSparseOrg", {
        "SmallDept1": [
            {"email": "sd1_a@sparse.test", "completed": True, "flags": ["customer_data_shared", "policy_unaware"]},
            {"email": "sd1_b@sparse.test", "completed": True, "flags": []},
        ],
        "SmallDept2": [
            {"email": "sd2_a@sparse.test", "completed": True, "flags": ["policy_unaware"]},
        ],
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/insights?department_id=other", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["department"] == "Other teams"
    assert data["department_id"] == "other"

    # customer_data_shared was only flagged by 1 respondent (< 2) -> suppressed!
    # policy_unaware was flagged by 2 respondents (>= 2) -> retained!
    combined_text = " ".join([
        it["observed_pattern"] + " " + it["recommended_action"] + " " + it["reason"]
        for it in data["insights"]
    ])
    assert "policy" in combined_text.lower() or "acceptable-use" in combined_text.lower()
    assert "customer data shared" not in combined_text.lower()
    assert "client data" not in combined_text.lower()
    assert "SmallDept1" not in r.text
    assert "SmallDept2" not in r.text


def test_other_teams_insights_insufficient_data_shows_general_recommendation(client):
    # Proves that when small teams have insufficient/sparse risk data (e.g. N < 2),
    # a clear general governance recommendation is returned rather than specific individual risks.
    admin_email, org_name = _setup_test_org("OtherTinyOrg", {
        "TinyDept": [
            {"email": "tiny@tiny.test", "completed": True, "flags": ["confidential_data_shared"]},
        ],
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/insights?department_id=other", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["department"] == "Other teams"
    assert len(data["insights"]) > 0

    # General recommendation with low priority
    ins = data["insights"][0]
    assert ins["priority"] == "low"
    assert "sparse" in ins["observed_pattern"].lower() or "insufficient" in ins["observed_pattern"].lower()
    assert "confidential_data_shared" not in r.text
    assert "TinyDept" not in r.text


def test_other_teams_insights_prompt_input_minimization(client, monkeypatch):
    # Proves the insights service receives only the aggregate "Other teams" record
    # and NEVER individual department names, employee emails, or raw text.
    captured_payloads = []
    from app.services import insights_service
    orig_func = insights_service.generate_other_teams_insights

    def spy_func(target_dept):
        captured_payloads.append(target_dept)
        return orig_func(target_dept)

    monkeypatch.setattr(insights_service, "generate_other_teams_insights", spy_func)

    from app import seed
    seed.run(expanded=True)
    try:
        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get("/insights?department_id=other", headers=headers)
        assert r.status_code == 200

        assert len(captured_payloads) == 1
        payload = captured_payloads[0]
        assert payload["department"] == "Other teams"
        payload_str = str(payload)
        assert "Customer Success" not in payload_str
        assert "Legal & Compliance" not in payload_str
        assert "@" not in payload_str
    finally:
        seed.run(expanded=False)


def test_other_teams_insights_cross_tenant_isolation(client):
    # Proves admin of Org A cannot access Other teams insights of Org B
    from app import seed
    seed.run(expanded=True)
    try:
        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get("/insights?department_id=other&org_id=2", headers=headers)
        assert r.status_code == 403
        assert "another organization" in r.json()["detail"].lower()
    finally:
        seed.run(expanded=False)


def test_other_teams_insights_non_admin_rejected(client):
    # Proves non-admin employee cannot access Other teams insights
    from app import seed
    seed.run(expanded=True)
    try:
        headers, _ = login(client, "priyanka@apex.test", "Apex Global")
        r = client.get("/insights?department_id=other", headers=headers)
        assert r.status_code == 403
        assert "admins only" in r.json()["detail"].lower()
    finally:
        seed.run(expanded=False)
