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

st.set_page_config(
    page_title="FIT Assistant (PUMPUI)",
    page_icon="assets/pumpui.png",  # หรือ Path("assets/pumpui.png")
)

DATA_PATH = Path("data/faq.csv")
LOG_DIR = Path("logs"); LOG_DIR.mkdir(exist_ok=True)
LOG_QNA = LOG_DIR / "qna_log.csv"
LOG_UNK = LOG_DIR / "unanswered.csv"
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "fit@lightblueconsulting.com")

SUPPORT_FALLBACK_MSG = (
    "I’m sorry, but I’m not able to answer this question at the moment. "
    "Please contact our FIT Support Team for assistance.\n\n"
    f"• Contact FIT Support: [{SUPPORT_EMAIL}](mailto:{SUPPORT_EMAIL})\n"
)

def is_low_confidence_text(txt: str) -> bool:
    t = (txt or "").strip().lower()
    if not t or len(t) < 4:
        return True
    hints = [
        "not sure", "i’m not sure", "i am not sure",
        "don't know", "do not know", "unsure",
        "cannot answer", "can't answer"
    ]
    return any(h in t for h in hints)

# ---------- Theme Injection (ปรับ input pill ให้เต็มแถว + typing dots) ----------
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

/* ===== Make chat input pill fill the whole row ===== */
[data-testid="stChatInput"]{ padding:12px 16px !important; }

/* ===== Chat bar (Pill) – ปรับโทนให้กลืนกับพื้นหลัง ===== */
[data-testid="stChatInput"] > div{
  display:flex !important;
  align-items:center;
  gap:10px;
  width:100% !important;
  background:var(--bg-main) !important;
  border:1px solid #FFD7E033 !important;
  border-radius:9999px !important;
  box-shadow:0 4px 14px rgba(0,0,0,.25) !important;
  padding:8px 10px 8px 16px !important;
  overflow:hidden !important;
}
[data-testid="stChatInput"] > div > :first-child{ flex:1 1 auto !important; min-width:0 }
[data-testid="stChatInput"] > div > :last-child{ flex:0 0 auto }
[data-testid="stChatInput"] textarea{
  background:#6A0040!important; color:var(--text-main)!important;
  border: none !important;
  outline: none !important;
  font-family:'Inter',sans-serif;
  width:100% !important; flex:1 1 auto !important;
}
[data-testid="stChatInput"] button{
  background:var(--btn-bg)!important; color:var(--accent)!important;
  border:0!important; border-radius:12px!important; font-weight:600!important;
  font-family:'Poppins',sans-serif; padding:.6rem 1rem!important;
  transition:background .2s, box-shadow .2s;
}
[data-testid="stChatInput"] button:hover{ background:var(--btn-hover)!important; box-shadow:0 0 10px #FFD7E055; }
button[kind="primary"]{ background:var(--btn-bg)!important; color:var(--accent)!important; border:0!important; border-radius:12px!important; font-weight:600!important; }
button[kind="primary"]:hover{ background:var(--btn-hover)!important; box-shadow:0 0 10px #FFD7E044; }

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

/* ===== Quick suggestion chips ===== */
#fit-suggest .stButton > button{
  background: #3A8DFF !important;
  color: #fff !important;
  border: 0 !important;
  border-radius: 999px !important;
  padding: 6px 12px !important;
  font-weight: 600 !important;
  box-shadow: 0 2px 8px rgba(0,0,0,.25) !important;
}
#fit-suggest .stButton > button:hover{
  filter: brightness(1.05);
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(0,0,0,.28) !important;
}
#fit-suggest .stButton{ margin: 2px 6px 8px 0 !important; }
a,.stMarkdown a{ color:var(--accent)!important; text-decoration:none; font-weight:600; }
a:hover{ text-decoration:underline; }
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

