# Changes Log

## Change 1: Repository Hygiene, Secret Management, Python Pinning & Docker Entrypoint

### Plain Language Explanation
1. **Untracked `backend/.env`:**
   Previously, the local configuration file containing secret keys and credentials (`backend/.env`) was actively tracked in Git. This was a critical security flaw because any commit would leak secret keys to version control. The file has now been untracked from Git index so local environment secrets remain private on developer machines, while `.gitignore` ensures it stays ignored.
2. **Added `.env.example`:**
   Because `.env` is untracked, new developers need a clean template showing which environment variables the application expects. Created `.env.example` (with placeholders for `SECRET_KEY`, `DATABASE_URL`, `AI_MODE`, `LLM_API_URL`, `LLM_API_KEY`, and `LLM_MODEL`) without exposing actual secrets.
3. **Pinned Python 3.12 in `.python-version`:**
   Python 3.14 breaks dependency installation due to Pydantic/pydantic-core compilation incompatibilities. Creating `.python-version` containing `3.12` ensures development environments, version managers (`pyenv`, `mise`, `asdf`), and CI tools automatically use the tested, stable Python 3.12 runtime.
4. **Fixed Dockerfile CMD:**
   The backend code lives inside the `app/` subfolder (entrypoint `app/main.py`). The Dockerfile previously had `CMD ["uvicorn", "main:app", ...]`, which failed at runtime because `/app/main.py` does not exist inside the container. It has been corrected to `CMD ["uvicorn", "app.main:app", ...]`.

---

### Before vs. After

| Item | Before | After |
|---|---|---|
| **Git Tracking of `backend/.env`** | `backend/.env` was tracked in Git (`git ls-files` returned `backend/.env`), risking credential leakage. | Untracked from Git index (`git rm --cached backend/.env`). Remains locally on disk and is ignored by `.gitignore`. |
| **Environment Template** | No `.env.example` existed in the repository. | Added `.env.example` and `backend/.env.example` with non-secret template configuration keys. |
| **Python Version** | No `.python-version` file existed; unpinned Python versions caused build failures on Python 3.14. | Added `.python-version` pinning `3.12`. |
| **Dockerfile Entrypoint** | `CMD ["uvicorn", "main:app", ...]` crashed with `ModuleNotFoundError: Could not import module "main"`. | `CMD ["uvicorn", "app.main:app", ...]` correctly targets the `app` package. |

---

### Git Diff

```diff
diff --git a/backend/.env b/backend/.env
deleted file mode 100644
index 518f4a3..0000000
--- a/backend/.env
+++ /dev/null
@@ -1,6 +0,0 @@
-SECRET_KEY=pulse-7f3a9c2e1b-prod
-DATABASE_URL=sqlite:///./aipulse.db
-AI_MODE=mock
-LLM_API_URL=
-LLM_API_KEY=
-LLM_MODEL=

diff --git a/backend/Dockerfile b/backend/Dockerfile
index 1b1cb48..774b099 100644
--- a/backend/Dockerfile
+++ b/backend/Dockerfile
@@ -3,4 +3,4 @@ WORKDIR /app
 COPY . .
 RUN pip install -r requirements.txt
 EXPOSE 8000
-CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
+CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

--- /dev/null
+++ b/.python-version
@@ -0,0 +1 @@
+3.12

--- /dev/null
+++ b/.env.example
@@ -0,0 +1,6 @@
+SECRET_KEY=dev-secret-change-in-production
+DATABASE_URL=sqlite:///./aipulse.db
+AI_MODE=mock
+LLM_API_URL=
+LLM_API_KEY=
+LLM_MODEL=

--- /dev/null
+++ b/backend/.env.example
@@ -0,0 +1,6 @@
+SECRET_KEY=dev-secret-change-in-production
+DATABASE_URL=sqlite:///./aipulse.db
+AI_MODE=mock
+LLM_API_URL=
+LLM_API_KEY=
+LLM_MODEL=
```

---

