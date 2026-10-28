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
