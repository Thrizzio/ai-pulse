# AI Pulse: Issue Log

How to use: every issue gets an ID, a severity, evidence (file:line or reproduction steps), a decision, and a test. Status values: `open`, `confirmed`, `fixed`, `deferred`, `wontfix`.
Rule: **no issue is "confirmed" until I have reproduced it myself.** Anything an AI told me stays `suspected` until verified.

Severity: **P0** = data leak or security hole. **P1** = product claims something false or gives wrong results. **P2** = reliability or UX. **P3** = polish.

---

## Summary table

| ID | Area | Issue | Sev | Status | Evidence | Decision | Test |
|---|---|---|---|---|---|---|---|
| SEC-1 | Security | Admin/manager endpoints may be callable by employees (role checks unverified) | P0 | **fixed** | `dashboard.py:25` | Enforce admin role check `m.role == 'admin'` | `test_dashboard_scoped_to_token_org` |
| SEC-2 | Security | Cross-company access: changing a company/user ID may return another company's data | P0 | **fixed** | `dashboard.py:28`, `auth.py:68` | Bind to token org & reject non-member select | `test_dashboard_scoped_to_token_org`, `test_select_org_rejects_non_member` |
| SEC-3 | Privacy | Admin dashboard returns raw JSON, possibly with per-person data | P0 | **fixed** | `Dashboard.jsx` | Aggregate departments without PII, render executive table | UI & API inspection |
| SEC-4 | Security | Secrets or DB committed in git history? | P0 | **fixed** | `backend/.env` tracked in Git | Untrack `.env`, add `.env.example`, `.gitignore` secrets | `test_backend_env_not_tracked_in_git` |
| AI-1 | AI honesty | Score and "next steps" returned with no LLM key configured, so a silent mock or fallback is likely | P1 | **fixed** | `llm.py:32` | Disclose source ("mock" vs "ai"), error on missing live key | `test_ai_scoring_hardening_and_prompt_isolation` |
| AI-2 | AI trust | No error states for LLM failure, timeout, or bad output | P1 | **fixed** | `llm.py:45` | Handle timeout & HTTP errors returning 503 | `test_ai_scoring_hardening_and_prompt_isolation` |
| AI-3 | AI trust | Prompt injection via open-text answers not handled | P1 | **fixed** | `llm.py:41` | System/user message separation, `<employee_answer>` tags, score clamp 1-5 | `test_ai_scoring_hardening_and_prompt_isolation` |
| AI-4 | AI trust | Risks are LLM-generated and come back empty without a key | P1 | **fixed** | `scoring.py:9` | Enforce flag whitelist, honest mock disclosures | `test_ai_scoring_hardening_and_prompt_isolation` |
| LOGIC-1 | Correctness | Diagnostic can be submitted with zero or one answer and still gets a score | P1 | **fixed** | `diagnostic.py:44` | Validate all role questions answered, min 10 chars, return 422 | `test_submit_validation` |
| LOGIC-2 | Correctness | Score logic appears broken; metrics are undocumented | P1 | **fixed** | `questions.py:18`, `dashboard.py:52` | Numeric seniority ranks, per-respondent averaging, unified `maturity_level` | `test_lead_manager_gets_policy_questions`, `test_department_score_math` |
| LOGIC-3 | Correctness | Results page is unclear: it doesn't explain what the score means | P2 | **fixed** | `Report.jsx` | Clear display of level, score, risks, next steps, assessment source | Manual & UI inspection |
| UX-1 | UX | No redirect or way back after finishing an assessment | P2 | **fixed** | `App.jsx` | Redirect to Report on submit, add Back, Retake, and Switch Org buttons | Frontend build & test |
| UX-2 | UX | Login is not persistent | P2 | **fixed** | `App.jsx`, `api.js` | Persist token/session/org in localStorage, restore on mount, add Logout button | Frontend build & test |
| UX-3 | UX | No history page for past reports | P2 | **fixed** | `App.jsx`, `Report.jsx` | Restore last report on login, view past results, self-service delete | Frontend build & test |
| DASH-1 | Product | Admin view has no table: it should show avg score by department and top company risks | P1 | **fixed** | `Dashboard.jsx` | Executive table with Department, Headcount, Responded, Avg Score, Level | Frontend build & test |
| DEV-1 | DX | Python 3.14 breaks install (pydantic-core build fails); no pinned Python version | P2 | **fixed** | pip error on 3.14 | Pin 3.12, add `.python-version` and README note | `test_python_version_pinned` |
| DEV-2 | DX | npm version churn rewrites `package-lock.json` | P3 | **fixed** | `"peer": true` diff | Validated clean package-lock & build | `npm run build` |
| TEST-1 | Quality | Existing tests may be stale or failing | P2 | **fixed** | `test_questions.py:26`, `test_api.py:27` | Fixed seniority rank logic, fixed sham test to assert 403, 17/17 green | Full pytest suite |
| CLIENT-1 | Client request | Hide departments with fewer than 5 completed (k-anonymity), enforced in backend | P0 | **open** | `CLIENT_REQUEST.md` | Architectural questions documented; awaiting pilot rollout policy decisions | `README.md` |
| CLIENT-2 | Client request | Employee self-service hard delete of answers and report, gone from dashboards immediately | P0 | **fixed** | `CLIENT_REQUEST.md` | Implemented `DELETE /reports/me` and UI "Delete My Data" action | `test_delete_my_report_scoped_to_caller` |

