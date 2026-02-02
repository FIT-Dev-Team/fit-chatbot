import streamlit as st
import pandas as pd
from pathlib import Path

# --- Config & Path ---
import os
# --- Config & Path ---
DATA_PATH = Path(os.path.join("data", "faq_decision_tree.csv"))

st.set_page_config(
    page_title="FIT Assistant",
    page_icon="assets/pumpui.png", 
    layout="centered"
)

# --- Theme Injection (Burgundy) ---
def inject_theme():
    # Futuristic Light Theme (Total Overhaul)
    css = r"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    /* Hide Streamlit topmost decoration bar and hamburger menu if desired */
    header {
        visibility: hidden !important;
    }
    
    /* Force overrides of Streamlit theme variables */
    :root {
        --primary-color: #00D4FF !important;
        --bg-main: #F8F9FF;
        --text-main: #1A1A2E;
        --accent: #00D4FF;
        --glass-bg: #FFFFFF;
        --glass-border: rgba(0, 212, 255, 0.4);
    }
    
    .stApp {
        background-color: var(--bg-main) !important;
        color: var(--text-main) !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Titles and Headers */
    h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: var(--text-main) !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }
    
    .stMarkdown, p, label, div, span {
        color: var(--text-main) !important;
    }

    /* Primary Buttons */
    .stButton > button {
        background-color: #FFFFFF !important;
        color: var(--text-main) !important;
        border: 1px solid var(--accent) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1rem !important;
        box-shadow: 0 0 10px rgba(0, 212, 255, 0.15) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        background-color: var(--accent) !important;
        color: #FFFFFF !important;
        border-color: var(--accent) !important;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.5) !important;
        transform: translateY(-2px);
    }
    
    .stButton > button:active {
        border-color: var(--accent) !important;
        background-color: var(--accent) !important;
        color: #FFFFFF !important;
    }

    /* Answer Box */
    .answer-box {
        background: #FFFFFF;
        border: 1px solid var(--glass-border);
        border-left: 5px solid var(--accent); /* Thick left border */
        border-radius: 8px;
        padding: 2rem;
        margin-top: 1rem;
        box-shadow: 0 4px 24px rgba(0, 212, 255, 0.15); /* Blue glow */
        color: var(--text-main);
    }

    /* Back Buttons (Secondary) */
    div[data-testid="stHorizontalBlock"] button {
        border-color: #E0E0E0 !important;
        box-shadow: none !important;
    }
    div[data-testid="stHorizontalBlock"] button:hover {
        border-color: var(--accent) !important;
        color: var(--accent) !important;
        background-color: #FFFFFF !important;
    }

    /* Container Spacing */
    .block-container {
        max_width: 800px;
        padding-top: 2rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# --- Data Loading ---
@st.cache_data
def load_faq_data():
    if not DATA_PATH.exists():
        st.error(f"Data file not found at {DATA_PATH}")
        return {}

    try:
        df = pd.read_csv(DATA_PATH)
        # Normalize columns: remove whitespace
        df.columns = [c.strip() for c in df.columns]
        
        required = {"Category", "Subcategory", "Question", "Answer"}
        if not required.issubset(set(df.columns)):
            st.error(f"CSV must have columns: {required}")
            return {}

        # Parse into nested structure:
        # tree = { 
        #    "Category A": {
        #        "Subcategory 1": [ { "q": "Question?", "a": "Answer" }, ... ],
        #        ...
        #    }, ...
        # }
        tree = {}
        
        for _, row in df.iterrows():
            cat = str(row["Category"]).strip()
            sub = str(row["Subcategory"]).strip()
            qst = str(row["Question"]).strip()
            ans = str(row["Answer"]).strip()
            
            if not cat or not sub or not qst:
                continue

            if cat not in tree:
                tree[cat] = {}
            if sub not in tree[cat]:
                tree[cat][sub] = []
            
            tree[cat][sub].append({"q": qst, "a": ans})
            
        return tree

    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        return {}

# --- State Management ---
# Steps: menu -> subcategory -> questions -> answer
if "step" not in st.session_state:
    st.session_state.step = "menu"
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "selected_subcategory" not in st.session_state:
    st.session_state.selected_subcategory = None
if "selected_item" not in st.session_state:
    st.session_state.selected_item = None

def go_home():
    st.session_state.step = "menu"
    st.session_state.selected_category = None
    st.session_state.selected_subcategory = None
    st.session_state.selected_item = None

def go_category(cat_name):
    st.session_state.selected_category = cat_name
    st.session_state.step = "subcategory"

def go_subcategory(sub_name):
    st.session_state.selected_subcategory = sub_name
    st.session_state.step = "questions"

def go_answer(item):
    st.session_state.selected_item = item
    st.session_state.step = "answer"

def go_back():
    if st.session_state.step == "answer":
        st.session_state.step = "questions"
        st.session_state.selected_item = None
    elif st.session_state.step == "questions":
        st.session_state.step = "subcategory"
        st.session_state.selected_subcategory = None
    elif st.session_state.step == "subcategory":
        go_home()

# --- Main App ---
def main():
    inject_theme()
    
    # Header
    col1, col2 = st.columns([1, 5])
    with col1:
        if Path("assets/pumpui.png").exists():
            st.image("assets/pumpui.png", width=80)
        else:
            st.write("🤖") 
    with col2:
        st.title("FIT Assistant Support")

    data_tree = load_faq_data()
    if not data_tree:
        st.warning("No FAQ data available.")
        return

    step = st.session_state.step

    # -------------------------------------------------------------------------
    # 1. Main Menu (Categories)
    # -------------------------------------------------------------------------
    if step == "menu":
        st.markdown("### How can I help you today?")
        st.markdown("Select a topic below:")
        
        cats = sorted(data_tree.keys())
        # Optional: put 'General' last if present
        # if "General" in cats: ...

        cols = st.columns(2)
        for i, cat in enumerate(cats):
            with cols[i % 2]:
                if st.button(f"📂 {cat}", key=f"cat_{i}"):
                    go_category(cat)
                    st.rerun()

    # -------------------------------------------------------------------------
    # 2. Subcategory Menu
    # -------------------------------------------------------------------------
    elif step == "subcategory":
        cat = st.session_state.selected_category
        
        # Navigation
        if st.button("⬅️ Back to Menu", key="back_cat"):
            go_back()
            st.rerun()
            
        st.markdown(f"### {cat}")
        st.write("Please select a sub-topic:")
        st.write("---")

        subcats = data_tree.get(cat, {})
        sorted_subs = sorted(subcats.keys())
        
        for i, sub in enumerate(sorted_subs):
            if st.button(f"🔹 {sub}", key=f"sub_{i}"):
                go_subcategory(sub)
                st.rerun()

    # -------------------------------------------------------------------------
    # 3. Question Menu
    # -------------------------------------------------------------------------
    elif step == "questions":
        cat = st.session_state.selected_category
        sub = st.session_state.selected_subcategory
        
        # Navigation
        if st.button(f"⬅️ Back to {cat}", key="back_sub"):
            go_back()
            st.rerun()
            
        st.markdown(f"### {cat} > {sub}")
        st.write("Select a question:")
        st.write("---")

        questions = data_tree.get(cat, {}).get(sub, [])
        for i, item in enumerate(questions):
            if st.button(f"❓ {item['q']}", key=f"q_{i}"):
                go_answer(item)
                st.rerun()

    # -------------------------------------------------------------------------
    # 4. Answer Display
    # -------------------------------------------------------------------------
    elif step == "answer":
        item = st.session_state.selected_item
        cat = st.session_state.selected_category
        sub = st.session_state.selected_subcategory
        
        st.caption(f"{cat} > {sub}")
        st.markdown(f"### {item['q']}")
        
        formatted_ans = item['a'].replace("\n", "<br>")
        
        st.markdown(
            f"""
            <div class="answer-box">
                {formatted_ans}
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        st.write("")
        st.write("")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("⬅️ Back to Questions", key="back_ans"):
                go_back()
                st.rerun()
        with c2:
            if st.button("🏠 Home", key="home_ans"):
                go_home()
                st.rerun()

if __name__ == "__main__":
    main()