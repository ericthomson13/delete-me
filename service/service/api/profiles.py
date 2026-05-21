from __future__ import annotations

from delete_me.cases import profile_to_consumer, upsert_profile
from delete_me.db import Profile
from delete_me.letters.engine import ConsumerProfile
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ._deps import get_session

router = APIRouter(prefix="/profiles", tags=["profiles"])


class ProfileIn(BaseModel):
    full_legal_name: str
    current_address: str
    email: str | None = None
    phone: str | None = None
    dob_year: int | None = None
    prior_addresses: list[str] = []
    former_names: list[str] = []


class ProfileOut(BaseModel):
    id: int
    full_legal_name: str
    current_address: str
    email: str | None
    phone: str | None
    dob_year: int | None
    prior_addresses: list[str]
    former_names: list[str]


def _to_out(p: Profile) -> ProfileOut:
    c = profile_to_consumer(p)
    return ProfileOut(
        id=p.id,
        full_legal_name=c.full_legal_name,
        current_address=c.current_address,
        email=c.email,
        phone=c.phone,
        dob_year=c.dob_year,
        prior_addresses=list(c.prior_addresses),
        former_names=list(c.former_names),
    )


@router.get("", response_model=list[ProfileOut])
def list_profiles(session: Session = Depends(get_session)) -> list[ProfileOut]:
    return [_to_out(p) for p in session.exec(select(Profile).order_by(Profile.id)).all()]


@router.post("", response_model=ProfileOut)
def create_or_update_profile(
    payload: ProfileIn,
    session: Session = Depends(get_session),
) -> ProfileOut:
    consumer = ConsumerProfile(
        full_legal_name=payload.full_legal_name,
        current_address=payload.current_address,
        email=payload.email,
        phone=payload.phone,
        dob_year=payload.dob_year,
        prior_addresses=tuple(payload.prior_addresses),
        former_names=tuple(payload.former_names),
    )
    profile = upsert_profile(session, consumer)
    return _to_out(profile)


@router.get("/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: int, session: Session = Depends(get_session)) -> ProfileOut:
    p = session.get(Profile, profile_id)
    if not p:
        raise HTTPException(404, f"profile {profile_id} not found")
    return _to_out(p)
