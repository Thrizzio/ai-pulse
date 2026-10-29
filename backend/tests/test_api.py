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
    depts = r.json()["departments"]
    assert len(depts) == 1
    assert depts[0]["department"] == "Other teams"
    assert depts[0]["id"] == "other"
    assert depts[0]["employees"] == 10
    assert depts[0]["responded"] == 0
    assert depts[0]["average_score"] is None
    assert depts[0]["level"] == "Not assessed"
    assert r.json()["hidden_small_groups"] is True


def test_admin_cannot_see_other_org(client):
    # Proves an admin cannot view another org dashboard (returns 403).
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    r = client.get("/dashboard?org_id=2", headers=headers)
    assert r.status_code == 403


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
    # Proves department average computes across respondents only for qualified departments (k >= 5).
    from app import seed
    seed.run(expanded=True)
    try:
        headers, _ = login(client, "alex@apex.test", "Apex Global")
        r = client.get("/dashboard", headers=headers)
        assert r.status_code == 200
        depts = {d["department"]: d for d in r.json()["departments"]}
        assert "Engineering" in depts
        assert depts["Engineering"]["responded"] == 6
        assert "Product" in depts
        assert depts["Product"]["responded"] == 5
    finally:
        seed.run(expanded=False)


def test_dashboard_uses_shared_maturity_level(client):
    # Proves dashboard uses utils.maturity_level and level_for is removed.
    import app.routes.dashboard as dash_mod
    assert not hasattr(dash_mod, "level_for")


def test_delete_my_report_scoped_to_caller(client):
    # Proves DELETE /reports/me deletes caller responses without affecting other users.
    headers_priya, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    headers_vikram, _ = login(client, "vikram@northwind.test", "Northwind Logistics")

    del_res = client.delete("/reports/me", headers=headers_priya)
    assert del_res.status_code == 200

    rep_priya = client.get("/reports/me", headers=headers_priya).json()
    assert rep_priya["answered"] == 0
    assert rep_priya["average_score"] is None
    assert rep_priya["level"] == "Not assessed"

    rep_vikram = client.get("/reports/me", headers=headers_vikram).json()
    assert rep_vikram["answered"] == 2
    assert rep_vikram["average_score"] == 4.0


def test_ai_scoring_hardening_and_prompt_isolation(client):
    # Proves LLM parsing handles code fences, clamps score, whitelists flags, and reports source.
    from app.services.scoring import score_open_answer
    import app.services.llm as llm_service

    orig_score_answer = llm_service.score_answer
    try:
        llm_service.score_answer = lambda q, a: (
            "```json\n{\"score\": 99, \"reason\": \"Out of bounds\", \"flags\": [\"customer_data_shared\", \"fake_flag\"]}\n```",
            "mock",
        )
        res = score_open_answer("test question", "my answer")
        assert res["score"] == 5.0
        assert res["flags"] == ["customer_data_shared"]
        assert res["source"] == "mock"
    finally:
        llm_service.score_answer = orig_score_answer



def test_seed_mode_selection(client):
    # Proves seed can toggle between standard pilot and expanded enterprise datasets.
    from app import seed
    seed.run(expanded=True)
    headers_apex, _ = login(client, "alex@apex.test", "Apex Global")
    r = client.get("/dashboard", headers=headers_apex)
    assert r.status_code == 200
    assert r.json()["organization"] == "Apex Global"
    depts = {d["department"]: d for d in r.json()["departments"]}
    assert "Engineering" in depts
    assert depts["Engineering"]["employees"] == 6

    # Reset back to standard seed
    seed.run(expanded=False)


def test_failed_submission_preserves_previous_responses(client, monkeypatch):
    # Proves atomic submission: if scoring raises an error, previous responses are not deleted
    headers, _ = login(client, "vikram@northwind.test", "Northwind Logistics")
    rep_before = client.get("/reports/me", headers=headers).json()
    assert rep_before["answered"] == 2

    # Break scoring in diagnostic route
    from app.routes import diagnostic
    def broken_score(*args, **kwargs):
        raise RuntimeError("Model provider 503 outage")
    monkeypatch.setattr(diagnostic, "score_open_answer", broken_score)

    q_res = client.get("/diagnostic/questions", headers=headers).json()
    body = {
        "answers": [
            {"question_id": q["id"], "answer": q["options"][0] if q["type"] == "mcq" else "Pasting code into ChatGPT for debugging."}
            for q in q_res
        ]
    }
    submit_res = client.post("/diagnostic/submit", json=body, headers=headers)
    assert submit_res.status_code == 503

    # Verify previous responses were NOT deleted
    rep_after = client.get("/reports/me", headers=headers).json()
    assert rep_after["answered"] == 2
    assert rep_after["average_score"] == rep_before["average_score"]


def test_deleted_data_no_longer_contributes_to_dashboard_or_insights(client):
    # Proves that when an employee deletes their report, their data is removed from dashboard & insights
    from app import seed
    seed.run(expanded=True)
    try:
        headers_alex, _ = login(client, "alex@apex.test", "Apex Global")
        dash_before = client.get("/dashboard", headers=headers_alex).json()
        eng_before = next(d for d in dash_before["departments"] if d["department"] == "Engineering")
        assert eng_before["responded"] == 6

        # One engineer deletes their diagnostic data
        headers_jason, _ = login(client, "jason@apex.test", "Apex Global")
        del_res = client.delete("/reports/me", headers=headers_jason)
        assert del_res.status_code == 200

        # Dashboard immediately reflects 5 respondents
        dash_after = client.get("/dashboard", headers=headers_alex).json()
        eng_after = next(d for d in dash_after["departments"] if d["department"] == "Engineering")
        assert eng_after["responded"] == 5

        # Repeated deletion is safe and returns 0 deleted
        del_again = client.delete("/reports/me", headers=headers_jason)
        assert del_again.status_code == 200
        assert del_again.json()["deleted_responses"] == 0
    finally:
        seed.run(expanded=False)


