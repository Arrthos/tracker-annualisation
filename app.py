import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import holidays

# --- 1. CONFIGURATION DES UTILISATEURS ---
USERS = {
    "Julien": {"password": "123", "base_sup": 20.5, "full_name": "Julien", "role": "admin"},
    #"collegue1": {"password": "abc", "base_sup": 10.0, "full_name": "Jean Dupont", "role": "user"}
}

st.set_page_config(
    page_title="Work Tracker Pro",
    page_icon="https://raw.githubusercontent.com/Arrthos/tracker-annualisation/main/image_11.png",
    layout="centered"
)

# --- 2. GESTION DU THÈME ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

# --- 3. LOGIN ---
if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center;'>🔐 Connexion</h1>", unsafe_allow_html=True)
    with st.container():
        u_i = st.text_input("Identifiant")
        p_i = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter", use_container_width=True):
            if u_i in USERS and USERS[u_i]["password"] == p_i:
                st.session_state.authenticated = True
                st.session_state.user_key = u_i
                st.rerun()
            else:
                st.error("Identifiants incorrects")
    st.stop()

curr_user = st.session_state.user_key
u_info = USERS[curr_user]

# --- 4. STYLE CSS (RETOUR DU VISUEL PRÉCÉDENT) ---
common_css = """
    <style>
    .element-container h1 a, .element-container h2 a { display: none !important; }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    .stProgress > div > div > div > div { background-color: #238636; }
    </style>
"""
dark_css = """
    .stApp { background: radial-gradient(circle at center, #1a2a40 0%, #0d1117 100%); background-attachment: fixed; }
    .main-card { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(20px); padding: 30px; border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; margin-bottom: 25px; }
    .stat-label { color: rgba(255, 255, 255, 0.6) !important; font-size: 0.9em; }
    .stat-value { color: white !important; font-size: 1.8em; font-weight: bold; }
    h1, h2, h3, p, span, .stMarkdown { color: white !important; }
"""
light_css = """
    .stApp { background-color: #FAF5F0; }
    .main-card { background: white; padding: 30px; border-radius: 15px; border: 1px solid #E2E8F0; text-align: center; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); }
    .stat-label { color: #4A5568 !important; font-size: 0.9em; }
    .stat-value { color: #1A202C !important; font-size: 1.8em; font-weight: bold; }
    h1, h2, h3, p, span, .stMarkdown { color: #1A202C !important; }
"""

st.markdown(common_css, unsafe_allow_html=True)
st.markdown(f"<style>{dark_css if st.session_state.theme == 'dark' else light_css}</style>", unsafe_allow_html=True)

# --- 5. LOGIQUE GSHEETS & CALCULS ---
conn = st.connection("gsheets", type=GSheetsConnection)
OBJECTIF_ANNUEL = 1652.0

def get_user_stats(uid, df_a, df_c):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start_date = datetime(sy, 9, 1)
    ajd = now.replace(hour=23, minute=59)
    fr_h = holidays.France(years=[sy, sy + 1])
    
    u_c = df_c[df_c['user'] == uid] if 'user' in df_c.columns else pd.DataFrame()
    u_a = df_a[df_a['user'] == uid] if 'user' in df_a.columns else pd.DataFrame()
    
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
    total_delta = USERS[uid]["base_sup"] + delta_s
    return total_delta, theo

df_ajust_raw = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
df_conges_raw = conn.read(worksheet="Conges", ttl=0).dropna(how='all')

my_delta, my_theo = get_user_stats(curr_user, df_ajust_raw, df_conges_raw)
fait = my_theo + my_delta

# --- 6. INTERFACE UTILISATEUR ---
with st.sidebar:
    st.markdown(f"### 👤 {u_info['full_name']}")
    st.button("🌓 Changer de Mode", on_click=toggle_theme, use_container_width=True)
    if u_info['role'] == "admin":
        with st.expander("📊 Vue Équipe"):
            for uid, info in USERS.items():
                d, _ = get_user_stats(uid, df_ajust_raw, df_conges_raw)
                st.write(f"{info['full_name']} : **{d:+.2f}h**")
    st.divider()
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# Progression
st.markdown(f"### Progression : {int(fait)}h / {int(OBJECTIF_ANNUEL)}h")
st.progress(min(fait / OBJECTIF_ANNUEL, 1.0))

