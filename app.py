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
    # Widget Card Theme (White/Blue) - Adjusted for FAQ Browser
    css = r"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap');
    
    header { visibility: hidden !important; }
    
    :root {
        --bg-main: #F4F6F8;
        --widget-bg: #FFFFFF;
        --text-main: #1A1A2E;
        --text-light: #6B7280;
        --accent: #00D4FF;
        --border-color: #E6E8EB;
    }
    
    .stApp {
        background-color: var(--bg-main) !important;
        font-family: 'Outfit', sans-serif !important;
        color: var(--text-main) !important;
    }
    
    /* Widget Card Simulation */
    .block-container {
        background-color: var(--widget-bg);
        max-width: 450px !important;
        margin: 2rem auto;
        padding: 2rem !important;
        border-radius: 16px;
        /* Blue Glow Shadow */
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.15), 0 0 0 1px rgba(0, 212, 255, 0.1); 
        min-height: 80vh;
    }

    /* Standard Buttons (List Items) */
    .stButton > button {
        background-color: #FFFFFF !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        padding: 1rem 1rem !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        width: 100% !important;
        display: flex !important;
        justify-content: flex-start !important;
        text-align: left !important;
        margin-bottom: 0.6rem !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        border-color: var(--accent) !important;
        color: var(--accent) !important;
        background-color: #F8FDFF !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 212, 255, 0.15) !important;
    }

    /* Blue Icon Styling Helper */
    /* Since we can't style emojis easily, we use a span in markdown or just use a specific character like ➤ */
    
    /* ... rest of CSS ... */
    
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
if "view" not in st.session_state:
    st.session_state.view = "home" # home, subcategory, question_list, article
if "context" not in st.session_state:
    st.session_state.context = {} # stores 'cat', 'sub', 'q_item'

def navigate(view_name, **kwargs):
    st.session_state.view = view_name
    for k, v in kwargs.items():
        st.session_state.context[k] = v

def go_back():
    current = st.session_state.view
    if current == "article":
        navigate("question_list")
    elif current == "question_list":
        navigate("subcategory")
    elif current == "subcategory":
        navigate("home")

# --- Views ---
def render_header(title, subtitle=None, show_back=False):
    if show_back:
        if st.button("⬅ Back", key="nav_back"):
            go_back()
            st.rerun()
            
    st.markdown(f"### {title}")
    if subtitle:
        st.markdown(f"<div class='subtitle'>{subtitle}</div>", unsafe_allow_html=True)
    st.write("") # spacer

# Helper for Blue Icon
def icon(label):
    return f"🔹 {label}"

def render_home(data_tree):
    # Header
    c_logo, c_text = st.columns([1, 5])
    with c_logo:
        if ASSETS_PATH.exists():
            st.image(str(ASSETS_PATH), width=80)
        else:
            st.write("🤖")
    with c_text:
        st.markdown("### FIT Support")
        st.markdown("<div class='subtitle'>How can we help you today?</div>", unsafe_allow_html=True)

    st.write("---")
    
    # Categories
    cats = sorted(data_tree.keys())
    for i, cat in enumerate(cats):
        if st.button(f"🔹 {cat}", key=f"home_cat_{i}"):
            navigate("subcategory", cat=cat)
            st.rerun()

def render_subcategory(data_tree):
    cat = st.session_state.context.get("cat")
    render_header(title=cat, subtitle="Select a topic", show_back=True)
    
    subcats = data_tree.get(cat, {})
    for i, sub in enumerate(sorted(subcats.keys())):
        if st.button(f"🔹 {sub}", key=f"sub_{i}"):
            navigate("question_list", sub=sub)
            st.rerun()

def render_question_list(data_tree):
    cat = st.session_state.context.get("cat")
    sub = st.session_state.context.get("sub")
    render_header(title=sub, subtitle=f"In {cat}", show_back=True)
    
    questions = data_tree.get(cat, {}).get(sub, [])
    for i, item in enumerate(questions):
        if st.button(f"📄 {item['q']}", key=f"q_{i}"):
            navigate("article", q_item=item)
            st.rerun()

def render_article(data_tree):
    cat = st.session_state.context.get("cat")
    sub = st.session_state.context.get("sub")
    item = st.session_state.context.get("q_item")
    
    render_header(title=item['q'], show_back=True)
    
    # Answer Content
    ans_html = item['a'].replace("\n", "<br>")
    st.markdown(f"<div class='article-box'>{ans_html}</div>", unsafe_allow_html=True)
    
    # Related Articles
    st.markdown("#### Related Articles")
    questions = data_tree.get(cat, {}).get(sub, [])
    related = [q for q in questions if q['q'] != item['q']]
    
    if not related:
        st.caption("No related articles found.")
        
    for i, r_item in enumerate(related):
        if st.button(r_item['q'], key=f"rel_{i}"):
            navigate("article", q_item=r_item)
            st.rerun()
            
    st.write("---")
    if st.button("🏠 Home", key="art_home"):
        navigate("home")
        st.rerun()

# --- Main App ---
def main():
    inject_theme()
    data_tree = load_faq_data()
    
    view = st.session_state.view
    
    if view == "home":
        render_home(data_tree)
    elif view == "subcategory":
        render_subcategory(data_tree)
    elif view == "question_list":
        render_question_list(data_tree)
    elif view == "article":
        render_article(data_tree)

if __name__ == "__main__":
    main()