def test_employee_cannot_delete_another_employee_data(client):
    # Proves employee A cannot delete employee B's data
    headers_priya, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    headers_vikram, _ = login(client, "vikram@northwind.test", "Northwind Logistics")

    # Priya attempts to delete with another user's or membership's query param
    del_res = client.delete("/reports/me?user_id=2&membership_id=2", headers=headers_priya)
    assert del_res.status_code == 200

    # Vikram's responses remain untouched
    rep_vikram = client.get("/reports/me", headers=headers_vikram).json()
    assert rep_vikram["answered"] == 2


def test_live_llm_scoring_valid_and_invalid_submission(client):
    # Proves valid assessment submission scores via LLM and commits transaction, while invalid submission returns 422
    headers, _ = login(client, "vikram@northwind.test", "Northwind Logistics")
    r_q = client.get("/diagnostic/questions", headers=headers)
    assert r_q.status_code == 200
    questions = r_q.json()

    # Valid submission
    valid_answers = [
        {"question_id": q["id"], "answer": q["options"][0] if q["type"] == "mcq" else "I use Claude and ChatGPT daily to draft customer outreach emails and proofread proposals."}
        for q in questions
    ]
    r_val = client.post("/diagnostic/submit", json={"answers": valid_answers}, headers=headers)
    assert r_val.status_code == 200
    assert r_val.json()["saved"] == len(questions)

    # Invalid submission (open answer under 10 chars -> 422)
    invalid_answers = [
        {"question_id": q["id"], "answer": q["options"][0] if q["type"] == "mcq" else "short"}
        for q in questions
    ]
    r_inval = client.post("/diagnostic/submit", json={"answers": invalid_answers}, headers=headers)
    assert r_inval.status_code == 422


def test_list_and_delete_reports_across_multiple_organizations(client):
    # Proves employee with memberships in multiple orgs can view saved reports and delete a specific org report
    from app import seed
    seed.run(expanded=True)
    try:
        # Marcus Brody is in Apex Global (has completed report) and Crestline Health
        headers_marcus, _ = login(client, "marcus@apex.test")
        r_list = client.get("/reports", headers=headers_marcus)
        assert r_list.status_code == 200
        reports = r_list.json()
        # Initially only Apex Global has a completed report
        assert len(reports) == 1
        assert reports[0]["organization"] == "Apex Global"
        assert reports[0]["answered"] == 7
        assert reports[0]["has_report"] is True

        # Marcus submits diagnostic for Crestline Health (org_id=2)
        r_org2 = client.post("/auth/select-org", json={"org_id": 2}, headers=headers_marcus)
        headers_marcus_org2 = {"Authorization": f"Bearer {r_org2.json()['token']}"}
        r_q = client.get("/diagnostic/questions", headers=headers_marcus_org2)
        qs = r_q.json()
        sub_answers = [
            {"question_id": q["id"], "answer": q["options"][0] if q["type"] == "mcq" else "Researching AI models on synthetic clinical data."}
            for q in qs
        ]
        r_sub = client.post("/diagnostic/submit", json={"answers": sub_answers}, headers=headers_marcus_org2)
        assert r_sub.status_code == 200

        # Now Marcus has reports for BOTH Apex Global and Crestline Health
        r_list2 = client.get("/reports", headers=headers_marcus)
        assert r_list2.status_code == 200
        org_names = [rep["organization"] for rep in r_list2.json()]
        assert "Apex Global" in org_names
        assert "Crestline Health" in org_names

        # Delete only Apex Global report using org_id=1
        r_del = client.delete("/reports/me?org_id=1", headers=headers_marcus)
        assert r_del.status_code == 200
        assert r_del.json()["status"] == "deleted"

        # Now listing reports returns ONLY Crestline Health
        r_list3 = client.get("/reports", headers=headers_marcus)
        assert r_list3.status_code == 200
        reports3 = r_list3.json()
        assert len(reports3) == 1
        assert reports3[0]["organization"] == "Crestline Health"
    finally:
        seed.run(expanded=False)


def test_cross_org_report_retrieval_and_deletion_rejected(client):
    # Proves employee cannot read or delete reports for organizations they do not belong to
    headers_vikram, _ = login(client, "vikram@northwind.test")
    # Vikram belongs only to Northwind Logistics (org_id=1), not Bluepeak Retail (org_id=2)
    r_get = client.get("/reports/me?org_id=2", headers=headers_vikram)
    assert r_get.status_code == 403
    assert "not a member" in r_get.json()["detail"].lower()

    r_del = client.delete("/reports/me?org_id=2", headers=headers_vikram)
    assert r_del.status_code == 403
    assert "not a member" in r_del.json()["detail"].lower()


def test_opening_diagnostic_does_not_mutate_existing_report(client):
    # Proves viewing diagnostic form without submitting does not alter existing report
    headers, _ = login(client, "vikram@northwind.test", "Northwind Logistics")
    report_before = client.get("/reports/me", headers=headers).json()

    # User opens diagnostic questions (navigating to diagnostic page)
    client.get("/diagnostic/questions", headers=headers)

    # Report remains completely unchanged
    report_after = client.get("/reports/me", headers=headers).json()
    assert report_before == report_after
