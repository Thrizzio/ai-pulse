# AI Pulse: Product Requirements Document

Status: working draft. Sections marked **[VERIFY]** are assumptions from the assessment brief and must be checked against the actual code.

---

## 1. Overview

**AI Pulse** helps a company see how well its people use AI at work.

- Employees take a short **diagnostic** that adapts to their role.
- Leadership sees **where each team stands** and **what the risks are**.
- Some users work with **more than one company**, so the product is multi-tenant.

The codebase was started by a developer who left. It runs, but it is not trusted. The goal of this work is to get it to a state we would be comfortable putting in front of a real enterprise client.

## 2. Problem

Companies adopt AI tools quickly but have no clear view of whether employees use them well or safely. AI Pulse gives a measurable, role-aware picture, per person and per team, without leaking one company's data to another or one employee's answers to the wrong audience.

## 3. Users

| User | Goal | What they must never see |
|---|---|---|
| **Employee** | Take the diagnostic, understand their own result | Other employees' answers or scores; other companies' data |
| **Leadership / manager** | See team-level standing and risks | Data from other companies; individual detail beyond what their role allows **[VERIFY]** |
| **Multi-company user** | Belong to several companies without mixing data | One company's data while acting in another |
| **Client (enterprise buyer)** | Trust the product with company data; has an open feature request | n/a |
| **Engineer on the team** | Run, change and test the app safely | n/a |

## 4. Core flow **[VERIFY]**

1. User signs in and is associated with one or more companies.
2. User selects or is scoped to a company context.
3. The diagnostic is generated or selected based on the user's **role**.
4. User answers; the answers are scored (AI-assisted and/or rule-based **[VERIFY]**).
5. The result is stored against the user and company.
6. Leadership views aggregated team results and risk flags for their company only.

## 5. Design **[VERIFY]**

To be filled after the code audit:

- Stack (backend: Python, `backend/requirements.txt`; frontend: TBD)
- Data model: users, companies, memberships, diagnostics, responses, results
- Auth and authorization: how the user and company are identified on each request
- Where LLM calls happen and how outputs are used
- Where scoring and aggregation logic lives

## 6. Requirements (from the assessment brief)

### 6.1 Safe to give to a client
- Data stays with the right people: strict tenant (company) isolation on every read and write.
- Role-based access: employees and leadership see only what their role permits.
- The product does what it claims: UI and README claims match actual behavior; no fake or hardcoded results.
- No secrets in the repo or its history.

### 6.2 Provable
- Automated tests on the highest-risk paths (tenant isolation, authorization, scoring).
- A demo that shows it working, not just a statement that it works (screen recording, up to 5 minutes).

### 6.3 Runnable and changeable by anyone on the team
- One documented setup path, pinned Python version, `.env.example`, seed data.
- Clear structure and a short architecture note.
- CI or a single command that runs the tests.

### 6.4 AI parts can be trusted
- Validate and constrain LLM output (schema validation, bounds checks).
- Defend against prompt injection from user-supplied text.
- Handle timeouts, errors and bad output with safe fallbacks.
- Keep scoring explainable and, where possible, deterministic.

### 6.5 Client request
- A client request exists in the repo and has not been acted on.
- Deliverable: handle it, or do the safe part, and document **what we would ask the client**.
- Details: **[ADD after reading the request file]**

### 6.6 Own feature
- One feature that is not in the code or the client request.
- Makes AI Pulse more useful to employees or leadership.
- Small and sharp beats big and generic.
- Chosen feature: **[DECIDE after audit]**. Problem solved: TBD. Why chosen: TBD.

## 7. Prioritization approach

There is no checklist, and part of the assessment is deciding what matters most. Order of work:

1. Security and data isolation
2. Correctness (claims vs. reality)
3. Reliability of the AI parts
4. Tests and developer experience
5. Client request
6. Own feature

Out-of-scope items will be listed deliberately in the final README ("what I left and why"). Expected effort is about 15 hours; actual time available is shorter, and the README will say so.

## 8. Deliverables and rules

| Item | Detail |
|---|---|
| Repo | Fork or clone into own GitHub account, keep existing commit history |
| README | What was found wrong, fixed, and deliberately left; how the client request was handled and what to ask them; own feature (problem and why); how AI tools were used and one place they got it wrong |
| Recording | Screen recording, up to 5 minutes |
| Deadline | 29 Oct 2026, **11:59 AM IST** (the email says 12:00 PM; treat 11:59 as binding) |
| Submission | Google Form, one submission per person; update the shared tracker afterwards. The email and the brief list different form links, so confirm with the placement team |
| AI tools | Allowed |
| Live round | 30 minutes: explain the code, make a change, and debug, **without AI tools** |
| Principle | Build only what you understand. Honest beats polished; a partial submission with clear notes beats a polished one that hides broken parts |

## 9. Open questions

- Which roles exist, and what exactly can each see?
- How is a multi-company user's active company determined per request?
- What does the client request ask for, and does it conflict with data-isolation rules?
- Are any secrets or API keys already in git history?
- What does the README or UI claim that the code does not actually do?

## 10. Decisions log (fill as we go)

| Date/time | Decision | Why | Alternative rejected |
|---|---|---|---|
| | | | |