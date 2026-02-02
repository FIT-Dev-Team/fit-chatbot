import streamlit as st
import pandas as pd
import os
from pathlib import Path

# --- Config & Path ---
BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "data" / "faq_decision_tree.csv"
ASSETS_PATH = BASE_DIR / "assets" / "pumpui.png"

st.set_page_config(
    page_title="FIT Assistant",
    page_icon=str(ASSETS_PATH) if ASSETS_PATH.exists() else "🤖", 
    layout="centered"
)

# --- Theme Injection ---
def inject_theme():
    # Futuristic Light Theme + Chat Bubbles
    css = r"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    header { visibility: hidden !important; }
    
    :root {
        --bg-main: #F8F9FF;
        --text-main: #1A1A2E;
        --accent: #00D4FF;
        --user-bubble: #00D4FF;
        --bot-bubble: #FFFFFF;
    }
    
    .stApp {
        background-color: var(--bg-main) !important;
        color: var(--text-main) !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Buttons (Options) */
    .stButton > button {
        background-color: #FFFFFF !important;
        color: var(--text-main) !important;
        border: 1px solid var(--accent) !important;
        border-radius: 20px !important; /* Pill shape */
        padding: 0.5rem 1rem !important;
        font-size: 0.9rem !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
        transition: all 0.2s ease !important;
        margin-bottom: 0.5rem !important;
    }
    
    .stButton > button:hover {
        background-color: var(--accent) !important;
        color: #FFFFFF !important;
        transform: translateY(-2px);
    }
    
    /* Chat Bubbles */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        margin-bottom: 2rem;
    }
    
    .chat-bubble {
        padding: 1rem 1.2rem;
        border-radius: 16px;
        max-width: 80%;
        line-height: 1.5;
        font-size: 1rem;
        position: relative;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    .chat-bubble.bot {
        align-self: flex-start;
        background-color: var(--bot-bubble);
        color: var(--text-main);
        border-bottom-left-radius: 4px;
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    .chat-bubble.user {
        align-self: flex-end;
        background-color: var(--user-bubble);
        color: #FFFFFF;
        border-bottom-right-radius: 4px;
        text-align: right;
    }
    
    /* Avatar */
    .bot-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        margin-right: 8px;
        vertical-align: middle;
    }
    
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# --- Data Loading ---
@st.cache_data
def load_faq_data():
    if not DATA_PATH.exists(): return {}
    try:
        df = pd.read_csv(DATA_PATH)
        df.columns = [c.strip() for c in df.columns]
        tree = {}
        for _, row in df.iterrows():
            cat = str(row["Category"]).strip()
            sub = str(row["Subcategory"]).strip()
            qst = str(row["Question"]).strip()
            ans = str(row["Answer"]).strip()
            if not cat or not sub or not qst: continue
            
            if cat not in tree: tree[cat] = {}
            if sub not in tree[cat]: tree[cat][sub] = []
            tree[cat][sub].append({"q": qst, "a": ans})
        return tree
    except: return {}

# --- State Management ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi there! 👋 I'm Pumpui, your FIT Assistant.\n\nHow can I help you today?"}
    ]
if "current_options" not in st.session_state:
    st.session_state.current_options = {"type": "category"} # type: category, subcategory, question, none

# Helper to append user msg and bot response
def handle_selection(label, next_type, next_data=None):
    # 1. User message
    st.session_state.messages.append({"role": "user", "content": label})
    
    # 2. Logic for next step
    if next_type == "subcategory":
        st.session_state.messages.append({"role": "assistant", "content": f"Sure, what about **{label}**?"})
        st.session_state.current_options = {"type": "subcategory", "data": label}
        
    elif next_type == "question":
        st.session_state.messages.append({"role": "assistant", "content": "Please select a specific question:"})
        st.session_state.current_options = {"type": "question", "cat": next_data, "sub": label}
        
    elif next_type == "answer":
        # Find answer
        ans = next_data['a'].replace("\n", "\n\n")
        st.session_state.messages.append({"role": "assistant", "content": ans})
        
        # Determine if we show a "Back" or "Reset" options, or just nothing (end of flow)
        # Check correctness of flow: usually we might want to ask "Anything else?"
        st.session_state.messages.append({"role": "assistant", "content": "Is there anything else I can help with?"})
        st.session_state.current_options = {"type": "reset"}

def reset_chat():
    st.session_state.messages = [
        {"role": "assistant", "content": "How else can I help you?"}
    ]
    st.session_state.current_options = {"type": "category"}

def back_step():
    # Simplistic back: just reset to main menu for now or implement stack if needed
    # For this iteration, "Start Over" is safer.
    reset_chat()

# --- Main App ---
def main():
    inject_theme()
    data_tree = load_faq_data()
    
    # 1. Render History
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        
        if role == "assistant":
            # Bot Bubble
            avatar_html = ""
            if ASSETS_PATH.exists():
                # We can't use local path in HTML directly easily without base64, 
                # but we can use st.image col layout or Streamlit's chat_message.
                # Let's use Streamlit's native chat_message which handles avatars nicely now.
                with st.chat_message("assistant", avatar=str(ASSETS_PATH)):
                    st.markdown(content)
            else:
                 with st.chat_message("assistant"):
                    st.markdown(content)
        else:
            # User Bubble
            with st.chat_message("user"):
                st.markdown(content)

    # 2. Render Options (Buttons) at bottom
    # We use a container to keep it separate
    st.write("---")
    
    opt_type = st.session_state.current_options.get("type")
    
    if opt_type == "category":
        cats = sorted(data_tree.keys())
        cols = st.columns(2)
        for i, cat in enumerate(cats):
            if cols[i%2].button(cat, key=f"btn_cat_{i}"):
                handle_selection(cat, "subcategory")
                st.rerun()

    elif opt_type == "subcategory":
        cat = st.session_state.current_options.get("data")
        subcats = data_tree.get(cat, {})
        
        # Back/Reset
        if st.button("⬅️ Start Over"):
            reset_chat()
            st.rerun()

        cols = st.columns(2)
        for i, sub in enumerate(sorted(subcats.keys())):
            if cols[i%2].button(sub, key=f"btn_sub_{i}"):
                handle_selection(sub, "question", next_data=cat)
                st.rerun()

    elif opt_type == "question":
        cat = st.session_state.current_options.get("cat")
        sub = st.session_state.current_options.get("sub")
        questions = data_tree.get(cat, {}).get(sub, [])
        
        if st.button("⬅️ Start Over"):
            reset_chat()
            st.rerun()
            
        for i, item in enumerate(questions):
            if st.button(item['q'], key=f"btn_q_{i}"):
                handle_selection(item['q'], "answer", next_data=item)
                st.rerun()

    elif opt_type == "reset":
        if st.button("🔄 Start New Conversation"):
            reset_chat()
            st.rerun()

if __name__ == "__main__":
    main()