import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import holidays

# --- 1. CONFIGURATION & SESSION ---
USERS = {
    "Julien": {"password": "123", "base_sup": 20.5, "full_name": "Julien", "role": "admin"}
}
OBJECTIF_ANNUEL = 1652.0

st.set_page_config(page_title="Work Tracker Pro", page_icon="📊", layout="centered")

# Initialisation cruciale pour rester connecté
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_key' not in st.session_state:
    st.session_state.user_key = None

# --- 2. FONCTIONS (AVEC FILTRE MOIS) ---
@st.cache_data(ttl=600)
def get_holidays(year):
    return holidays.France(years=[year, year + 1])

def get_stats(uid, df_a, df_c):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    fr_h = get_holidays(sy)
    
    u_c = df_c[df_c['user'] == uid].copy() if 'user' in df_c.columns else pd.DataFrame()
    u_a = df_a[df_a['user'] == uid].copy() if 'user' in df_a.columns else pd.DataFrame()
    
    # Conversion propre des dates pour éviter les erreurs de format
    if not u_c.empty:
        u_c['dt_obj'] = pd.to_datetime(u_c['date'], dayfirst=True).dt.date
        d_conges = dict(zip(u_c['dt_obj'], u_c['type'].astype(float)))
    else:
        d_conges = {}
    
    theo = 0
    curr = start
    end_calc = now.replace(hour=23, minute=59)
    
    while curr <= end_calc:
        d = curr.date()
        if curr.weekday() < 5:
            h_j = 7.5 if curr.weekday() <= 1 else 7.0
            if not (d in fr_h and d != date(sy+1, 6, 1)):
                theo += h_j * (1 - d_conges.get(d, 0))
        curr += timedelta(days=1)
    
    val_ajust = u_a['val'].sum() if not u_a.empty else 0
    return USERS[uid]["base_sup"] + val_ajust, theo, u_c, u_a

# --- 3. FORMULAIRE DE CONNEXION ---
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center;'>🔐 Connexion</h2>", unsafe_allow_html=True)
    with st.form("login"):
        u_i = st.text_input("Identifiant")
        p_i = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Entrer", use_container_width=True):
            if u_i in USERS and USERS[u_i]["password"] == p_i:
                st.session_state.authenticated = True
                st.session_state.user_key = u_i
                st.rerun()
            else:
                st.error("Identifiants erronés")
    st.stop()

# --- 4. CHARGEMENT DONNÉES ---
conn = st.connection("gsheets", type=GSheetsConnection)
df_a = conn.read(worksheet="Feuille 1", ttl="1m").dropna(how='all')
df_c = conn.read(worksheet="Conges", ttl="1m").dropna(how='all')

curr_user = st.session_state.user_key
my_delta, my_theo, my_conges_df, my_ajust_df = get_stats(curr_user, df_a, df_c)
fait = my_theo + my_delta

# --- 5. INTERFACE ---
st.title(f"Salut {curr_user} !")

# Barre de progression
st.write(f"**Progression : {int(fait)}h / {int(OBJECTIF_ANNUEL)}h**")
st.progress(min(fait / OBJECTIF_ANNUEL, 1.0))

# Carte Balance
h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:20px; border-radius:15px; text-align:center; border:1px solid rgba(255,255,255,0.1); margin-bottom:15px;">
        <p style="opacity:0.6; margin:0; font-size:0.8em;">BALANCE ACTUELLE</p>
        <h1 style="color:{color}; font-size:3.5em; margin:5px 0;">{'+' if my_delta >= 0 else '-'}{h}h{m:02d}</h1>
        <p style="opacity:0.8; margin:0;">≃ {my_delta/7.2:.1f} jours</p>
    </div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
col1.metric("FAIT", f"{fait:.1f}h")
col2.metric("DÛ", f"{my_theo:.1f}h")

t1, t2 = st.tabs(["⚡ Réguler", "🌴 Congés"])

with t1:
    with st.expander("📝 Ajouter des heures", expanded=False):
        with st.form("h_form", clear_on_submit=True):
            typ = st.selectbox("Type", ["Heures Sup (+)", "Heures en moins (-)"])
            dat = st.date_input("Date", value=date.today())
            h_s, m_s = st.number_input("Heures", 0, 12, 0), st.number_input("Minutes", 0, 59, 0)
            if st.form_submit_button("Enregistrer"):
                val = (h_s + m_s/60) * (-1 if "moins" in typ else 1)
                new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": val}])
                conn.update(worksheet="Feuille 1", data=pd.concat([df_a, new], ignore_index=True)[['user', 'date', 'val']])
                st.cache_data.clear()
                st.rerun()

with t2:
    # --- CALENDRIER AVEC FILTRE MOIS EN COURS ---
    today = datetime.now()
    cal = calendar.monthcalendar(today.year, today.month)
    
    # On ne garde que les jours du mois actuel
    if not my_conges_df.empty:
        my_conges_df['dt_temp'] = pd.to_datetime(my_conges_df['date'], dayfirst=True)
        posees_ce_mois = my_conges_df[
            (my_conges_df['dt_temp'].dt.month == today.month) & 
            (my_conges_df['dt_temp'].dt.year == today.year)
        ]['dt_temp'].dt.day.tolist()
    else:
        posees_ce_mois = []

    st.write(f"📅 **{calendar.month_name[today.month]} {today.year}**")
    cal_html = "<div style='display:grid; grid-template-columns:repeat(7,1fr); gap:4px; margin-bottom:15px;'>"
    for d in ["L","M","M","J","V","S","D"]: cal_html += f"<b style='text-align:center; font-size:0.7em;'>{d}</b>"
    for week in cal:
        for day in week:
            if day == 0: cal_html += "<div></div>"
            else:
                is_conge = day in posees_ce_mois
                bg = "#007bff" if is_conge else "rgba(255,255,255,0.05)"
                border = "1px solid #238636" if day == today.day else "none"
                cal_html += f"<div style='text-align:center; padding:8px 0; background:{bg}; border:{border}; border-radius:5px;'>{day}</div>"
    cal_html += "</div>"
    st.markdown(cal_html, unsafe_allow_html=True)

    with st.expander("🌴 Poser un congé", expanded=False):
        with st.form("c_form", clear_on_submit=True):
            d_c = st.date_input("Date", value=date.today())
            t_c = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
            if st.form_submit_button("Valider"):
                v_c = 1.0 if t_c == "Journée" else 0.5
                new_c = pd.DataFrame([{"user": curr_user, "date": d_c.strftime("%d/%m/%Y"), "type": v_c}])
                conn.update(worksheet="Conges", data=pd.concat([df_c, new_c], ignore_index=True)[['user', 'date', 'type']])
                st.cache_data.clear()
                st.rerun()

if st.sidebar.button("🚪 Déconnexion"):
    st.session_state.authenticated = False
    st.session_state.user_key = None
    st.rerun()
