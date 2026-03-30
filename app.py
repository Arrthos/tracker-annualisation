import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import holidays

# --- 1. CONFIGURATION DES UTILISATEURS ---
# Tu peux ajouter tes collègues ici
USERS = {
    "ton_nom": {"password": "123", "base_sup": 20.5, "full_name": "Ton Prénom"},
    "collegue1": {"password": "abc", "base_sup": 10.0, "full_name": "Jean Dupont"},
    "collegue2": {"password": "456", "base_sup": -5.5, "full_name": "Marie Curie"}
}

# --- 2. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Work Tracker Team", layout="centered")

# --- 3. GESTION DE LA SESSION (AUTH) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_key = None

def login():
    st.title("🔐 Connexion Equipe")
    user_input = st.text_input("Utilisateur")
    pass_input = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if user_input in USERS and USERS[user_input]["password"] == pass_input:
            st.session_state.authenticated = True
            st.session_state.user_key = user_input
            st.rerun()
        else:
            st.error("Identifiants incorrects")

if not st.session_state.authenticated:
    login()
    st.stop()

# --- 4. STYLE & THÈME ---
current_user = st.session_state.user_key
user_data = USERS[current_user]

if 'theme' not in st.session_state: st.session_state.theme = 'dark'
def toggle_theme(): st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

common_css = "<style>.element-container h1 a { display: none !important; } .stButton>button { border-radius: 8px; }</style>"
dark_css = ".stApp { background: #0d1117; } .main-card { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 12px; text-align: center; } h1, h2, h3, p, span { color: white !important; }"
light_css = ".stApp { background: #FAF5F0; } .main-card { background: white; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); } h1, h2, h3, p, span { color: #1A202C !important; }"
active_css = dark_css if st.session_state.theme == 'dark' else light_css
st.markdown(common_css + f"<style>{active_css}</style>", unsafe_allow_html=True)

# --- 5. CONNEXION GSHEETS & CALCULS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_totals(df_ajust, df_conges, user_key):
    now = datetime.now()
    start_year = now.year if now.month >= 9 else now.year - 1
    start_date = datetime(start_year, 9, 1)
    aujourdhui = now.replace(hour=23, minute=59)
    
    fr_holidays = holidays.France(years=[start_year, start_year + 1])
    
    # Filtrage des données par utilisateur
    u_conges = df_conges[df_conges['user'] == user_key]
    u_ajust = df_ajust[df_ajust['user'] == user_key]
    
    dict_conges = {pd.to_datetime(row['date'], dayfirst=True).date(): float(row['type']) for _, row in u_conges.iterrows()}

    theo_total = 0
    curr = start_date
    while curr <= aujourdhui:
        d = curr.date()
        if curr.weekday() < 5:
            h_jour = 7.5 if curr.weekday() <= 1 else 7.0
            if not (d in fr_holidays and d != date(start_year+1, 6, 1)):
                conge = dict_conges.get(d, 0)
                theo_total += h_jour * (1 - conge)
        curr += timedelta(days=1)
    
    delta_saisi = u_ajust['val'].sum() if not u_ajust.empty else 0
    return theo_total, delta_saisi

# Lecture des données
df_ajust_raw = conn.read(worksheet="Feuille 1", ttl=0)
df_conges_raw = conn.read(worksheet="Conges", ttl=0)

theo, delta_saisi = get_totals(df_ajust_raw, df_conges_raw, current_user)
total_delta = user_data["base_sup"] + delta_saisi
fait = theo + total_delta

# --- 6. INTERFACE ---
with st.sidebar:
    st.write(f"👤 **{user_data['full_name']}**")
    st.button("🌓 Mode", on_click=toggle_theme)
    if st.button("🚪 Déconnexion"):
        st.session_state.authenticated = False
        st.rerun()

st.title("Work Tracker Pro")
color = "#238636" if total_delta >= 0 else "#da3633"
h_delta, m_delta = int(abs(total_delta)), int((abs(total_delta) - int(abs(total_delta))) * 60)

st.markdown(f"""
    <div class="main-card">
        <p style="font-size: 0.9em; opacity: 0.8;">Ma Balance</p>
        <h1 style="color: {color} !important; font-size: 3.5em; margin: 0;">{'+' if total_delta >= 0 else '-'}{h_delta}h{m_delta:02d}</h1>
    </div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["⚡ Réguler", "🌴 Congés"])

with tab1:
    col1, col2 = st.columns(2)
    adj_type = col1.selectbox("Type", ["Heures Sup (+)", "Heures en moins (-)"])
    d_adj = col2.date_input("Date", value=datetime.now())
    h_adj = st.number_input("Heures", 0, 10, 0)
    m_adj = st.number_input("Minutes", 0, 59, 0)
    
    if st.button("Enregistrer"):
        val = (h_adj + m_adj/60) * (-1 if "moins" in adj_type else 1)
        new_row = pd.DataFrame([{"user": current_user, "date": d_adj.strftime("%d/%m/%Y"), "val": val}])
        updated = pd.concat([df_ajust_raw, new_row], ignore_index=True)
        conn.update(worksheet="Feuille 1", data=updated)
        st.rerun()

with tab2:
    c_date = st.date_input("Date congé", value=datetime.now())
    c_type = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
    if st.button("Confirmer congé"):
        new_c = pd.DataFrame([{"user": current_user, "date": c_date.strftime("%d/%m/%Y"), "type": 1.0 if c_type == "Journée" else 0.5}])
        updated_c = pd.concat([df_conges_raw, new_c], ignore_index=True)
        conn.update(worksheet="Conges", data=updated_c)
        st.rerun()
    
