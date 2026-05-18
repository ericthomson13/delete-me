from __future__ import annotations

from delete_me.cases import brokers_summary
from delete_me.registry import load_brokers
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/brokers", tags=["brokers"])


@router.get("")
def list_brokers() -> list[dict]:
    return list(brokers_summary())


@router.get("/{broker_id}")
def get_broker(broker_id: str) -> dict:
    for b in load_brokers():
        if b.id == broker_id:
            return b.model_dump(mode="json")
    raise HTTPException(404, f"unknown broker_id: {broker_id}")
