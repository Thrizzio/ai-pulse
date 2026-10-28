"""Creates demo data.
Run:
  python -m app.seed             (runs standard seed or expanded based on EXPANDED_SEED in .env)
  python -m app.seed --standard  (forces standard pilot seed)
  python -m app.seed --expanded  (forces expanded multi-company seed)

All passwords are: pulse123
"""
import sys
from .db import Base, engine, SessionLocal
from . import models
from .auth import hash_password
from .config import EXPANDED_SEED
from .services.questions import questions_for

PEOPLE_NORTHWIND = [
    # name, email, department, role, job_role, seniority
    ("Asha Rao", "asha@northwind.test", None, "admin", "manager", "lead"),
    ("Vikram Shah", "vikram@northwind.test", "Sales", "employee", "sales", "senior"),
    ("Neha Gupta", "neha@northwind.test", "Sales", "employee", "sales", "junior"),
    ("Rohan Mehta", "rohan@northwind.test", "Sales", "employee", "sales", "mid"),
    ("Priya Nair", "priya@northwind.test", "Support", "employee", "support", "junior"),
    ("Arjun Iyer", "arjun@northwind.test", "Support", "employee", "support", "senior"),
    ("Kavitha Menon", "kavitha@northwind.test", "Support", "employee", "support", "mid"),
    ("Dev Malhotra", "dev@northwind.test", "Engineering", "employee", "engineering", "lead"),
    ("Sara Thomas", "sara@northwind.test", "Engineering", "employee", "engineering", "mid"),
    ("Imran Khan", "imran@northwind.test", "HR", "employee", "manager", "senior"),
]

PEOPLE_BLUEPEAK = [
    ("Meera Pillai", "meera@bluepeak.test", None, "admin", "manager", "lead"),
    ("Tom Fernandes", "tom@bluepeak.test", "Stores", "employee", "sales", "mid"),
    ("Lina George", "lina@bluepeak.test", "Stores", "employee", "sales", "junior"),
    ("Kabir Das", "kabir@bluepeak.test", "Customer Care", "employee", "support", "senior"),
]

# Expanded Dataset: Larger enterprises, multiple departments with 5+ employees
PEOPLE_APEX = [
    ("Alex Vance", "alex@apex.test", None, "admin", "manager", "lead"),
    # Engineering (6 employees: 5 completed)
    ("Priyanka Roy", "priyanka@apex.test", "Engineering", "employee", "engineering", "senior"),
    ("Marcus Brody", "marcus@apex.test", "Engineering", "employee", "engineering", "mid"),
    ("Elena Rostova", "elena@apex.test", "Engineering", "employee", "engineering", "mid"),
    ("David Kim", "david@apex.test", "Engineering", "employee", "engineering", "junior"),
    ("Chloe Bennet", "chloe@apex.test", "Engineering", "employee", "engineering", "junior"),
    ("Jason Hayes", "jason@apex.test", "Engineering", "employee", "engineering", "senior"),
    # Product (5 employees: all completed)
    ("Samantha Reed", "sam@apex.test", "Product", "employee", "manager", "senior"),
    ("Rachel Green", "rachel@apex.test", "Product", "employee", "manager", "mid"),
    ("Jordan Bell", "jordan@apex.test", "Product", "employee", "manager", "junior"),
    ("Nina Patel", "nina@apex.test", "Product", "employee", "manager", "lead"),
    ("Leo Rossi", "leo@apex.test", "Product", "employee", "manager", "mid"),
    # Customer Success (3 employees: 2 completed)
    ("Tariq Al-Mansoor", "tariq@apex.test", "Customer Success", "employee", "support", "senior"),
    ("Maya Lin", "maya@apex.test", "Customer Success", "employee", "support", "mid"),
    ("Lucas Silva", "lucas@apex.test", "Customer Success", "employee", "support", "junior"),
    # Legal & Compliance (2 employees: 0 completed)
    ("Victoria Sterling", "victoria@apex.test", "Legal & Compliance", "employee", "manager", "senior"),
    ("Omar Farooq", "omar@apex.test", "Legal & Compliance", "employee", "manager", "junior"),
]

