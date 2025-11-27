# llm.py  — Mistral version (no ChatMessage import)

import os, time
from typing import List, Dict, Tuple
from dotenv import load_dotenv

# ใช้ client แบบใหม่ของ Mistral
from mistralai import Mistral

load_dotenv()

# ---- API key & model ----
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# ลองอ่านจาก Streamlit secrets ด้วย (กรณี deploy ข้างหน้า)
if not MISTRAL_API_KEY:
    try:
        import streamlit as st
        MISTRAL_API_KEY = st.secrets.get("MISTRAL_API_KEY", MISTRAL_API_KEY)
    except Exception:
        pass

if not MISTRAL_API_KEY:
    raise RuntimeError("MISTRAL_API_KEY not found. Put it in .env OR Streamlit secrets.")

# ตั้งชื่อ model จาก env (ถ้าไม่ตั้งจะใช้ mistral-small-latest เป็น default)
MODEL       = os.getenv("MISTRAL_MODEL") or os.getenv("MODEL", "mistral-small-latest")
SMART_MODEL = os.getenv("MISTRAL_SMART_MODEL") or os.getenv("SMART_MODEL", "mistral-large-latest")

MAX_ANSWER_TOKENS = int(os.getenv("MAX_ANSWER_TOKENS", 320))
MAX_CTX_CHARS     = int(os.getenv("MAX_CTX_CHARS", 4000))
ALLOW_ESCALATE    = os.getenv("ALLOW_ESCALATE", "1") == "1"
REQUEST_TIMEOUT_S = float(os.getenv("REQUEST_TIMEOUT_S", 30))
USER_TAG          = os.getenv("USER_TAG", "fit-assistant")

# สร้าง client ของ Mistral
client = Mistral(api_key=MISTRAL_API_KEY)

SYSTEM = (
  "You are FIT Assistant. Answer ONLY about FIT topics (FWCV, covers, waste logging, "
  "shift settings, app use). "
  "Use the provided context and cite facts as [Q#]. "
  "If the context is missing or unrelated, reply: \"I’m not sure from the current docs.\""
)

def _clean(s: str) -> str:
    return " ".join((s or "").split())

def _clamp_context(chunks: List[Dict]) -> Tuple[str, int]:
    if not chunks:
        return "NO_CONTEXT", 0
    acc, total, used = [], 0, 0
    for i, ch in enumerate(sorted(chunks, key=lambda x: x.get("score", 0), reverse=True), 1):
        q = _clean(ch.get("meta", {}).get("question", ""))
        body = ch.get("text", "")
        block = f"[Q{i}] {q}\n{body}\n\n"
        if total + len(block) > MAX_CTX_CHARS:
            break
        acc.append(block); total += len(block); used += 1
    return ("".join(acc) if acc else "NO_CONTEXT"), used

def _usage_to_dict(u) -> Dict[str, int]:
    """
    พยายามรองรับทั้งรูปแบบเก่า/ใหม่:
    - dict ที่มี prompt_tokens / completion_tokens / total_tokens
    - หรือมี input_tokens / output_tokens
    """
    try:
        if u is None:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if isinstance(u, dict):
            pt = int(u.get("prompt_tokens", u.get("input_tokens", 0)) or 0)
            ct = int(u.get("completion_tokens", u.get("output_tokens", 0)) or 0)
            tt = int(u.get("total_tokens", pt + ct) or (pt + ct))
            return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
        if hasattr(u, "model_dump"):
            return _usage_to_dict(u.model_dump())
        pt = int(getattr(u, "prompt_tokens", getattr(u, "input_tokens", 0)) or 0)
        ct = int(getattr(u, "completion_tokens", getattr(u, "output_tokens", 0)) or 0)
        tt = int(getattr(u, "total_tokens", 0) or (pt + ct))
        return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
    except Exception:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

def _call(model: str, user_q: str, ctx: str) -> Dict:
    # ใช้ message เป็น dict แบบใน docs ของ mistral
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                f"Question: {user_q}\n\nContext:\n{ctx}\n\n"
                "Rules:\n- Be concise and helpful.\n"
                "- Use the context and cite as [Q#].\n"
                "- If unsure, say: 'I’m not sure from the current docs.'"
            ),
        },
    ]

    t0 = time.time()
    try:
        resp = client.chat.complete(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=MAX_ANSWER_TOKENS,
            # SDK ปัจจุบันไม่มี metadata / user parameter แบบ OpenAI
        )
        t1 = time.time()

        # resp.choices[0].message.content เป็นสตริงใน mistralai
        text = (resp.choices[0].message.content or "").strip()
        usage = _usage_to_dict(getattr(resp, "usage", None))

        return {
            "text": text,
            "usage": usage,
            "latency": t1 - t0,
            "model_used": model,
        }

    except Exception as e:
        t1 = time.time()
        return {
            "text": "I’m not sure from the current docs (temporary error). Please try again.",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency": t1 - t0,
            "model_used": model,
            "error": str(e),
        }

def answer_with_llm(user_q: str, chunks: List[Dict]) -> Dict:
    ctx, used = _clamp_context(chunks)
    out = _call(MODEL, user_q, ctx)

    top_score = (chunks[0].get("score", 0.0) if chunks else 0.0)
    need_escalate = ALLOW_ESCALATE and ("not sure" in out["text"].lower()) and top_score >= 0.45

    if need_escalate and SMART_MODEL and SMART_MODEL != MODEL:
        out2 = _call(SMART_MODEL, user_q, ctx)
        if len(out2["text"]) > len(out["text"]):
            u1, u2 = out["usage"], out2["usage"]
            out2["usage"] = {
                "prompt_tokens": u1["prompt_tokens"] + u2["prompt_tokens"],
                "completion_tokens": u1["completion_tokens"] + u2["completion_tokens"],
                "total_tokens": u1["total_tokens"] + u2["total_tokens"],
            }
            out2["ctx_used"] = used
            out2["chunks_used"] = used
            return out2

    out["ctx_used"] = used
    out["chunks_used"] = used
    return out