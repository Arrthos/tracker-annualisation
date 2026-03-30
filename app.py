import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import holidays

# --- 1. CONFIGURATION DES UTILISATEURS ---
USERS = {
    "Julien": {"password": "123", "base_sup": 20.5, "full_name": "Julien", "role": "admin"},
    #"collegue1": {"password": "abc", "base_sup": 10.0, "full_name": "Jean Dupont", "role": "user"},
   # "collegue2": {"password": "456", "base_sup": 0.0, "full_name": "Marie Curie", "role": "user"}
}

# --- 2. CONFIGURATION PAGE ---
st.set_page_config(page_title="Work Tracker Team", layout="centered")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def login():
    st.title("🔐 Connexion Equipe")
    u_input = st.text_input("Identifiant")
    p_input = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if u_input in USERS and USERS[u_input]["password"] == p_input:
            st.session_state.authenticated = True
            st.session_state.user_key = u_input
            st.rerun()
        else:
            st.error("Identifiants incorrects")

if not st.session_state.authenticated:
    login()
    st.stop()

# --- 3. STYLE & THÈME ---
curr_user = st.session_state.user_key
u_info = USERS[curr_user]

if 'theme' not in st.session_state: st.session_state.theme = 'dark'
def toggle_theme(): st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

common_css = """
<style>
    .element-container h1 a, .element-container h2 a, .element-container h3 a { display: none !important; }
    .stButton>button { border-radius: 8px; font-weight: bold; }
</style>
"""
dark_css = ".stApp { background: #0d1117; } .main-card { background: rgba(255,255,255,0.05); padding: 25px; border-radius: 15px; text-align: center; border: 1px solid rgba(255,255,255,0.1); } h1, h2, h3, p, span { color: white !important; }"
light_css = ".stApp { background: #FAF5F0; } .main-card { background: white; padding: 25px; border-radius: 15px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #E2E8F0; } h1, h2, h3, p, span { color: #1A202C !important; }"
st.markdown(common_css + f"<style>{dark_css if st.session_state.theme == 'dark' else light_css}</style>", unsafe_allow_html=True)

# --- 4. CALCULS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def calculate_for_user(uid, df_a, df_c):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start_date = datetime(sy, 9, 1)
    ajd = now.replace(hour=23, minute=59)
    fr_h = holidays.France(years=[sy, sy + 1])
    
    u_c = df_c[df_c['user'] == uid]
    u_a = df_a[df_a['user'] == uid]
    d_conges = {pd.to_datetime(row['date'], dayfirst=True).date(): float(row['type']) for _, row in u_c.iterrows()}

    theo = 0
    curr = start_date
    while curr <= ajd:
        d = curr.date()
        if curr.weekday() < 5:
            h_j = 7.5 if curr.weekday() <= 1 else 7.0
            if not (d in fr_h and d != date(sy+1, 6, 1)):
                theo += h_j * (1 - d_conges.get(d, 0))
        curr += timedelta(days=1)
    
    delta_s = u_a['val'].sum() if not u_a.empty else 0
    total_d = USERS[uid]["base_sup"] + delta_s
    return total_d, theo

df_ajust_raw = conn.read(worksheet="Feuille 1", ttl=0)
df_conges_raw = conn.read(worksheet="Conges", ttl=0)

my_delta, my_theo = calculate_for_user(curr_user, df_ajust_raw, df_conges_raw)

# --- 5. INTERFACE ---
with st.sidebar:
    st.markdown(f"### 👤 {u_info['full_name']}")
    st.button("🌓 Mode", on_click=toggle_theme, use_container_width=True)
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

if u_info['role'] == "admin":
    with st.expander("📊 Tableau de bord Equipe (Admin)"):
        data_team = []
        for uid, info in USERS.items():
            d, t = calculate_for_user(uid, df_ajust_raw, df_conges_raw)
            data_team.append({"Nom": info['full_name'], "Balance": f"{d:+.2f}h"})
        st.table(pd.DataFrame(data_team))

st.title("Mon Annualisation")
color = "#238636" if my_delta >= 0 else "#da3633"
h_d, m_d = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)

st.markdown(f"""
    <div class="main-card">
        <p style="font-size: 0.9em; opacity: 0.7;">Balance actuelle</p>
        <h1 style="color: {color} !important; font-size: 4em; margin: 0;">{'+' if my_delta >= 0 else '-'}{h_d}h{m_d:02d}</h1>
    </div>
""", unsafe_allow_html=True)

st.divider()

t1, t2 = st.tabs(["⚡ Réguler", "🌴 Congés"])

with t1:
    st.subheader("Saisir un écart")
    c1, c2 = st.columns(2)
    a_t = c1.selectbox("Type", ["Heures Sup (+)", "Heures en moins (-)"])
    d_a = c2.date_input("Date", value=datetime.now(), key="date_h")
    h_a = st.number_input("Heures", 0, 12, 0)
    m_a = st.number_input("Minutes", 0, 59, 0)
    
    if st.button("Enregistrer l'écart", use_container_width=True):
        val = (h_a + m_a/60) * (-1 if "moins" in a_t else 1)
        