PEOPLE_CRESTLINE = [
    ("Dr. Angela Chen", "dr.chen@crestline.test", None, "admin", "manager", "lead"),
    ("Sarah Connor", "sarah.ops@crestline.test", "Clinical Operations", "employee", "manager", "senior"),
    ("Dr. Rajesh Patel", "dr.patel@crestline.test", "Research & Data", "employee", "engineering", "lead"),
    ("Lisa Ray", "lisa.admin@crestline.test", "Administration", "employee", "support", "mid"),
]


def _reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _make_org(db, name, depts):
    org = models.Organization(name=name)
    db.add(org)
    db.flush()
    d = {}
    for dn in depts:
        dept = models.Department(org_id=org.id, name=dn)
        db.add(dept)
        db.flush()
        d[dn] = dept.id
    return org, d


def _add_people(db, users, org, depts, people):
    for name, email, dept, role, job_role, seniority in people:
        u = users.get(email)
        if not u:
            u = models.User(name=name, email=email, password_hash=hash_password("pulse123"))
            db.add(u)
            db.flush()
            users[email] = u
        db.add(models.Membership(
            user_id=u.id, org_id=org.id,
            department_id=depts.get(dept) if dept else None,
            role=role, job_role=job_role, seniority=seniority,
        ))


def run_standard():
    """Seeds the standard pilot dataset (Northwind Logistics & Bluepeak Retail)."""
    _reset_database()
    db = SessionLocal()
    try:
        nw, nw_depts = _make_org(db, "Northwind Logistics", ["Sales", "Support", "Engineering", "HR"])
        bp, bp_depts = _make_org(db, "Bluepeak Retail", ["Stores", "Customer Care"])

        users = {}
        _add_people(db, users, nw, nw_depts, PEOPLE_NORTHWIND)
        _add_people(db, users, bp, bp_depts, PEOPLE_BLUEPEAK)

        # Consultant who works with both companies
        _add_people(db, users, nw, nw_depts, [("Ravi Kapoor", "ravi@consult.test", "HR", "employee", "manager", "senior")])
        _add_people(db, users, bp, bp_depts, [("Ravi Kapoor", "ravi@consult.test", None, "admin", "manager", "senior")])
        db.flush()

        def answer(email, org, qid, text, score, reason=None, flags=None):
            m = db.query(models.Membership).filter_by(user_id=users[email].id, org_id=org.id).first()
            db.add(models.Response(membership_id=m.id, question_id=qid, answer=text, score=score, reason=reason, flags=flags or []))

        answer("vikram@northwind.test", nw, "common-freq", "Daily", 4)
        answer("vikram@northwind.test", nw, "common-open", "Used ChatGPT to draft 20 follow-up emails and edited each one.", 4, "Regular use with editing.", [])
        answer("priya@northwind.test", nw, "common-freq", "A few times a month", 2)
        answer("priya@northwind.test", nw, "common-open", "Pasted a customer's complaint thread into ChatGPT to summarise it.", 3, "Useful summary but shared customer data.", ["customer_data_shared"])
        answer("tom@bluepeak.test", bp, "common-freq", "A few times a week", 3)
        answer("kabir@bluepeak.test", bp, "common-open", "Uploaded our full customer refund list to an AI tool to find patterns.", 3, "Good idea, unsafe data handling.", ["customer_data_shared", "confidential_data_shared"])
        answer("kabir@bluepeak.test", bp, "common-freq", "Daily", 4)

        db.commit()
    finally:
        db.close()
    print("Standard seed complete: Northwind Logistics & Bluepeak Retail created. Log in with password 'pulse123'.")


