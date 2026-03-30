import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import holidays

# --- 1. CONFIGURATION DES UTILISATEURS ---
USERS = {
    "Julien": {"password": "123", "base_sup": 20.5, "full_name": "Julien", "role": "admin"}
}

st.set_page_config(
    page_title="Work Tracker Pro",
    page_icon="https://raw.githubusercontent.com/Arrthos/tracker-annualisation/main/image_11.png",
    layout="centered"
)

# --- 2. GESTION DU THÈME & SESSION ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

# --- 3. LOGIN ---
if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center;'>🔐 Connexion Pro</h1>", unsafe_allow_html=True)
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

# --- 4. STYLE CSS COMPLET ---
common_css = """
    <style>
    .element-container h1 a, .element-container h2 a { display: none !important; }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    .stProgress > div > div > div > div { background-color: #238636; }
    .conge-card { background: rgba(255,255,255,0.1); padding: 10px; border-radius: 10px; margin: 5px 0; border-left: 5px solid #007bff; }
    .cal-day { text-align: center; padding: 5px; border-radius: 5px; }
    </style>
"""
dark_css = """
    .stApp { background: radial-gradient(circle at center, #1a2a40 0%, #0d1117 100%); background-attachment: fixed; }
    .main-card { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(20px); padding: 30px; border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; margin-bottom: 25px; }
    .stat-label { color: rgba(255, 255, 255, 0.6) !important; }
    .stat-value { color: white !important; font-size: 1.8em; font-weight: bold; }
    h1, h2, h3, p, span, .stMarkdown { color: white !important; }
"""
light_css = """
    .stApp { background-color: #FAF5F0; }
    .main-card { background: white; padding: 30px; border-radius: 15px; border: 1px solid #E2E8F0; text-align: center; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); }
    .stat-label { color: #4A5568 !important; }
    .stat-value { color: #1A202C !important; font-size: 1.8em; font-weight: bold; }
    h1, h2, h3, p, span, .stMarkdown { color: #1A202C !important; }
"""
st.markdown(common_css, unsafe_allow_html=True)
st.markdown(f"<style>{dark_css if st.session_state.theme == 'dark' else light_css}</style>", unsafe_allow_html=True)

# --- 5. LOGIQUE CALCULS ---
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
    
    # Dictionnaire des dates de congés pour le calcul théorique
    d_conges = {}
    if not u_c.empty:
        for _, row in u_c.iterrows():
            try:
                d_obj = pd.to_datetime(row['date'], dayfirst=True).date()
                d_conges[d_obj] = float(row['type'])
            except: continue

    theo = 0
    curr = start_date
    while curr <= ajd:
        d = curr.date()
        if curr.weekday() < 5: # Lundi-Vendredi
            h_j = 7.5 if curr.weekday() <= 1 else 7.0 # Lundi-Mardi 7.5h, Mer-Ven 7h
            if not (d in fr_h and d != date(sy+1, 6, 1)): # Pas férié (sauf lundi pentecôte travaillé)
                theo += h_j * (1 - d_conges.get(d, 0))
        curr += timedelta(days=1)
    
    delta_s = u_a['val'].sum() if not u_a.empty else 0
    return USERS[uid]["base_sup"] + delta_s, theo, u_c

# Chargement données
df_ajust_raw = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
df_conges_raw = conn.read(worksheet="Conges", ttl=0).dropna(how='all')

my_delta, my_theo, my_conges_df = get_user_stats(curr_user, df_ajust_raw, df_conges_raw)
fait = my_theo + my_delta

# --- 6. FONCTION CALENDRIER VISUEL ---
def draw_calendar(df_c):
    today = datetime.now()
    cal = calendar.monthcalendar(today.year, today.month)
    month_name = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"][today.month-1]
    
    st.write(f"📅 **{month_name} {today.year}**")
    
    posees = []
    if not df_c.empty:
        df_c['dt'] = pd.to_datetime(df_c['date'], dayfirst=True)
        posees = df_c[(df_c['dt'].dt.month == today.month) & (df_c['dt'].dt.year == today.year)]['dt'].dt.day.tolist()

    # Construction du calendrier en HTML/CSS Grid
    days_header = "".join([f'<div style="text-align:center; font-weight:bold; font-size:0.8em; opacity:0.6;">{d}</div>' for d in ["L", "M", "M", "J", "V", "S", "D"]])
    
    cal_html = f"""
    <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px; margin-top: 10px;">
        {days_header}
    """
    
    for week in cal:
        for day in week:
            if day == 0:
                cal_html += '<div></div>'
            else:
                # Style par défaut
                bg = "transparent"
                border = "none"
                text_color = "inherit"
                content = str(day)
                
                # Style si jour de congé
                if day in posees:
                    bg = "#007bff"
                    content = f"{day}🔵"
                # Style si aujourd'hui
                elif day == today.day:
                    border = "1px solid #238636"
                    content = f"{day}📍"
                
                cal_html += f"""
                <div style="text-align:center; padding:8px 0; background:{bg}; border:{border}; border-radius:5px; font-size:0.9em;">
                    {content}
                </div>
                """
    
    cal_html += "</div>"
    st.markdown(cal_html, unsafe_allow_html=True)
