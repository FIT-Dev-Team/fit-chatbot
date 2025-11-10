# app.py
import os, csv, time, datetime as dt
import streamlit as st
import pandas as pd
from pathlib import Path
from streamlit.components.v1 import html
from dotenv import load_dotenv


load_dotenv()

# RAG & LLM
from retrieval import retrieve
from llm import answer_with_llm

# --- Config (env overrides) ---
MIN_SIM = float(os.getenv("MIN_SIM", 0.34))
TOP_K = int(os.getenv("TOP_K", 4))
SESSION_TOKEN_BUDGET = int(os.getenv("SESSION_TOKEN_BUDGET", 30000))
DAILY_TOKEN_BUDGET = int(os.getenv("DAILY_TOKEN_BUDGET", 300000))

st.set_page_config(page_title="FIT Assistant (RAG + LLM)", page_icon="🍽️")

DATA_PATH = Path("data/faq.csv")
LOG_DIR = Path("logs"); LOG_DIR.mkdir(exist_ok=True)
LOG_QNA = LOG_DIR / "qna_log.csv"
LOG_UNK = LOG_DIR / "unanswered.csv"
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "fit@lightblueconsulting.com")

# ---------- Theme Injection ----------
def inject_theme():
    css = r"""
:root{
  --bg-main:#7C0046; --bg-bubble:#8A0053;
  --text-main:#FFD7E0; --text-soft:#F7F3CE;
  --accent:#F7F3CE; --btn-bg:#A6005A; --btn-hover:#C20068;
}
html, body, .stApp, [data-testid="stAppViewContainer"], .block-container, .main{
  background:var(--bg-main)!important; color:var(--text-main)!important;
  background-image:none!important; font-family:'Poppins','Inter',sans-serif;
}
[data-testid="stSidebar"] > div:first-child{ background:var(--bg-main)!important; border-right:none!important; }
#MainMenu, footer, header{ visibility:hidden; }
h1,h2,h3,h4{ color:var(--accent)!important; text-shadow:0 0 10px #FFD7E055; font-weight:700; }
.block-container .caption,.stCaption{ color:var(--text-soft)!important; }
[data-testid="stChatMessage"]{
  border:1px solid #FFD7E055; border-radius:10px; background:var(--bg-bubble)!important;
  box-shadow:0 0 10px #FFD7E033; padding:.8rem 1rem; margin-bottom:.5rem;
}
[data-testid="stChatMessage"] .stMarkdown{ color:var(--text-main)!important; }
[data-testid="stChatInput"] textarea{
  background:#6A0040!important; color:var(--text-main)!important;
  border:1px solid #FFD7E066!important; border-radius:8px!important; font-family:'Inter',sans-serif;
}
[data-testid="stChatInput"] button{
  background:var(--btn-bg)!important; color:var(--accent)!important;
  border:0!important; border-radius:12px!important; font-weight:600!important;
  font-family:'Poppins',sans-serif; padding:.6rem 1rem!important; transition:background .2s, box-shadow .2s;
}
/* typing dots */
.typing{ display:inline-flex; align-items:center; gap:8px; line-height:1 }
.typing .dots{ display:inline-flex; gap:6px }
.typing .dot{
  width:6px; height:6px; border-radius:50%;
  background:var(--accent); opacity:.3;
  display:inline-block; animation:typingBlink 1s infinite ease-in-out
}
.typing .dot:nth-child(2){ animation-delay:.15s }
.typing .dot:nth-child(3){ animation-delay:.30s }
.typing .txt{ opacity:.9; font-weight:600 }
@keyframes typingBlink{
  0%,100%{ opacity:.25; transform: translateY(0) }
  50%{    opacity:1;   transform: translateY(-3px) }
}
[data-testid="stChatInput"] button:hover{ background:var(--btn-hover)!important; box-shadow:0 0 10px #FFD7E055; }
button[kind="primary"]{ background:var(--btn-bg)!important; color:var(--accent)!important; border:0!important; border-radius:12px!important; font-weight:600!important; }
button[kind="primary"]:hover{ background:var(--btn-hover)!important; box-shadow:0 0 10px #FFD7E044; }
a,.stMarkdown a{ color:var(--accent)!important; text-decoration:none; font-weight:600; } a:hover{ text-decoration:underline; }
"""
    html(f"""
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<script>
const css = `{css}`;
(function inject(){{
  try{{
    const s = document.createElement('style');
    s.setAttribute('data-fit-theme','burgundy'); s.innerHTML = css;
    const head = window.parent?.document?.head || document.head;
    if(!head.querySelector('style[data-fit-theme="burgundy"]')) head.appendChild(s);
  }}catch(_){{
    const s2 = document.createElement('style'); s2.innerHTML = css; document.head.appendChild(s2);
  }}
}})();
</script>
""", height=0)

