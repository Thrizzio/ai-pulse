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

    # Reuse existing privacy-preserving dashboard aggregates (k >= 5)
    agg = compute_dashboard_aggregates(db, m.org_id)
    visible_departments = agg.get("departments", [])

    # Generate actionable insights strictly from privacy-cleared aggregates
    res = insights_service.generate_insights(visible_departments)

    return {
        "organization": agg["organization"],
        "insights": res["insights"],
        "source": res["source"],
        "hidden_small_groups": agg["hidden_small_groups"],
    }