### Verification
Tests in `backend/tests/test_setup.py`:
- `test_python_version_pinned`: **PASSED**
- `test_env_example_exists`: **PASSED**
- `test_dockerfile_cmd_uses_app_main`: **PASSED**
- `test_backend_env_not_tracked_in_git`: **PASSED**



## Change 2: Bind /dashboard to Active Token Organization (Fix Cross-Tenant Access)

### Problem in One Line
The `/dashboard` endpoint accepted an unvalidated `org_id` query parameter, allowing admins to view other companies' dashboards and allowing multi-org users (like Ravi) to escalate privileges across organizations.

### Before and After Code (Key Lines)

#### `backend/app/routes/dashboard.py`
**Before:**
```python
@router.get("")
def org_dashboard(org_id: int, m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    if m.role != "admin":
        raise HTTPException(403, "Admins only")

    org = db.get(models.Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    members = db.query(models.Membership).filter_by(org_id=org_id).all()
```

**After:**
```python
@router.get("")
def org_dashboard(org_id: int | None = None, m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    if m.role != "admin":
        raise HTTPException(403, "Admins only")

    if org_id is not None and org_id != m.org_id:
        raise HTTPException(403, "Cannot view another organization's dashboard")

    target_org_id = m.org_id
    org = db.get(models.Organization, target_org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    members = db.query(models.Membership).filter_by(org_id=target_org_id).all()
```

#### `frontend/src/pages/Dashboard.jsx`
**Before:**
```javascript
  useEffect(() => {
    api(`/dashboard?org_id=${org.org_id}`).then(setData);
  }, [org]);
```

**After:**
```javascript
  useEffect(() => {
    api("/dashboard").then(setData);
  }, [org]);
```

### Manual Verification Steps
1. **Login as Asha and select Northwind Logistics:**
   - Call `POST /auth/login` with `{"email": "asha@northwind.test", "password": "pulse123"}`.
   - Call `POST /auth/select-org` with `{"org_id": 1}` to obtain scoped Bearer token.
2. **Access dashboard with no query parameter (`GET /dashboard`):**
   - *Before fix:* HTTP 422 Unprocessable Entity (FastAPI error: `org_id` query parameter required).
   - *After fix:* HTTP 200 OK returning Northwind Logistics dashboard.