# Carte Principale
color = "#238636" if my_delta >= 0 else "#da3633"
h_d, m_d = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
st.markdown(f"""
    <div class="main-card">
        <p class="stat-label">Balance Annualisation</p>
        <h1 style="color: {color} !important; font-size: 4em; margin: 10px 0;">{'+' if my_delta >= 0 else '-'}{h_d}h{m_d:02d}</h1>
        <p style="color: {color}; opacity: 0.8;">≃ {my_delta/7.2:.1f} jours de repos</p>
    </div>
""", unsafe_allow_html=True)

col_a, col_b = st.columns(2)
col_a.markdown(f'<p class="stat-label">HEURES FAITES</p><p class="stat-value">{fait:.2f}h</p>', unsafe_allow_html=True)
col_b.markdown(f'<p class="stat-label">HEURES DUES</p><p class="stat-value">{my_theo:.2f}h</p>', unsafe_allow_html=True)

st.divider()

# Onglets Saisie
t1, t2 = st.tabs(["⚡ Réguler", "🌴 Congés"])

with t1:
    with st.form("h_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_t = c1.selectbox("Type", ["Heures Sup (+)", "Heures en moins (-)"])
        d_a = c2.date_input("Date", value=datetime.now())
        h_s = st.number_input("Heures", 0, 12, 0)
        m_s = st.number_input("Minutes", 0, 59, 0)
        if st.form_submit_button("Valider la régulation", use_container_width=True):
            val = (h_s + m_s/60) * (-1 if "moins" in a_t else 1)
            new_row = pd.DataFrame([{"user": curr_user, "date": d_a.strftime("%d/%m/%Y"), "val": val}])
            updated = pd.concat([df_ajust_raw, new_row], ignore_index=True)
            conn.update(worksheet="Feuille 1", data=updated[['user', 'date', 'val']])
            st.rerun()

    u_h = df_ajust_raw[df_ajust_raw['user'] == curr_user]
    if not u_h.empty:
        st.write("**Dernières régulations :**")
        for i, row in u_h.iloc[::-1].head(5).iterrows():
            c_txt, c_del = st.columns([4, 1])
            c_txt.write(f"{row['date']} : {row['val']:+.2f}h")
            if c_del.button("🗑️", key=f"h_{i}"):
                conn.update(worksheet="Feuille 1", data=df_ajust_raw.drop(i)[['user', 'date', 'val']])
                st.rerun()

with t2:
    with st.form("c_form", clear_on_submit=True):
        c_d = st.date_input("Date du congé", value=datetime.now())
        c_t = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
        if st.form_submit_button("Enregistrer le congé", use_container_width=True):
            new_c = pd.DataFrame([{"user": curr_user, "date": c_d.strftime("%d/%m/%Y"), "type": 1.0 if c_t == "Journée" else 0.5}])
            updated_c = pd.concat([df_conges_raw, new_c], ignore_index=True)
            conn.update(worksheet="Conges", data=updated_c[['user', 'date', 'type']])
            st.rerun()

    u_c = df_conges_raw[df_conges_raw['user'] == curr_user]
    if not u_c.empty:
        st.write("**Mes congés :**")
        for i, row in u_c.iloc[::-1].head(5).iterrows():
            c_txt, c_del = st.columns([4, 1])
            lab = "Jour" if row['type'] == 1.0 else "Demi"
            c_txt.write(f"📅 {row['date']} ({lab})")
            if c_del.button("🗑️", key=f"c_{i}"):
                conn.update(worksheet="Conges", data=df_conges_raw.drop(i)[['user', 'date', 'type']])
                st.rerun()