inject_theme()

# ---------- Auto-scroll ONLY the last assistant bubble ----------
def scroll_to_last_assistant():
    html("""
    <script>
    (function(){
      const d = window.parent?.document || document;
      // หาเฉพาะคอนเทนเนอร์ที่เราห่อไว้ของผู้ช่วย
      const as = d.querySelectorAll('[data-fit-role="assistant"]');
      if (as && as.length){
        as[as.length-1].scrollIntoView({behavior:'smooth', block:'end'});
      }
    })();
    </script>
    """, height=0)

# ---------- Data check ----------
@st.cache_data
def load_faq():
    if not DATA_PATH.exists():
        st.error(f"FAQ file not found: {DATA_PATH}")
        return []
    df = pd.read_csv(DATA_PATH)
    if not {"Question", "Answer"}.issubset(df.columns):
        st.error("CSV must contain 'Question' and 'Answer' columns.")
        return []
    return df.to_dict(orient="records")
_ = load_faq()

# ---------- Logging ----------
def write_csv(path: Path, header: list, row: list):
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(header)
        w.writerow(row)

def log_qna(user_q, hits, answer, usage, latency):
    header = ["ts","question","top_scores","answer_preview","total_tokens","latency_s"]
    row = [
        dt.datetime.utcnow().isoformat(),
        user_q,
        [round(h["score"],3) for h in hits][:3],
        (answer[:160] + "…") if answer else "",
        (usage or {}).get("total_tokens",""),
        round(latency or 0.0, 3)
    ]
    write_csv(LOG_QNA, header, row)

def log_unanswered(user_q, hits):
    header = ["ts","question","top_scores"]
    row = [dt.datetime.utcnow().isoformat(), user_q,
           [round(h["score"],3) for h in hits][:3]]
    write_csv(LOG_UNK, header, row)

def today_str():
    return dt.datetime.utcnow().strftime("%Y-%m-%d")

def tokens_today_from_log(path: Path) -> int:
    if not path.exists(): return 0
    total = 0
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0 and line.startswith("ts"):  # header
                continue
            cols = [c.strip() for c in line.rstrip("\n").split(",")]
            if not cols: continue
            if cols[0].startswith(today_str()):
                try: total += int(cols[4] or 0)
                except: pass
    return total

# ---------- Session ----------
if "history" not in st.session_state: st.session_state.history = []
if "qa_cache" not in st.session_state: st.session_state.qa_cache = {}
if "token_spent" not in st.session_state: st.session_state.token_spent = 0
if "last_ask_ts" not in st.session_state: st.session_state.last_ask_ts = 0.0

def norm_q(s: str) -> str:
    return " ".join((s or "").lower().strip().split())

GREETINGS = {"hi","hello","hey","สวัสดี","หวัดดี"}

# ---------- UI ----------
st.title("💬 FIT Assistant (FIT AI HELPER)")

st.caption("Grounded answers from your FIT FAQ with [Q#] citations. Low-confidence questions are logged for review.")

for role, msg in st.session_state.history:
    with st.chat_message(role):
        st.markdown(msg)

user_msg = st.chat_input("Ask something about FIT…")

