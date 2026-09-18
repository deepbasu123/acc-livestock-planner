"""Embedded Genie chat proxy."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from .. import genie

router = APIRouter()


class GenieReq(BaseModel):
    question: str
    conversation_id: Optional[str] = None


@router.post("/genie/ask")
def genie_ask(req: GenieReq):
    try:
        return genie.ask(req.question, req.conversation_id)
    except Exception as e:
        return {"answer": f"(Genie error: {e})", "sql": "", "table": None,
                "conversation_id": req.conversation_id, "message_id": None}
