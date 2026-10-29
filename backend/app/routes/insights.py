from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_membership
from .dashboard import compute_dashboard_aggregates
from ..services import insights_service

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("")
def get_insights(
    department_id: str | None = None,
    org_id: int | None = None,
    m: models.Membership = Depends(current_membership),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint providing actionable recommendations from approved aggregate risk patterns."""
    if m.role != "admin":
        raise HTTPException(403, "Admins only")

    # Strictly prevent viewing another organization's insights
    if org_id is not None and org_id != m.org_id:
        raise HTTPException(403, "Cannot view another organization's insights")

    agg = compute_dashboard_aggregates(db, m.org_id)
    departments = agg.get("departments", [])

    if department_id is not None:
        dept_str = str(department_id).strip().lower()

        # Handle "Other teams" aggregate Insights
        if dept_str in ("other", "other teams"):
            target_dept = next((d for d in departments if d.get("department") == "Other teams"), None)
            if not target_dept:
                raise HTTPException(404, "Other teams aggregate not found")

            res = insights_service.generate_other_teams_insights(target_dept)

            return {
                "organization": agg["organization"],
                "department_id": "other",
                "department": "Other teams",
                "insights": res["insights"],
                "source": res["source"],
                "hidden_small_groups": agg["hidden_small_groups"],
            }

        try:
            numeric_id = int(department_id)
        except ValueError:
            raise HTTPException(422, "Invalid department ID")

        dept = db.get(models.Department, numeric_id)
        if not dept:
            raise HTTPException(404, "Department not found")
        if dept.org_id != m.org_id:
            raise HTTPException(403, "Cannot access department belonging to another organization")

        # Find target department in privacy-cleared visible individual departments (k >= 5)
        target_dept = next((d for d in departments if d.get("id") == numeric_id and d.get("department") != "Other teams"), None)
        if not target_dept:
            raise HTTPException(403, "Department is not eligible for insights or is suppressed for privacy")

        # Process strictly the requested department's aggregate metrics
        res = insights_service.generate_insights([target_dept])

        return {
            "organization": agg["organization"],
            "department_id": dept.id,
            "department": dept.name,
            "insights": res["insights"],
            "source": res["source"],
            "hidden_small_groups": agg["hidden_small_groups"],
        }

    # Fallback to org-wide visible departments if no department specified
    visible_departments = [
        d for d in departments
        if (d.get("department") != "Other teams" or (d.get("responded") or 0) >= 5)
    ]
    res = insights_service.generate_insights(visible_departments)

    return {
        "organization": agg["organization"],
        "insights": res["insights"],
        "source": res["source"],
        "hidden_small_groups": agg["hidden_small_groups"],
    }