# --- 7. INTERFACE PRINCIPALE ---
with st.sidebar:
    st.markdown(f"### 👤 {u_info['full_name']}")
    st.button("🌓 Mode Sombre/Clair", on_click=toggle_theme, use_container_width=True)
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# Header Progression
st.markdown(f"### Progression Annuelle : {int(fait)}h / {int(OBJECTIF_ANNUEL)}h")
st.progress(min(fait / OBJECTIF_ANNUEL, 1.0))

# Carte de Balance
color = "#238636" if my_delta >= 0 else "#da3633"
h_d, m_d = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
st.markdown(f"""
    <div class="main-card">
        <p class="stat-label">Balance Actuelle</p>
        <h1 style="color: {color} !important; font-size: 4.5em; margin: 0;">{'+' if my_delta >= 0 else '-'}{h_d}h{m_d:02d}</h1>
        <p style="color: {color}; font-weight: bold;">≃ {my_delta/7.2:.1f} jours de repos cumulés</p>
    </div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
col1.markdown(f'<div class="main-card" style="padding:15px;"><p class="stat-label">FAIT</p><p class="stat-value">{fait:.2f}h</p></div>', unsafe_allow_html=True)
col2.markdown(f'<div class="main-card" style="padding:15px;"><p class="stat-label">DÛ</p><p class="stat-value">{my_theo:.2f}h</p></div>', unsafe_allow_html=True)

# --- 8. ONGLETS ---
t1, t2 = st.tabs(["⚡ Réguler Heures", "🌴 Congés & Calendrier"])

with t1:
    with st.form("h_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_t = c1.selectbox("Action", ["Heures Sup (+)", "Heures en moins (-)"])
        d_a = c2.date_input("Date de l'écart", value=datetime.now())
        h_s, m_s = st.number_input("Heures", 0, 12, 0), st.number_input("Minutes", 0, 59, 0)
        if st.form_submit_button("Enregistrer", use_container_width=True):
            val = (h_s + m_s/60) * (-1 if "moins" in a_t else 1)
            new_row = pd.DataFrame([{"user": curr_user, "date": d_a.strftime("%d/%m/%Y"), "val": val}])
            conn.update(worksheet="Feuille 1", data=pd.concat([df_ajust_raw, new_row], ignore_index=True)[['user', 'date', 'val']])
            st.rerun()

    st.write("**Historique (5 derniers) :**")
    u_h = df_ajust_raw[df_ajust_raw['user'] == curr_user]
    for i, row in u_h.iloc[::-1].head(5).iterrows():
        cx, cd = st.columns([4, 1])
        cx.write(f"{row['date']} : {row['val']:+.2f}h")
        if cd.button("🗑️", key=f"h_{i}"):
            conn.update(worksheet="Feuille 1", data=df_ajust_raw.drop(i)[['user', 'date', 'val']])
            st.rerun()

with t2:
    # Stats Congés
    total_j = my_conges_df['type'].sum() if not my_conges_df.empty else 0
    st.markdown(f"**Total pris : {total_j} jours** (soit {total_j*7.2:.1f}h déduites de ton temps dû)")
    
    # Affichage du calendrier
    draw_calendar(my_conges_df)
    
    st.divider()
    
    with st.form("c_form", clear_on_submit=True):
        c_d = st.date_input("Date du repos", value=datetime.now())
        c_t = st.radio("Type", ["Journée", "Demi"], horizontal=True)
        if st.form_submit_button("Poser le congé", use_container_width=True):
            val_c = 1.0 if c_t == "Journée" else 0.5
            new_c = pd.DataFrame([{"user": curr_user, "date": c_d.strftime("%d/%m/%Y"), "type": val_c}])
            conn.update(worksheet="Conges", data=pd.concat([df_conges_raw, new_c], ignore_index=True)[['user', 'date', 'type']])
            st.rerun()

    st.write("**Liste des congés :**")
    for i, row in my_conges_df.iloc[::-1].head(5).iterrows():
        cx, cd = st.columns([4, 1])
        lab = "Journée" if row['type'] == 1.0 else "Demi"
        cx.markdown(f'<div class="conge-card">📅 {row["date"]} ({lab})</div>', unsafe_allow_html=True)
        if cd.button("🗑️", key=f"c_{i}"):
            conn.update(worksheet="Conges", data=df_conges_raw.drop(i)[['user', 'date', 'type']])
            st.rerun()
