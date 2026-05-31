"""Internal service-to-service endpoints (not exposed to public)"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from app.database.connection import get_db
from app.models.user import User
from app.core.config import settings
from fastapi import Depends

router = APIRouter(prefix="/internal", tags=["internal"])


class UserEmailRequest(BaseModel):
    user_ids: List[str]


class UserEmailItem(BaseModel):
    user_id: str
    email: str


@router.post("/users/emails", response_model=List[UserEmailItem])
def get_user_emails(
    request: UserEmailRequest,
    x_internal_key: str = Header(...),
    db: Session = Depends(get_db),
):
    if x_internal_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not request.user_ids:
        return []
    users = db.query(User).filter(User.username.in_(request.user_ids)).all()
    return [UserEmailItem(user_id=u.username, email=u.email) for u in users]
