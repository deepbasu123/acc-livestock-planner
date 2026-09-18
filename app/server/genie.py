"""Genie Conversation API proxy via the SDK api_client (dual-mode auth)."""
import time
from .config import get_client, GENIE_SPACE_ID

BASE = "/api/2.0/genie/spaces"


def _do(method, path, body=None):
    w = get_client()
    return w.api_client.do(method, path, body=body)


def _extract(msg, space_id, conv_id, msg_id):
    """Pull a text answer + optional tabular result from a completed Genie message."""
    answer, sql, table = "", "", None
    for att in msg.get("attachments", []) or []:
        if "text" in att and att["text"]:
            answer = "".join(att["text"].get("content", "")) if isinstance(att["text"].get("content"), list) else att["text"].get("content", "")
        if "query" in att and att["query"]:
            q = att["query"]
            sql = q.get("query", "")
            if not answer:
                answer = q.get("description", "")
            att_id = att.get("attachment_id")
            try:
                res = _do("GET", f"{BASE}/{space_id}/conversations/{conv_id}/messages/{msg_id}/attachments/{att_id}/query-result")
                sr = res.get("statement_response", {})
                data = sr.get("result", {}).get("data_array", []) or []
                cols = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
                if cols:
                    table = {"columns": cols, "rows": data[:50]}
            except Exception:
                pass
    return answer, sql, table


def ask(content, conversation_id=None):
    space = GENIE_SPACE_ID
    if conversation_id:
        start = _do("POST", f"{BASE}/{space}/conversations/{conversation_id}/messages", {"content": content})
        conv_id = conversation_id
        msg_id = start.get("message_id") or start.get("id")
    else:
        start = _do("POST", f"{BASE}/{space}/start-conversation", {"content": content})
        conv_id = start.get("conversation_id") or start.get("conversation", {}).get("id")
        msg_id = start.get("message_id") or start.get("message", {}).get("id")

    # poll
    status = "IN_PROGRESS"
    msg = {}
    for _ in range(60):
        msg = _do("GET", f"{BASE}/{space}/conversations/{conv_id}/messages/{msg_id}")
        status = msg.get("status", "")
        if status in ("COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"):
            break
        time.sleep(2)
    if status != "COMPLETED":
        return {"answer": f"(Genie status: {status})", "sql": "", "table": None,
                "conversation_id": conv_id, "message_id": msg_id}
    answer, sql, table = _extract(msg, space, conv_id, msg_id)
    return {"answer": answer or "(no answer)", "sql": sql, "table": table,
            "conversation_id": conv_id, "message_id": msg_id}
