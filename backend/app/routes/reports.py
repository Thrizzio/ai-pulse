from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_user, current_membership, _decode
from ..utils import maturity_level
from ..config import AI_MODE

router = APIRouter(prefix="/reports", tags=["reports"])

NEXT_STEPS = {
    "support": ["Use AI to draft first replies, then edit", "Summarise long ticket threads before escalating", "Never paste customer details into public chatbots"],
    "engineering": ["Use a code assistant for tests and refactors", "Review every AI suggestion before merging", "Keep secrets and customer data out of prompts"],
    "sales": ["Draft outreach emails with AI and personalise them", "Summarise call notes into CRM updates", "Check AI-written claims before sending"],
    "manager": ["Agree an AI usage policy with your team", "Pick one workflow per quarter to improve with AI", "Track time saved, not tool licences"],
}


@router.get("")
def list_my_reports(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    """Lists saved diagnostic reports across organizations where the user is an authorized member."""
    memberships = db.query(models.Membership).filter_by(user_id=user.id).all()
    results = []
    for m in memberships:
        rows = db.query(models.Response).filter_by(membership_id=m.id).all()
        if not rows:
            continue
        scores = [r.score for r in rows if r.score is not None]
        avg = sum(scores) / len(scores) if scores else None
        results.append({
            "org_id": m.org_id,
            "organization": m.org.name,
            "role": m.role,
            "answered": len(rows),
            "average_score": round(avg, 2) if avg is not None else None,
            "level": maturity_level(avg),
            "has_report": True,
        })
    return results


@router.get("/me")
def my_report(
    org_id: int | None = None,
    user: models.User = Depends(current_user),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    target_org_id = org_id
    if target_org_id is None:
        data = _decode(authorization)
        target_org_id = data.get("org")

    if not target_org_id:
        raise HTTPException(400, "Select an organization first")

    m = db.query(models.Membership).filter_by(user_id=user.id, org_id=target_org_id).first()
    if not m:
        raise HTTPException(403, "Not a member of this organization")

    rows = db.query(models.Response).filter_by(membership_id=m.id).all()
    scores = [r.score for r in rows if r.score is not None]
    avg = sum(scores) / len(scores) if scores else None
    flags = sorted({f for r in rows for f in (r.flags or [])})
    return {
        "name": m.user.name,
        "organization": m.org.name,
        "answered": len(rows),
        "average_score": round(avg, 2) if avg is not None else None,
        "level": maturity_level(avg),
        "risks": flags,
        "next_steps": NEXT_STEPS.get(m.job_role, NEXT_STEPS["manager"]),
        "source": "mock" if AI_MODE == "mock" else "ai",
    }


@router.delete("/me")
def delete_my_report(
    org_id: int | None = None,
    user: models.User = Depends(current_user),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    target_org_id = org_id
    if target_org_id is None:
        data = _decode(authorization)
        target_org_id = data.get("org")

    if not target_org_id:
        raise HTTPException(400, "Select an organization first")

    m = db.query(models.Membership).filter_by(user_id=user.id, org_id=target_org_id).first()
    if not m:
        raise HTTPException(403, "Not a member of this organization")

    deleted = db.query(models.Response).filter_by(membership_id=m.id).delete()
    db.commit()
    return {"status": "deleted", "deleted_responses": deleted}