if user_msg:
    # Debounce
    now = time.time()
    if now - st.session_state.last_ask_ts < 0.75:
        st.warning("Please wait a moment before asking again.")
        st.stop()
    st.session_state.last_ask_ts = now

    st.session_state.history.append(("user", user_msg))
    with st.chat_message("user"):
        st.markdown(user_msg)

    qn = norm_q(user_msg)

    # Greetings / very short
    if qn in GREETINGS or len(qn) < 3:
        reply = "Hi! Ask me about FIT (e.g., “What is FWCV?” or “When do I enter covers?”)."
        st.session_state.history.append(("assistant", reply))
        with st.chat_message("assistant"):
            # ✨ ห่อด้วย data-fit-role="assistant" เพื่อให้ scroll เจอ
            st.markdown(f'<div data-fit-role="assistant">{reply}</div>', unsafe_allow_html=True)
        scroll_to_last_assistant()
        st.stop()

    # Daily budget
    if tokens_today_from_log(LOG_QNA) > DAILY_TOKEN_BUDGET:
        reply = "Daily AI budget is reached. Please try again tomorrow."
        st.session_state.history.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.markdown(f'<div data-fit-role="assistant">{reply}</div>', unsafe_allow_html=True)
        scroll_to_last_assistant()
        st.stop()

    # Cache
    cached = st.session_state.qa_cache.get(qn)
    if cached:
        reply = cached
        st.session_state.history.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.markdown(f'<div data-fit-role="assistant">{reply}</div>', unsafe_allow_html=True)
        scroll_to_last_assistant()
        st.stop()

    # --- Retrieve ---
    hits = retrieve(user_msg, k=TOP_K, min_sim=MIN_SIM)

    # Retrieval debug (FIXED INDENT)
    with st.expander("🔎 Retrieval debug"):
        st.write([
            {"score": round(h["score"], 3),
             "q": h["meta"].get("question","")[:120]}
            for h in (hits or [])
        ])

    # Gate by similarity (fallback with contact)
    if not hits or hits[0]["score"] < MIN_SIM:
        reply = (
            "I’m sorry, but I’m not able to answer this question at the moment. Please contact our FIT Support Team for assistance.\n\n"
            f"• Contact FIT Support: [{SUPPORT_EMAIL}](mailto:{SUPPORT_EMAIL})\n"
        )
        log_unanswered(user_msg, hits or [])
        st.session_state.history.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.markdown(f'<div data-fit-role="assistant">{reply}</div>', unsafe_allow_html=True)
        scroll_to_last_assistant()
        st.stop()

    # --- LLM ---  ✅ แสดง “กำลังคิด…” และเลื่อนเฉพาะบับเบิลผู้ช่วย
    with st.chat_message("assistant"):
        thinking = st.empty()
        thinking.markdown(
            '''
            <div data-fit-role="assistant">
              <div class="typing" aria-live="polite" aria-label="Assistant is typing">
                <span class="dots">
                  <i class="dot"></i><i class="dot"></i><i class="dot"></i>
                </span>
                <span class="txt">Thinking…</span>
              </div>
            </div>
            ''',
            unsafe_allow_html=True
        )
        scroll_to_last_assistant()

        result = answer_with_llm(user_msg, hits)
        reply = result.get("text", "")
        usage = result.get("usage", {})
        latency = result.get("latency", 0.0)

        # แทนที่บับเบิลเดิมด้วยคำตอบ (ยังห่อด้วย data-fit-role="assistant")
        thinking.markdown(f'<div data-fit-role="assistant">{reply}</div>', unsafe_allow_html=True)
        scroll_to_last_assistant()

    # Error debug (optional)
    if result.get("error"):
        with st.expander("⚠️ LLM error (debug)"):
            st.code(result["error"])

    # Spend tracking
    spent = (usage.get("total_tokens")
             or (usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)))
    try: st.session_state.token_spent += int(spent or 0)
    except: pass

    if st.session_state.token_spent > SESSION_TOKEN_BUDGET:
        st.warning("Session token budget reached. Further questions may be limited.")

    # Log / unanswered
    if (not reply) or ("not sure" in reply.lower()) or (hits[0]["score"] < max(MIN_SIM, 0.36)):
        log_unanswered(user_msg, hits)
    log_qna(user_msg, hits, reply, usage, latency)

    # Cache good answers
    if reply and "not sure" not in reply.lower():
        st.session_state.qa_cache[qn] = reply

    # บันทึกลง history (เก็บเฉพาะข้อความ ไม่ต้องห่อ div ตรงนี้)
    st.session_state.history.append(("assistant", reply))

# ---------- Floating scroll-to-latest button ----------
html("""
<style>
#scroll-to-latest {
  position: fixed;
  right: 24px;
  bottom: 90px;
  z-index: 9997;
  background: var(--btn-bg, #A6005A);
  color: var(--accent, #F7F3CE);
  border: none;
  border-radius: 999px;
  padding: 10px 14px;
  font-weight: 600;
  font-family: 'Poppins', sans-serif;
  box-shadow: 0 4px 12px #0004;
  cursor: pointer;
  transition: all .2s ease;
}
#scroll-to-latest:hover {
  background: var(--btn-hover, #C20068);
  box-shadow: 0 0 10px #fff4;
}
</style>

<button id="scroll-to-latest" title="Scroll to latest reply">⬇ Latest</button>

<script>
(function(){
  const btn = document.getElementById('scroll-to-latest');
  const d = window.parent?.document || document;

  // คลิกแล้วเลื่อนไป assistant bubble สุดท้าย
  btn.onclick = () => {
    const as = d.querySelectorAll('[data-fit-role="assistant"]');
    if(as && as.length){
      as[as.length-1].scrollIntoView({behavior:'smooth', block:'end'});
    }
  };

  // ซ่อน/แสดงปุ่มตามตำแหน่ง scroll (ถ้าอยู่ใกล้ล่างสุดก็ซ่อน)
  const root = d.scrollingElement || d.documentElement;
  const toggleBtn = () => {
    const nearBottom = root.scrollTop >= (root.scrollHeight - window.innerHeight - 400);
    btn.style.display = nearBottom ? 'none' : 'block';
  };
  window.addEventListener('scroll', toggleBtn, true);
  toggleBtn();
})();
</script>
""", height=0)