# ---------- Floating button: Scroll-to-last-assistant (inject ไปที่ parent) ----------
def inject_scroll_to_latest_button():
    html("""
<script>
(function(){
  let d = document;
  try {
    if (window.parent && window.parent !== window && window.parent.document) {
      void window.parent.document.nodeType;
      d = window.parent.document;
    }
  } catch (e) {}

  if(!d.querySelector('style[data-fit-scroll-style]')){
    const st = d.createElement('style');
    st.setAttribute('data-fit-scroll-style','1');
    st.textContent = `
      #fit-scroll-latest{
        position: fixed; right: 24px; bottom: 120px; z-index: 99999;
        display: none; width: 44px; height: 44px;
        border: 2px solid #000; border-radius: 50%; background:#fff; color:#000;
        box-shadow: 0 6px 16px rgba(0,0,0,0.35);
        cursor: pointer; justify-content: center; align-items: center;
        transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
      }
      #fit-scroll-latest:hover{ transform: translateY(-2px); box-shadow:0 10px 22px rgba(0,0,0,0.45); }
      #fit-scroll-latest svg{ width: 22px; height: 22px; }
    `;
    (d.head || d.body).appendChild(st);
  }

  if(!d.getElementById('fit-scroll-latest')){
    const btn = d.createElement('button');
    btn.id = 'fit-scroll-latest';
    btn.title = 'Scroll to latest AI message';
    btn.setAttribute('aria-label','Scroll to latest AI message');
    btn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 5v14"></path>
        <path d="m19 12-7 7-7-7"></path>
      </svg>
    `;
    d.body.appendChild(btn);
  }

  const btn  = d.getElementById('fit-scroll-latest');

  function getAssistantNodesSorted(){
    const nodes = Array.from(d.querySelectorAll('[data-fit-role="assistant"]'))
      .filter(el => el.offsetParent !== null);
    nodes.sort((a,b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
    return nodes;
  }

  function scrollToLastAssistant(){
    const nodes = getAssistantNodesSorted();
    if (nodes.length){
      nodes[nodes.length-1].scrollIntoView({ behavior: "smooth", block: "end" });
    } else {
      const root = d.scrollingElement || d.documentElement || d.body;
      root.scrollTo({ top: root.scrollHeight, behavior: "smooth" });
    }
  }

  function nearBottom(){
    const root = d.scrollingElement || d.documentElement || d.body;
    return ((root.scrollTop || 0) + window.innerHeight + 120) >= root.scrollHeight;
  }

  function refreshButton(){
    if (!btn) return;
    const hasAssistant = getAssistantNodesSorted().length > 0;
    btn.style.display = (hasAssistant && !nearBottom()) ? "flex" : "none";
  }

  btn.addEventListener("click", scrollToLastAssistant);
  window.addEventListener("scroll",  refreshButton, true);
  window.addEventListener("resize",  refreshButton, true);
  new MutationObserver(() => setTimeout(refreshButton, 50))
    .observe(d.body, {childList:true, subtree:true});
  setTimeout(refreshButton, 0);
})();
</script>
    """, height=0)

# ---------- Auto-scroll ONLY the last assistant bubble ----------
def scroll_to_last_assistant():
    html("""
    <script>
    (function(){
      const d = document;

      function getScrollContainer(){
        const candSel = [
          '[data-testid="stAppViewContainer"]',
          '.main',
          'body',
          'html'
        ];
        for(const sel of candSel){
          const el = d.querySelector(sel);
          if(!el) continue;
          const sh = el.scrollHeight || 0;
          const ch = el.clientHeight || 0;
          if(sh - ch > 5) return el;
        }
        return d.scrollingElement || d.documentElement || d.body;
      }

      const container = getScrollContainer();
      const nodes = Array.from(d.querySelectorAll('[data-fit-role="assistant"]'))
        .filter(el => el.offsetParent !== null)
        .sort((a,b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);

      if(nodes.length){
        const target = nodes[nodes.length-1];
        const rect = target.getBoundingClientRect();
        const crec = container.getBoundingClientRect ? container.getBoundingClientRect() : {top:0};
        const top  = (rect.top - crec.top) + (container.scrollTop || 0) - 60;
        container.scrollTo({ top, behavior: "smooth" });
      }
    })();
    </script>
    """, height=0)