3. **Attempt cross-tenant access to Bluepeak (`GET /dashboard?org_id=2` with Asha's token):**
   - *Before fix:* HTTP 200 OK returning Bluepeak Retail's confidential data.
   - *After fix:* HTTP 403 Forbidden with `{"detail": "Cannot view another organization's dashboard"}`.
4. **Login as Ravi and select Bluepeak Retail (where Ravi is an admin):**
   - Call `POST /auth/login` with `{"email": "ravi@consult.test", "password": "pulse123"}`.
   - Call `POST /auth/select-org` with `{"org_id": 2}` to obtain scoped Bearer token.
5. **Attempt to access Northwind data (`GET /dashboard?org_id=1` with Ravi's Bluepeak token):**
   - *Before fix:* HTTP 200 OK returning Northwind Logistics dashboard.
   - *After fix:* HTTP 403 Forbidden with `{"detail": "Cannot view another organization's dashboard"}`.


## Change 3: Membership Check in /auth/select-org (Reject Non-Member Org Selection)

### Problem in One Line
The `/auth/select-org` endpoint minted a signed JWT scoped to any requested `org_id` without checking if the authenticated user was actually a member of that organization.

### Before and After Code (Key Lines)

#### `backend/app/routes/auth_routes.py`
**Before:**
```python
@router.post("/select-org")
def select_org(body: SelectOrgIn, user: models.User = Depends(current_user)):
    # Issue a token scoped to the chosen organization
    return {"token": make_token(user.id, body.org_id), "org_id": body.org_id}
```

**After:**
```python
@router.post("/select-org")
def select_org(body: SelectOrgIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    membership = (
        db.query(models.Membership)
        .filter_by(user_id=user.id, org_id=body.org_id)
        .first()
    )
    if not membership:
        raise HTTPException(403, "Not a member of this organization")
    return {"token": make_token(user.id, body.org_id), "org_id": body.org_id}
```

### Manual Verification Steps
1. **Login as Priya (`priya@northwind.test`, password `pulse123`):**
   - Call `POST /auth/login` with `{"email": "priya@northwind.test", "password": "pulse123"}` $\rightarrow$ copy unscoped token.
2. **Select Priya's valid organization (Northwind Logistics, `org_id: 1`):**
   - Call `POST /auth/select-org` with `{"org_id": 1}` and `Authorization: Bearer <unscoped_token>`.
   - *Expected result (before and after fix):* HTTP 200 OK with scoped JWT.
3. **Attempt to select unauthorized organization (Bluepeak Retail, `org_id: 2`):**
   - Call `POST /auth/select-org` with `{"org_id": 2}` and `Authorization: Bearer <unscoped_token>`.
   - *Before fix:* HTTP 200 OK returning signed JWT claiming Priya is authorized for Bluepeak.
   - *After fix:* HTTP 403 Forbidden with `{"detail": "Not a member of this organization"}`.
4. **Login as multi-org user Ravi (`ravi@consult.test`, password `pulse123`):**
   - Call `POST /auth/login` with `{"email": "ravi@consult.test", "password": "pulse123"}`.
   - Call `POST /auth/select-org` with `{"org_id": 1}` $\rightarrow$ HTTP 200 OK.
   - Call `POST /auth/select-org` with `{"org_id": 2}` $\rightarrow$ HTTP 200 OK.
   - Call `POST /auth/select-org` with `{"org_id": 999}` $\rightarrow$ HTTP 403 Forbidden.


## Change 4: Server-Side Submission Validation in /diagnostic/submit

### Problem in One Line
The `/diagnostic/submit` endpoint accepted empty lists, partial submissions, blank answers, or short text, awarding scores without validating role requirements.

### Before and After Code (Key Lines)

#### `backend/app/routes/diagnostic.py`
**Before:**
```python
@router.post("/submit")
def submit(body: SubmitIn, m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    bank = {q["id"]: q for q in load_questions()}
    for a in body.answers:
        q = bank.get(a.question_id)
        if not q:
            raise HTTPException(400, f"Unknown question {a.question_id}")
        resp = models.Response(membership_id=m.id, question_id=q["id"], answer=a.answer)
        if q["type"] == "mcq":
            option = next((o for o in q["options"] if o["text"] == a.answer), None)
            if option is None:
                raise HTTPException(400, f"Invalid option for {q['id']}")
            resp.score = option["points"]
```

**After:**
```python
@router.post("/submit")
def submit(body: SubmitIn, m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    expected = questions_for(m.job_role, m.seniority)
    expected_map = {q["id"]: q for q in expected}

    submitted_ids = [a.question_id for a in body.answers]
    if len(submitted_ids) != len(expected_map) or set(submitted_ids) != set(expected_map.keys()):
        raise HTTPException(422, "All questions assigned to your role must be answered")

    for a in body.answers:
        q = expected_map[a.question_id]
        val = (a.answer or "").strip()
        if not val:
            raise HTTPException(422, f"Answer for '{q['id']}' cannot be blank")
        if q["type"] == "open" and len(val) < 10:
            raise HTTPException(422, f"Answer for '{q['id']}' must be at least 10 characters")
        if q["type"] == "mcq":
            option = next((o for o in q["options"] if o["text"] == a.answer), None)
            if option is None:
                raise HTTPException(422, f"Invalid option for {q['id']}")

    bank = expected_map
    for a in body.answers:
        q = bank.get(a.question_id)
        resp = models.Response(membership_id=m.id, question_id=q["id"], answer=a.answer.strip())
        ...
```

### Manual Verification Steps
1. **Sign in as Priya & select Northwind (`org_id: 1`):**
   - Call `POST /auth/login` with `{"email": "priya@northwind.test", "password": "pulse123"}` $\rightarrow$ copy token.
   - Call `POST /auth/select-org` with `{"org_id": 1}` $\rightarrow$ copy scoped token.
2. **Submit empty list of answers:**
   - POST `/diagnostic/submit` with `{"answers": []}` and `Authorization: Bearer <token>`.
   - *Before fix:* HTTP 200 OK `{"saved": 0}`.
   - *After fix:* HTTP 422 Unprocessable Entity `{"detail": "All questions assigned to your role must be answered"}`.
3. **Submit missing question (1 answer instead of all 6 for Support):**
   - POST `/diagnostic/submit` with `{"answers": [{"question_id": "common-freq", "answer": "Daily"}]}`.
   - *Before fix:* HTTP 200 OK `{"saved": 1}`.
   - *After fix:* HTTP 422 Unprocessable Entity `{"detail": "All questions assigned to your role must be answered"}`.
4. **Submit with blank or too-short open answer:**
   - POST `/diagnostic/submit` with all 6 questions, but `"common-open"` has answer `"short"`.
   - *Before fix:* HTTP 200 OK `{"saved": 6}`.
   - *After fix:* HTTP 422 Unprocessable Entity `{"detail": "Answer for 'common-open' must be at least 10 characters"}`.
5. **Submit complete and valid answers to all 6 assigned questions:**
   - POST `/diagnostic/submit` with valid answers to all 6 assigned questions.
   - *Expected result:* HTTP 200 OK `{"saved": 6}`.


## Change 5: Atomic Answer Replacement in /diagnostic/submit (Fix Lifetime Averaging)

### Problem in One Line
Diagnostic submissions appended new response rows without deleting previous answers, causing repeated attempts to accumulate in the database and corrupting individual and team averages over time.

### Before and After Code (Key Lines)

#### `backend/app/routes/diagnostic.py`
**Before:**
```python
    bank = expected_map
    for a in body.answers:
        q = bank.get(a.question_id)
        resp = models.Response(membership_id=m.id, question_id=q["id"], answer=a.answer.strip())
        ...
        db.add(resp)
    db.commit()
```

**After:**
```python
    # Delete previous responses for this membership in the same transaction
    db.query(models.Response).filter_by(membership_id=m.id).delete()

    bank = expected_map
    for a in body.answers:
        q = bank.get(a.question_id)
        resp = models.Response(membership_id=m.id, question_id=q["id"], answer=a.answer.strip())
        ...
        db.add(resp)
    db.commit()
```

### Manual Verification Steps
1. **Sign in as Priya & select Northwind (`org_id: 1`):**
   - Call `POST /auth/login` with `{"email": "priya@northwind.test", "password": "pulse123"}`.
   - Call `POST /auth/select-org` with `{"org_id": 1}` to get scoped Bearer token.
2. **Check initial report:**
   - GET `/reports/me` $\rightarrow$ returns `answered: 2` (seeded response rows).
3. **Submit a full diagnostic attempt (6 questions):**
   - POST `/diagnostic/submit` with all 6 required answers $\rightarrow$ returns HTTP 200 `{"saved": 6}`.
   - GET `/reports/me` $\rightarrow$ returns `answered: 6`.
4. **Retake and submit the diagnostic a second time:**
   - POST `/diagnostic/submit` with 6 answers again.
   - *Before fix:* GET `/reports/me` returned `answered: 14` (accumulated 2 + 6 + 6) and averaged old and new scores together.
   - *After fix:* GET `/reports/me` returns `answered: 6` (replaces previous responses), with scores reflecting only the latest submission.


## Change 6: Seniority Rank Fix in Questions Service (Numeric Ranks Instead of String Comparison)

### Problem in One Line
`questions_for` compared seniority strings lexicographically (`seniority < q.get("min_seniority", "junior")`), causing lead employees (alphabetical 'l') to be improperly filtered out of 'mid' and 'senior' questions ('l' < 'm' and 'l' < 's' evaluated to True).

### Before and After Code (Key Lines)

#### `backend/app/services/questions.py`
**Before:**
```python
def questions_for(job_role: str, seniority: str):
    """Common questions for everyone + questions for this job role, filtered by seniority."""
    result = []
    for q in load_questions():
        if q["roles"] != ["all"] and job_role not in q["roles"]:
            continue
        if seniority < q.get("min_seniority", "junior"):
            continue
        result.append(q)
    return result
```

**After:**
```python
SENIORITY_RANKS = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
}

...

def questions_for(job_role: str, seniority: str):
    """Common questions for everyone + questions for this job role, filtered by seniority."""
    user_rank = SENIORITY_RANKS.get(seniority, 1)
    result = []
    for q in load_questions():
        if q["roles"] != ["all"] and job_role not in q["roles"]:
            continue
        if user_rank < SENIORITY_RANKS.get(q.get("min_seniority", "junior"), 1):
            continue
        result.append(q)
    return result
```

### Manual Verification Steps
1. **Sign in as Dev (`dev@northwind.test`, lead engineer at Northwind Logistics):**
   - Call `POST /auth/login` with `{"email": "dev@northwind.test", "password": "pulse123"}` $\rightarrow$ copy token.
2. **Select organization 1 (Northwind Logistics):**
   - Call `POST /auth/select-org` with `{"org_id": 1}` and `Authorization: Bearer <token>` $\rightarrow$ copy scoped token.
3. **Fetch questions via `GET /diagnostic/questions`:**
   - Call `GET /diagnostic/questions` with `Authorization: Bearer <scoped_token>`.
   - *Before fix:* Returned only junior-level role questions (`eng-assistant`) and common questions. `eng-review` (mid) and `eng-arch` (senior) were omitted because Python string comparison `'lead' < 'mid'` and `'lead' < 'senior'` evaluated to `True`.
   - *After fix:* Returned both `eng-review` and `eng-arch` alongside `eng-assistant` and common questions because lead (rank 4) >= mid (rank 2) and senior (rank 3).
4. **Verify Lead Manager questions:**
   - Log in as a lead manager user or test `questions_for("manager", "lead")`.
   - *Before fix:* `mgr-policy` was missing.
   - *After fix:* `mgr-policy` is present.


## Change 7: Department Score Math (Per-Respondent Average & Unassessed Handling)

### Problem in One Line
Department scores summed raw question scores across all department members and divided by total employee headcount, diluting respondent scores with non-respondents and reporting `0.0` / `"Beginner"` instead of `"Not assessed"` for departments with zero respondents.

### Before and After Code (Key Lines)

#### `backend/app/routes/dashboard.py`
**Before:**
```python
        scores = []
        responded = 0
        for dm in dept_members:
            rows = db.query(models.Response).filter_by(membership_id=dm.id).all()
            if rows:
                responded += 1
            for r in rows:
                if r.score is not None:
                    scores.append(r.score)
                for f in r.flags or []:
                    all_flags[f] = all_flags.get(f, 0) + 1
        avg = sum(scores) / len(dept_members) if dept_members else None
```

**After:**
```python
        respondent_averages = []
        responded = 0
        for dm in dept_members:
            rows = db.query(models.Response).filter_by(membership_id=dm.id).all()
            user_scores = [r.score for r in rows if r.score is not None]
            if user_scores:
                respondent_averages.append(sum(user_scores) / len(user_scores))
            if rows:
                responded += 1
            for r in rows:
                for f in r.flags or []:
                    all_flags[f] = all_flags.get(f, 0) + 1
        avg = sum(respondent_averages) / len(respondent_averages) if respondent_averages else None
```

### Manual Verification Steps
1. **Sign in as Admin Asha (`asha@northwind.test`, admin at Northwind Logistics):**
   - Call `POST /auth/login` with `{"email": "asha@northwind.test", "password": "pulse123"}` $\rightarrow$ copy token.
2. **Select organization 1 (Northwind Logistics):**
   - Call `POST /auth/select-org` with `{"org_id": 1}` and `Authorization: Bearer <token>` $\rightarrow$ copy scoped token.
3. **Fetch department analytics via `GET /dashboard`:**
   - Call `GET /dashboard` with `Authorization: Bearer <scoped_token>`.
4. **Verify assessed department score (Sales):**
   - *Before fix:* Sales showed `average_score: 2.67` because respondent Vikram's scores (4 and 4) were divided by the total department headcount (3 employees).
   - *After fix:* Sales shows `average_score: 4.0` because Vikram's average (4.0) is averaged only across active respondents (1 respondent).
5. **Verify unassessed department status (Engineering & HR):**
   - *Before fix:* Engineering and HR showed `average_score: 0.0` and `level: "Beginner"`.
   - *After fix:* Engineering and HR show `average_score: null` and `level: "Not assessed"`.


## Change 8: Consolidate Maturity Level Calculation (Use utils.maturity_level in Dashboard)

### Problem in One Line
`dashboard.py` defined its own duplicate `level_for` function with inconsistent threshold cutoffs (1.5, 2.5, 3.5) compared to `utils.maturity_level` (2.0, 3.0, 4.0), causing identical averages to be categorized under different maturity levels between employee reports and admin dashboards.

### Before and After Code (Key Lines)

#### `backend/app/routes/dashboard.py`
**Before:**
```python
def level_for(avg):
    if avg is None:
        return "Not assessed"
    if avg < 1.5:
        return "Beginner"
    if avg < 2.5:
        return "Exploring"
    if avg < 3.5:
        return "Practitioner"
    return "Leader"
...
            "level": level_for(avg),
```

**After:**
```python
from ..utils import maturity_level
...
            "level": maturity_level(avg),
```

### Manual Verification Steps
1. **Sign in as Admin Asha (`asha@northwind.test`, admin at Northwind Logistics):**
   - Call `POST /auth/login` with `{"email": "asha@northwind.test", "password": "pulse123"}` $\rightarrow$ copy token.
2. **Select organization 1 (Northwind Logistics):**
   - Call `POST /auth/select-org` with `{"org_id": 1}` and `Authorization: Bearer <token>` $\rightarrow$ copy scoped token.
3. **Fetch department analytics via `GET /dashboard`:**
   - Call `GET /dashboard` with `Authorization: Bearer <scoped_token>`.
4. **Verify consistent maturity level classification:**
   - Verify that Support (avg 2.5) evaluates to `"Exploring"` according to the standard enterprise rubric in `utils.maturity_level` and unassessed departments evaluate to `"Not assessed"`.
   - Verify `level_for` is completely removed from `dashboard.py`.


## Change 9: Fix Sham Test (test_admin_cannot_see_other_org)

### Problem in One Line
`test_admin_cannot_see_other_org` previously queried `org_id=1` (the admin's own organization) and asserted HTTP 200, creating a sham test that did not verify cross-tenant access denial.

### Before and After Code (Key Lines)

#### `backend/tests/test_api.py`
**Before:**
```python
def test_admin_cannot_see_other_org(client):
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    r = client.get("/dashboard?org_id=1", headers=headers)
    assert r.status_code == 200
    assert "departments" in r.json()
```

**After:**
```python
def test_admin_cannot_see_other_org(client):
    # Proves an admin cannot view another org dashboard (returns 403).
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    r = client.get("/dashboard?org_id=2", headers=headers)
    assert r.status_code == 403
```

### Manual Verification Steps
1. **Sign in as Admin Asha (`asha@northwind.test`, admin at Northwind Logistics, org 1):**
   - Call `POST /auth/login` with `{"email": "asha@northwind.test", "password": "pulse123"}` $\rightarrow$ copy token.
2. **Select organization 1 (Northwind Logistics):**
   - Call `POST /auth/select-org` with `{"org_id": 1}` and `Authorization: Bearer <token>` $\rightarrow$ copy scoped token.
3. **Attempt to fetch organization 2 (Bluepeak Retail) dashboard:**
   - Call `GET /dashboard?org_id=2` with `Authorization: Bearer <scoped_token>`.
   - *Expected result:* HTTP 403 Forbidden `{"detail": "Cannot view another organization's dashboard"}`.
