import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class AgencyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    contact_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    plan: str = Field(default="standard", max_length=50)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()


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
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class InviteCreate(BaseModel):
    candidate_email: str = Field(..., max_length=254)
    include_monitoring: bool = False

    @field_validator("candidate_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()


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
