from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_membership
from ..utils import maturity_level
from ..services.questions import questions_for

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def compute_dashboard_aggregates(db: Session, target_org_id: int) -> dict:
    org = db.get(models.Organization, target_org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    members = db.query(models.Membership).filter_by(org_id=target_org_id).all()
    departments = []
    visible_flags = {}

    other_teams_member_averages = []
    other_teams_employees = 0
    other_teams_flags = []
    has_suppressed_departments = False

    for dept in org.departments:
        dept_members = [x for x in members if x.department_id == dept.id]
        completed_member_averages = []
        dept_flags = []

        for dm in dept_members:
            rows = db.query(models.Response).filter_by(membership_id=dm.id).all()
            if not rows:
                continue

            # A completed diagnostic requires answering every question assigned to the member's role
            assigned_questions = questions_for(dm.job_role, dm.seniority)
            assigned_ids = {q["id"] for q in assigned_questions}
            answered_ids = {r.question_id for r in rows if r.answer and r.answer.strip()}

            is_completed = bool(assigned_ids and assigned_ids.issubset(answered_ids))

            if is_completed:
                user_scores = [r.score for r in rows if r.score is not None]
                if user_scores:
                    completed_member_averages.append(sum(user_scores) / len(user_scores))
                for r in rows:
                    for f in r.flags or []:
                        dept_flags.append(f)

        distinct_completed_count = len(completed_member_averages)

        if distinct_completed_count >= 5:
            dept_avg = sum(completed_member_averages) / distinct_completed_count if distinct_completed_count else None
            dept_risk_counts = {}
            for f in dept_flags:
                dept_risk_counts[f] = dept_risk_counts.get(f, 0) + 1
                visible_flags[f] = visible_flags.get(f, 0) + 1
            departments.append({
                "department": dept.name,
                "employees": len(dept_members),
                "responded": distinct_completed_count,
                "average_score": round(dept_avg, 2) if dept_avg is not None else None,
                "level": maturity_level(dept_avg),
                "risk_counts": dept_risk_counts,
            })
        else:
            has_suppressed_departments = True
            other_teams_employees += len(dept_members)
            other_teams_member_averages.extend(completed_member_averages)
            other_teams_flags.extend(dept_flags)

    # Aggregate for Other teams
    other_completed_count = len(other_teams_member_averages)
    if other_completed_count >= 5:
        other_avg = sum(other_teams_member_averages) / other_completed_count
        other_risk_counts = {}
        for f in other_teams_flags:
            other_risk_counts[f] = other_risk_counts.get(f, 0) + 1
            visible_flags[f] = visible_flags.get(f, 0) + 1
        departments.append({
            "department": "Other teams",
            "employees": other_teams_employees,
            "responded": other_completed_count,
            "average_score": round(other_avg, 2),
            "level": maturity_level(other_avg),
            "risk_counts": other_risk_counts,
        })
        hidden_small_groups = False
    else:
        hidden_small_groups = has_suppressed_departments

    return {
        "organization": org.name,
        "departments": departments,
        "top_risks": sorted(visible_flags.items(), key=lambda kv: -kv[1])[:5],
        "hidden_small_groups": hidden_small_groups,
    }


@router.get("")
def org_dashboard(org_id: int | None = None, m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    if m.role != "admin":
        raise HTTPException(403, "Admins only")

    if org_id is not None and org_id != m.org_id:
        raise HTTPException(403, "Cannot view another organization's dashboard")

    return compute_dashboard_aggregates(db, m.org_id)
