Tier 1: Security and privacy (do these first)
Bind /dashboard to the token’s org. Stop using the org_id query param. Use the member’s own org_id. Test: an admin at org 1 requesting org 2 data gets 403, and Ravi (employee at A, admin at B) can’t read A.
Membership check in /auth/select-org. Return 403 if the user isn’t a member of that org. Test: Priya selecting org 2 is rejected.
Server-side submission validation. Require all questions assigned to the role, reject blank answers, set a small minimum length on open text, and return 422. Test: empty list, blank answer, and missing question all get rejected.
Submit replaces previous answers in one transaction. Fixes the lifetime-averaging bug and makes “completed” meaningful.
Tier 2: Correctness
Seniority rank fix in questions.py (numeric ranks instead of string comparison). The failing test should go green.
Department score math. Average each respondent first, then average across respondents only. Departments with no respondents show “Not assessed”, not 0.0.
One maturity-level function. Delete level_for in dashboard.py and use utils.maturity_level.
Tier 3: Client requests
K-anonymity (k=5), backend only. Count distinct members who completed. Group small departments into “Other teams”, hide that row too if it’s still under 5, and drop risks coming only from small groups. Show “fewer than 5”, never the exact number.
Delete endpoint (DELETE /reports/me), scoped to the member for the active org. Test: a department going from 5 to 4 completed disappears from the dashboard, and user A can’t delete user B’s data.
Tier 4: AI trust
Harden LLM parsing. Strip code fences, coerce score to a number, clamp to 1-5, whitelist flags, handle timeouts and HTTP errors.
Make mock mode honest. Label the result’s source (“mock” or “AI”) in the API response and the UI. In live mode with a missing key, return a clear error, not a fake score.
Prompt-injection defense: separate system and user messages, delimit the answer, and clamp the output anyway.
Tier 5: UI and repo hygiene
Dashboard table replacing the raw JSON, with labeled columns.
Persistent login (read the token on mount) plus logout and a way back.
Redirect home after submit, and a history/report view with a delete button.
Untrack backend/.env, add .env.example, pin Python 3.12 in .python-version, and fix the Dockerfile CMD.
Fix the sham test (test_admin_cannot_see_other_org) and make sure the whole suite is green.
Tier 6: Yours
Your own feature: per-department recommended actions from rules, after the core is done.
README, then the recording last.