def run_expanded():
    """Seeds the expanded enterprise dataset (Apex Global & Crestline Health) with large teams."""
    _reset_database()
    db = SessionLocal()
    try:
        apex, apex_depts = _make_org(db, "Apex Global", ["Engineering", "Product", "Customer Success", "Legal & Compliance"])
        crest, crest_depts = _make_org(db, "Crestline Health", ["Clinical Operations", "Research & Data", "Administration"])

        users = {}
        _add_people(db, users, apex, apex_depts, PEOPLE_APEX)
        _add_people(db, users, crest, crest_depts, PEOPLE_CRESTLINE)

        # Multi-org employee: Marcus Brody also advises Crestline Health
        _add_people(db, users, crest, crest_depts, [("Marcus Brody", "marcus@apex.test", "Research & Data", "employee", "engineering", "senior")])
        db.flush()

        def answer(email, org, qid, text, score, reason=None, flags=None):
            m = db.query(models.Membership).filter_by(user_id=users[email].id, org_id=org.id).first()
            db.add(models.Response(membership_id=m.id, question_id=qid, answer=text, score=score, reason=reason, flags=flags or []))

        def complete_diagnostic(email, org, open_score, open_text, flags=None):
            m = db.query(models.Membership).filter_by(user_id=users[email].id, org_id=org.id).first()
            qs = questions_for(m.job_role, m.seniority)
            for q in qs:
                if q["type"] == "open":
                    db.add(models.Response(
                        membership_id=m.id, question_id=q["id"], answer=open_text,
                        score=open_score, reason="Assessed open response", flags=flags or [],
                    ))
                else:
                    db.add(models.Response(
                        membership_id=m.id, question_id=q["id"], answer="Daily",
                        score=4.0, flags=[],
                    ))

        # Engineering at Apex (6 completed members -> Engineering qualifies for k >= 5)
        for email, score, text, flags in [
            ("priyanka@apex.test", 4.5, "I use GitHub Copilot daily for unit tests and security reviews.", ["unreviewed_output"]),
            ("marcus@apex.test", 4.0, "I use Claude for refactoring architecture blueprints and always verify outputs.", []),
            ("elena@apex.test", 3.5, "I use AI tools to generate SQL queries and regexes.", []),
            ("david@apex.test", 3.0, "I use AI for debugging error stack traces occasionally.", []),
            ("chloe@apex.test", 2.5, "I tried ChatGPT once to draft docstrings but haven't used it regularly.", ["policy_unaware"]),
            ("jason@apex.test", 4.0, "We use AI code completion across our backend with mandatory peer reviews.", []),
        ]:
            complete_diagnostic(email, apex, score, text, flags)

        # Product at Apex (5 completed members -> Product qualifies for k >= 5)
        for email, score, text, flags in [
            ("sam@apex.test", 4.5, "I draft user stories and PRDs using Claude, reviewing each section.", []),
            ("rachel@apex.test", 4.0, "I summarize competitor release notes and customer interviews.", ["customer_data_shared"]),
            ("jordan@apex.test", 3.0, "I brainstorm feature ideas and marketing copy.", []),
            ("nina@apex.test", 5.0, "AI is embedded in our sprint planning and backlog grooming workflow.", []),
            ("leo@apex.test", 3.5, "I use AI to write first drafts of product documentation.", []),
        ]:
            complete_diagnostic(email, apex, score, text, flags)

        # Customer Success at Apex (2 completed members -> small group < 5)
        complete_diagnostic("tariq@apex.test", apex, 3.5, "I draft customer email responses and edit them before sending.", ["customer_data_shared"])
        complete_diagnostic("maya@apex.test", apex, 2.5, "Pasted a client ticket to summarize customer sentiment.", ["customer_data_shared", "confidential_data_shared"])

        # Crestline Health respondents
        answer("dr.chen@crestline.test", crest, "common-freq", "A few times a week", 3)
        answer("dr.patel@crestline.test", crest, "common-open", "Analyzing synthetic clinical trial datasets with local models.", 4.5, "Thoughtful use", [])

        db.commit()
    finally:
        db.close()
    print("Expanded seed complete: Apex Global & Crestline Health created with 20+ employees. Log in with password 'pulse123'.")


def run(expanded: bool | None = None):
    """Main seed entrypoint. Chooses standard or expanded seed based on parameter or EXPANDED_SEED env var."""
    is_expanded = expanded if expanded is not None else EXPANDED_SEED
    if is_expanded:
        run_expanded()
    else:
        run_standard()


if __name__ == "__main__":
    if "--expanded" in sys.argv:
        run(expanded=True)
    elif "--standard" in sys.argv:
        run(expanded=False)
    else:
        run()