---

## Detail (fill in as I verify)

### SEC-1: role checks on admin endpoints
- How to verify: log in as an employee, call the admin/manager endpoints directly (curl or browser).
- Expected: 403. Actual: 403 returned.
- Fix: Enforce `m.role == "admin"` in `backend/app/routes/dashboard.py`.
- Test: `test_dashboard_scoped_to_token_org`.

### SEC-2: cross-company access
- How to verify: as a user in company A, request company B's resources by changing IDs.
- Expected: 403. Actual: 403 returned.
- Fix: Bound `/dashboard` to token organization; verified membership in `/auth/select-org`.
- Test: `test_dashboard_scoped_to_token_org`, `test_select_org_rejects_non_member`.

### SEC-3: admin JSON content
- How to verify: inspect the response. Any names, emails, user IDs, or per-person scores?
- Expected: Aggregated data only.
- Fix: Replaced raw JSON with executive dashboard table with Department, Headcount, Responded, Average Score, Maturity Level.
- Test: Frontend UI inspection.

### AI-1: score without a key
- How to verify: check scoring behavior when LLM_API_KEY is not configured.
- Fix: In live mode, return a clear 503 error if key/URL is missing; honestly label `"source": "mock"` or `"source": "ai"` in API response and UI.
- Test: `test_ai_scoring_hardening_and_prompt_isolation`.

### LOGIC-1: blank submissions
- How to verify: submit an empty payload directly to the API.
- Fix: server-side validation (all role questions answered, minimum 10 char text length), 422 on failure.
- Test: `test_submit_validation`.

---

## Verified facts (so far)
- Install fails on Python 3.14; works on 3.12 or 3.13.
- Frontend runs on Vite at :5173; backend runs on uvicorn.
- All 17 backend unit and integration tests passing.

## Deliberately NOT doing (copy into README)
- Creating organizations and departments through the app (vendor-side provisioning step for pilot)
- Inviting users, onboarding, and email verification
- Self-service password reset
- SSO/SAML and MFA
- Unsalted SHA-256 seed passwords (noted as known risk for pilot)
- Production hosting, database migrations, and Postgres

## Questions for the client (copy into README)
1. Is the threshold of 5 counted per department, by completed diagnostics? Does it apply to filters, exports, and AI summaries?
2. For small groups: "Other teams" or hide entirely? If "Other" is under 5, hide?
3. May leadership see company totals, given the risk of subtracting to reveal a hidden group?
4. Does delete cover answers and report only, or the account too? Can the employee retake?
5. For people in multiple companies, is deletion per company or global?
6. What about backups, logs, and data already sent to the AI provider?
7. Does this apply to pilot data already collected?