# เรียก injects
inject_theme()
inject_scroll_to_latest_button()

# ---------- Data check ----------
@st.cache_data
def load_faq():
    if not DATA_PATH.exists():
        st.error(f"FAQ file not found: {DATA_PATH}")
        return []

    # ลองอ่านด้วย utf-8 ก่อน ถ้าไม่ได้ค่อย fallback
    encodings_to_try = ["utf-8", "utf-8-sig", "cp1252", "latin1"]
    last_err = None
    for enc in encodings_to_try:
        try:
            df = pd.read_csv(DATA_PATH, encoding=enc)
            break
        except UnicodeDecodeError as e:
            last_err = e
            continue
    else:
        # ถ้าอ่านไม่ได้ทุก encoding ให้แจ้ง error ชัด ๆ
        st.error(
            f"Cannot read FAQ CSV with UTF-8/UTF-8-SIG/CP1252/LATIN1. "
            f"Please re-save {DATA_PATH.name} as UTF-8. Last error: {last_err}"
        )
        return []

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
            if i == 0 and line.startswith("ts"):
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

# suggestion display mode: แค่ top หรือ hidden
if "sugg_mode" not in st.session_state:
    st.session_state.sugg_mode = "top"  # top | hidden

# --- scroll-after-rerun flag ---
def request_scroll_next_run():
    st.session_state["__scroll_after__"] = True

# a single source of truth for questions
SUGGESTED_QS = [
    "How can I export my data?",
    "How do I add cover data?",
    "How do I add food waste data?",
    "How do I edit a data entry?",
    "Why is my data consistency low?",
    "Why is my data not showing on the dashboard?",
]

def render_suggestions_top():
    """Show chips on top only when mode == 'top'."""
    if st.session_state.sugg_mode != "top" or not SUGGESTED_QS:
        return
    st.markdown("**Quick help:** Choose a common question:")
    with st.container():
        st.markdown('<div id="fit-suggest">', unsafe_allow_html=True)
        cols = st.columns(5)
        for i, q in enumerate(SUGGESTED_QS):
            c = cols[i % len(cols)]
            if c.button(q, key=f"sugg_top_{i}"):
                st.session_state["queued_msg"] = q
                st.session_state.sugg_mode = "hidden"
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ---------- UI ----------
col_logo, col_title = st.columns([1, 4])

with col_logo:
    st.image("assets/pumpui.png", width=80)   # ปรับขนาดตามที่ถูกใจ

with col_title:
    st.title("FIT Assistant (PUMPUI)")
    #st.caption("Ask anything about using FIT – covers, food waste logs, reports, etc.")

# หน้าแรก (ยังไม่มี history) และโหมดยังเป็น top → แสดงชิปบนสุด
if not st.session_state.history and st.session_state.sugg_mode == "top":
    render_suggestions_top()

# แสดง history
for role, msg in st.session_state.history:
    with st.chat_message(role):
        if role == "assistant":
            st.markdown(f'<div data-fit-role="assistant">{msg}</div>', unsafe_allow_html=True)
        else:
            st.markdown(msg)

user_msg = st.chat_input("Ask something about FIT…")

# ถ้ามีข้อความที่คิวไว้จากการกดชิป ให้ใช้แทน
queued = st.session_state.pop("queued_msg", None)
if queued and not user_msg:
    user_msg = queued

