import pytest
from app.db import SessionLocal
from app import models
from app.auth import hash_password
from app.services.questions import questions_for
from tests.conftest import login


def _setup_org(org_name, dept_data):
    """
    dept_data: dict of {dept_name: list of dicts:
        {"email": ..., "role": ..., "job_role": ..., "seniority": ..., "completed": bool, "flags": list, "duplicate_responses": bool}}
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
                # Answer all questions
                for idx, q in enumerate(qs):
                    flags = m_info.get("flags", []) if idx == 0 else []
                    score = None if m_info.get("null_scores", False) else 4.0
                    db.add(models.Response(
                        membership_id=membership.id, question_id=q["id"],
                        answer="Completed answer with sufficient detail.", score=score, flags=flags,
                    ))
                if m_info.get("duplicate_responses", False):
                    # Add duplicate responses for the same member
                    for q in qs:
                        db.add(models.Response(
                            membership_id=membership.id, question_id=q["id"],
                            answer="Second attempt response.", score=4.0, flags=[],
                        ))
            elif m_info.get("partial", False):
                # Answer only 1 question (incomplete)
                if qs:
                    db.add(models.Response(
                        membership_id=membership.id, question_id=qs[0]["id"],
                        answer="Partial answer.", score=2.0, flags=[],
                    ))

    db.commit()
    db.close()
    return admin_email, org_name


def test_department_with_4_completed_members_is_suppressed(client):
    admin_email, org_name = _setup_org("KAnon-Org1", {
        "Sales": [{"email": f"s{i}@org1.test", "completed": True} for i in range(4)]
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    dept_names = [d["department"] for d in r.json()["departments"]]
    assert "Sales" not in dept_names


def test_department_with_exactly_5_completed_members_is_displayed(client):
    admin_email, org_name = _setup_org("KAnon-Org2", {
        "Support": [{"email": f"sup{i}@org2.test", "completed": True} for i in range(5)]
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    depts = {d["department"]: d for d in r.json()["departments"]}
    assert "Support" in depts
    assert depts["Support"]["responded"] == 5


def test_multiple_suppressed_departments_combined_into_other_teams(client):
    admin_email, org_name = _setup_org("KAnon-Org3", {
        "DeptA": [{"email": f"a{i}@org3.test", "completed": True} for i in range(3)],
        "DeptB": [{"email": f"b{i}@org3.test", "completed": True} for i in range(3)],
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    depts = {d["department"]: d for d in r.json()["departments"]}
    assert "DeptA" not in depts
    assert "DeptB" not in depts
    assert "Other teams" in depts
    assert depts["Other teams"]["responded"] == 6


def test_other_teams_with_fewer_than_5_completed_is_hidden_and_sets_flag(client):
    admin_email, org_name = _setup_org("KAnon-Org4", {
        "DeptA": [{"email": f"a{i}@org4.test", "completed": True} for i in range(2)],
        "DeptB": [{"email": f"b{i}@org4.test", "completed": True} for i in range(1)],
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    depts = {d["department"]: d for d in r.json()["departments"]}
    assert "Other teams" in depts
    other = depts["Other teams"]
    assert other["employees"] == 3
    assert other["responded"] == 3
    assert other["average_score"] == 4.0
    assert other["level"] == "Leader"
    assert other["id"] == "other"
    assert other["risk_counts"] == {}
    assert r.json()["hidden_small_groups"] is True


def test_other_teams_with_at_least_5_completed_is_displayed_as_aggregate(client):
    admin_email, org_name = _setup_org("KAnon-Org5", {
        "DeptA": [{"email": f"a{i}@org5.test", "completed": True} for i in range(2)],
        "DeptB": [{"email": f"b{i}@org5.test", "completed": True} for i in range(3)],
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    depts = {d["department"]: d for d in r.json()["departments"]}
    assert "Other teams" in depts
    assert depts["Other teams"]["responded"] == 5
    assert r.json().get("hidden_small_groups") is False


def test_risks_exclusive_to_suppressed_departments_do_not_appear_in_top_risks(client):
    admin_email, org_name = _setup_org("KAnon-Org6", {
        "BigDept": [{"email": f"big{i}@org6.test", "completed": True, "flags": ["customer_data_shared"]} for i in range(5)],
        "SmallDept": [{"email": f"small{i}@org6.test", "completed": True, "flags": ["confidential_data_shared"]} for i in range(2)],
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    flag_names = [f[0] for f in r.json()["top_risks"]]
    assert "customer_data_shared" in flag_names
    assert "confidential_data_shared" not in flag_names


def test_incomplete_diagnostics_do_not_count_as_completed(client):
    admin_email, org_name = _setup_org("KAnon-Org7", {
        "Engineering": [
            {"email": f"comp{i}@org7.test", "completed": True} for i in range(4)
        ] + [
            {"email": "incomp@org7.test", "completed": False, "partial": True}
        ]
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    dept_names = [d["department"] for d in r.json()["departments"]]
    assert "Engineering" not in dept_names


def test_repeated_responses_do_not_inflate_distinct_count(client):
    admin_email, org_name = _setup_org("KAnon-Org8", {
        "Analytics": [
            {"email": "dup@org8.test", "completed": True, "duplicate_responses": True}
        ] + [
            {"email": f"ana{i}@org8.test", "completed": True} for i in range(3)
        ]
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    dept_names = [d["department"] for d in r.json()["departments"]]
    assert "Analytics" not in dept_names


def test_completed_respondents_without_numeric_scores_count_toward_privacy_threshold(client):
    admin_email, org_name = _setup_org("KAnon-Org9", {
        "ScorelessDept": [
            {"email": f"noscore{i}@org9.test", "completed": True, "null_scores": True} for i in range(5)
        ]
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    depts = {d["department"]: d for d in r.json()["departments"]}
    assert "ScorelessDept" in depts
    assert depts["ScorelessDept"]["responded"] == 5
    assert depts["ScorelessDept"]["average_score"] is None
    assert depts["ScorelessDept"]["level"] == "Not assessed"


def test_suppressed_data_absent_from_api_payload(client):
    admin_email, org_name = _setup_org("KAnon-Org10", {
        "SmallDept": [{"email": f"s{i}@org10.test", "completed": True, "flags": ["confidential_data_shared"]} for i in range(3)]
    })
    headers, _ = login(client, admin_email, org_name)
    r = client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["departments"]) == 1
    assert body["departments"][0]["department"] == "Other teams"
    assert body["departments"][0]["employees"] == 3
    assert body["departments"][0]["responded"] == 3
    assert body["departments"][0]["average_score"] == 4.0
    assert body["departments"][0]["level"] == "Leader"
    assert body["departments"][0]["risk_counts"] == {}
    assert body["top_risks"] == []
    # Ensure raw payload string doesn't leak SmallDept or its confidential risk
    raw_text = r.text
    assert "SmallDept" not in raw_text
    assert "confidential_data_shared" not in raw_text

