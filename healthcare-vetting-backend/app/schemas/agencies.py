from pydantic import BaseModel
from typing import Optional


class AgencyCreate(BaseModel):
    name: str
    email: str
    password: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    plan: str = "standard"


class AgencyResponse(BaseModel):
    id: str
    name: str
    email: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    plan: str = "standard"
    monthly_fee: float = 300.0
    created_at: Optional[str] = None


class AgencyLogin(BaseModel):
    email: str
    password: str


class InviteCreate(BaseModel):
    candidate_email: str


class InviteResponse(BaseModel):
    id: str
    agency_id: str
    agency_name: Optional[str] = None
    candidate_email: str
    invite_code: str
    status: str = "pending"
    candidate_id: Optional[str] = None
    created_at: Optional[str] = None
    accepted_at: Optional[str] = None
