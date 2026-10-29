# AI Pulse

AI Pulse assesses how teams use AI at work and helps administrators identify risks and areas for improvement.

## Issues That I Solved in the Codebase

- Fixed cross-organization dashboard access by binding requests to the authenticated user's active organization.
- Added membership validation to prevent users from selecting organizations they do not belong to.
- Fixed a misleading security test that never actually tested access to another organization.
- Added server-side validation for missing questions, blank answers, short text responses, and invalid multiple-choice options.
- Fixed repeated submissions accumulating old answers and distorting scores by replacing previous responses on resubmission.
- Fixed seniority filtering that incorrectly compared seniority levels as strings.
- Corrected department score calculations to average respondents instead of dividing by total headcount.
- Changed departments with no usable assessment data to display `Not assessed` instead of a score of zero.
- Removed duplicate maturity-level logic and reused the shared scoring utility.
- Added validation for LLM responses, score clamping, and filtering of unsupported risk flags.
- Separated system instructions from employee answers to reduce prompt-injection risk.
- Added explicit disclosure of whether assessment results came from mock scoring or live AI.
- Replaced the raw JSON dashboard with a readable table.
- Added session restoration, logout, organization switching, and navigation controls.
- Removed `backend/.env` from Git tracking, added environment templates, pinned Python 3.12, and fixed the Docker entrypoint.
- Added standard and expanded seed modes for testing different organization and department sizes.

## What I Left

- Organization and department creation remains a vendor-side provisioning step for the pilot.
- User invitations, onboarding, and email verification are not implemented.
- Self-service password reset is not implemented.
- SSO/SAML and MFA are not implemented.
- Seed accounts still use unsalted SHA-256 password hashing and require a proper password hashing scheme before production use.
- Database migrations and PostgreSQL support remain outside the scope of this submission.

## Client Request

- Added `DELETE /reports/me` so employees can delete their current diagnostic responses.
- Enforced a minimum of five completed respondents before displaying department-level data.
- Combined small departments into `Other teams` when possible and suppressed the combined group if it still had fewer than five respondents.
- Excluded risks from suppressed departments from dashboard output.
- Made repeated submissions replace previous responses so reports reflect the latest attempt.

## My Idea: Department Insights

- Added a separate Insights page that turns department-level risk patterns into actionable recommendations.
- Recommendations include the observed pattern, suggested action, reason, and priority.
- The Insights LLM receives only privacy-filtered aggregate data, never raw employee answers or individual reports.
- Added output validation and fallback handling for unavailable or invalid LLM responses.

## Questions for the Client

- Should employees be allowed to delete their diagnostic data indefinitely, or should there be a defined time limit?
- Should employees be able to retake the diagnostic without limits, or should there be a cooldown or maximum number of attempts?
- Should the system retain historical reports, or should each new submission replace the previous one?


## How I Used AI Tools

- Used AI coding tools to audit the existing codebase, identify potential bugs, plan changes, implement fixes, and develop regression tests.
- Reviewed the generated changes against the existing architecture and client requirements, then ran the backend tests and frontend build.
- One example of AI assistance being insufficient was the existing `test_admin_cannot_see_other_org` test, which requested the admin's own organization and therefore did not verify cross-organization access; I corrected the test to request another organization and expect `403 Forbidden`.

## Verification

- Backend test suite: 55 tests passed across core API, question tailoring, k-anonymity privacy, and department insights suites.
- Frontend production build: completed successfully in the recorded development run.
- Tests cover authorization, diagnostic validation, department privacy, and the Insights endpoint.
- Test results should be rerun against the final submitted commit.

## Running Locally

- Backend: use Python 3.12, install dependencies from `backend/requirements.txt`, and configure environment variables using `.env.example`.
- Frontend: run `npm install` and `npm run dev` inside `frontend/`.
- Tests: run `python -m pytest backend` from the repository root.
- Build: run `npm --prefix frontend run build`.
- Use a disposable database when running seed/reset commands, as they can delete existing data.