# พิมพ์เอง -> ซ่อนชิประหว่างถาม
if user_msg and queued is None:
    st.session_state.sugg_mode = "hidden"

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

    # Greetings / very short  ---- early-exit → hide suggestions
    if qn in GREETINGS or len(qn) < 3:
        reply = "Hi! Ask me about FIT (e.g., “What is FWCV?” or “When do I enter covers?”)."
        st.session_state.history.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.markdown(f'<div data-fit-role="assistant">{reply}</div>', unsafe_allow_html=True)
        st.session_state.sugg_mode = "hidden"
        request_scroll_next_run()
        st.rerun()

    # Daily budget  ---- early-exit → hide suggestions
    if tokens_today_from_log(LOG_QNA) > DAILY_TOKEN_BUDGET:
        reply = "Daily AI budget is reached. Please try again tomorrow."
        st.session_state.history.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.markdown(f'<div data-fit-role="assistant">{reply}</div>', unsafe_allow_html=True)
        st.session_state.sugg_mode = "hidden"
        request_scroll_next_run()
        st.rerun()

    # Cache  ---- early-exit → hide suggestions
    cached = st.session_state.qa_cache.get(qn)
    if cached:
        reply = cached
        st.session_state.history.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.markdown(f'<div data-fit-role="assistant">{reply}</div>', unsafe_allow_html=True)
        st.session_state.sugg_mode = "hidden"
        request_scroll_next_run()
        st.rerun()

    # --- Retrieve ---
    hits = retrieve(user_msg, k=TOP_K, min_sim=MIN_SIM)

    # Retrieval debug
    #with st.expander("🔎 Retrieval debug"):
    #    st.write([
    #        {"score": round(h["score"], 3),
    #         "q": h["meta"].get("question","")[:120]}
    #        for h in (hits or [])
    #    ])

    # Gate by similarity (fallback with contact)  ---- early-exit → hide suggestions
    if not hits or hits[0]["score"] < MIN_SIM:
        reply = SUPPORT_FALLBACK_MSG
        log_unanswered(user_msg, hits or [])
        st.session_state.history.append(("assistant", reply))
        with st.chat_message("assistant"):
            st.markdown(f'<div data-fit-role="assistant">{reply}</div>', unsafe_allow_html=True)
        st.session_state.sugg_mode = "hidden"
        request_scroll_next_run()
        st.rerun()

    # --- LLM ---  “กำลังคิด…” แล้วแทนที่ด้วยคำตอบในบับเบิลเดิม (ไม่ rerun ตรงนี้)
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

        result = answer_with_llm(user_msg, hits)
        reply   = result.get("text", "")
        usage   = result.get("usage", {})
        latency = result.get("latency", 0.0)

        # ลบ citation tag [Q1][Q2] ออก
        import re
        reply = re.sub(r"\[Q\d+\]", "", reply).strip()

        # ถ้าคำตอบไม่มั่นใจ → แทนด้วยข้อความติดต่อทีม + log เป็น unanswered
        if is_low_confidence_text(reply):
            log_unanswered(user_msg, hits)
            reply = SUPPORT_FALLBACK_MSG

        thinking.markdown(f'<div data-fit-role="assistant">{reply}</div>', unsafe_allow_html=True)

        # เก็บลง history + ซ่อน suggestion + ขอเลื่อน
        st.session_state.history.append(("assistant", reply))
        st.session_state.sugg_mode = "hidden"
        request_scroll_next_run()

    # Error debug (optional)
    if result.get("error"):
        with st.expander("⚠️ LLM error (debug)"):
            st.code(result["error"])

    # Spend tracking
    spent = (usage.get("total_tokens")
             or (usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)))
    try:
        st.session_state.token_spent += int(spent or 0)
    except:
        pass

    if st.session_state.token_spent > SESSION_TOKEN_BUDGET:
        st.warning("Session token budget reached. Further questions may be limited.")

    # Log / unanswered
    if (reply == SUPPORT_FALLBACK_MSG) or (not reply) or (hits[0]["score"] < max(MIN_SIM, 0.36)):
        log_unanswered(user_msg, hits)
    log_qna(user_msg, hits, reply, usage, latency)

    # Cache good answers (avoid caching fallback)
    if reply and (reply != SUPPORT_FALLBACK_MSG) and ("not sure" not in reply.lower()):
        st.session_state.qa_cache[qn] = reply

# ---------- สั่งเลื่อน (ท้ายสุดของไฟล์เสมอ) ----------
if st.session_state.pop("__scroll_after__", False):
    scroll_to_last_assistant()