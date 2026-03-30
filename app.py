import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import holidays

# --- 1. CONFIGURATION & PERMANENCE ---
USERS = {
    "Julien": {"password": "123", "base_sup": 20.5, "full_name": "Julien", "role": "admin"}
}

st.set_page_config(page_title="Work Tracker Pro", page_icon="📊", layout="centered")

# Initialisation des variables de session
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_key' not in st.session_state:
    st.session_state.user_key = None

# --- 2. FONCTIONS OPTIMISÉES (CACHE) ---

@st.cache_data(ttl=600)  # Garde en mémoire les jours fériés pendant 10 min
def get_holidays(year):
    return holidays.France(years=[year, year + 1])

def get_stats_optimized(uid, df_a, df_c):
    """Calcul optimisé pour réduire la charge CPU"""
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    fr_h = get_holidays(sy)
    
    # Filtrage rapide
    u_c = df_c[df_c['user'] == uid] if 'user' in df_c.columns else pd.DataFrame()
    u_a = df_a[df_a['user'] == uid] if 'user' in df_a.columns else pd.DataFrame()
    
    d_conges = {pd.to_datetime(r['date'], dayfirst=True).date(): float(r['type']) for _, r in u_c.iterrows()}
    
    theo = 0
    curr = start
    end_calc = now.replace(hour=23, minute=59)
    
    # Boucle de calcul optimisée
    while curr <= end_calc:
        d = curr.date()
        if curr.weekday() < 5:
            h_j = 7.5 if curr.weekday() <= 1 else 7.0
            if not (d in fr_h and d != date(sy+1, 6, 1)):
                theo += h_j * (1 - d_conges.get(d, 0))
        curr += timedelta(days=1)
    
    val_ajust = u_a['val'].sum() if not u_a.empty else 0
    return USERS[uid]["base_sup"] + val_ajust, theo

# --- 3. LOGIQUE DE CONNEXION ---
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center;'>🔐 Accès Work Tracker</h2>", unsafe_allow_html=True)
    with st.form("login_form"):
        u_i = st.text_input("Identifiant")
        p_i = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Se connecter", use_container_width=True):
            if u_i in USERS and USERS[u_i]["password"] == p_i:
                st.session_state.authenticated = True
                st.session_state.user_key = u_i
                st.rerun()
            else:
                st.error("Identifiants erronés")
    st.stop()

# --- 4. RÉCUPÉRATION DES DONNÉES (FLUIDE) ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Lecture avec un TTL court pour l'interactivité, mais long assez pour la fluidité
df_a = conn.read(worksheet="Feuille 1", ttl="1m").dropna(how='all')
df_c = conn.read(worksheet="Conges", ttl="1m").dropna(how='all')

curr_user = st.session_state.user_key
my_delta, my_theo = get_stats_optimized(curr_user, df_a, df_c)

# --- 5. INTERFACE ET CALENDRIER (HTML GRID) ---
st.title(f"Salut, {USERS[curr_user]['full_name']} 👋")

# Affichage Balance (Simplifié pour mobile)
h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:15px; text-align:center; border-left: 5px solid {color};">
        <h1 style="color:{color}; margin:0; font-size:3em;">{'+' if my_delta >= 0 else '-'}{h}h{m:02d}</h1>
        <p style="opacity:0.7; margin:0;">Balance Annualisation</p>
    </div>
""", unsafe_allow_html=True)

st.write("") # Espacement

t1, t2 = st.tabs(["⚡ Heures", "🌴 Repos"])

with t1:
    with st.expander("➕ Enregistrer une régulation"):
        with st.form("h_form", clear_on_submit=True):
            typ = st.radio("Action", ["Plus (+)", "Moins (-)"], horizontal=True)
            dat = st.date_input("Date", value=date.today())
            c_h, c_m = st.columns(2)
            hrs = c_h.number_input("H", 0, 12, 0)
            mnt = c_m.number_input("min", 0, 59, 0)
            if st.form_submit_button("Valider"):
                v = (hrs + mnt/60) * (-1 if "Moins" in typ else 1)
                new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": v}])
                conn.update(worksheet="Feuille 1", data=pd.concat([df_a, new], ignore_index=True)[['user', 'date', 'val']])
                st.cache_data.clear() # Force le rafraîchissement
                st.rerun()

with t2:
    # Calendrier intégré avec grille CSS
    today = datetime.now()
    cal = calendar.monthcalendar(today.year, today.month)
    u_c_list = df_c[df_c['user'] == curr_user]
    posees = pd.to_datetime(u_c_list['date'], dayfirst=True).dt.day.tolist() if not u_c_list.empty else []

    cal_html = "<div style='display:grid; grid-template-columns:repeat(7,1fr); gap:3px;'>"
    for d in ["L","M","M","J","V","S","D"]: cal_html += f"<b style='text-align:center; font-size:0.7em;'>{d}</b>"
    for week in cal:
        for day in week:
            if day == 0: cal_html += "<div></div>"
            else:
                bg = "#007bff" if day in posees else "rgba(255,255,255,0.05)"
                border = "1px solid #238636" if day == today.day else "none"
                cal_html += f"<div style='text-align:center; padding:8px 0; background:{bg}; border:{border}; border-radius:4px; font-size:0.8em;'>{day}</div>"
    cal_html += "</div>"
    st.markdown(cal_html, unsafe_allow_html=True)

# Déconnexion en bas de page
if st.sidebar.button("🚪 Déconnexion"):
    st.session_state.authenticated = False
    st.rerun()
