import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import holidays

# --- 1. CONFIGURATION ---
# Note : À terme, déplace ceci dans st.secrets pour la prod
USERS = {"Julien": {"password": "123", "base_sup": 20.5, "role": "admin"}}
OBJECTIF_ANNUEL = 1652.0

st.set_page_config(page_title="Work Tracker Pro", layout="centered")

if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_key' not in st.session_state: st.session_state.user_key = None

# --- 2. LOGIQUE CONNEXION ---
if not st.session_state.authenticated:
    st.title("🔐 Connexion")
    with st.form("login"):
        u_i = st.text_input("Identifiant")
        p_i = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Entrer", use_container_width=True):
            if u_i in USERS and USERS[u_i]["password"] == p_i:
                st.session_state.authenticated, st.session_state.user_key = True, u_i
                st.rerun()
    st.stop()

# --- 3. PARAMÈTRES (SIDEBAR) ---
st.sidebar.title("⚙️ Paramètres")
# Case calendrier pour la journée de solidarité (Lundi de Pentecôte 2024 par défaut)
sol_date = st.sidebar.date_input("Journée de Solidarité", value=date(2024, 5, 20))

# --- 4. CHARGEMENT & CALCULS ---
conn = st.connection("gsheets", type=GSheetsConnection)
df_a = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
df_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')

curr_user = st.session_state.user_key
u_a = df_a[df_a['user'] == curr_user].copy()
u_c = df_c[df_c['user'] == curr_user].copy()

def calculate_due(uid, df_conges, solidarity_day):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    fr_h = holidays.France(years=[sy, sy+1])
    
    # On retire la journée de solidarité des jours fériés pour qu'elle soit comptée comme travaillée
    if solidarity_day in fr_h:
        del fr_h[solidarity_day]
        
    d_conges = {pd.to_datetime(r['date'], dayfirst=True).date(): float(r['type']) for _, r in df_conges.iterrows()} if not df_conges.empty else {}
    theo = 0
    curr = start
    while curr <= now.replace(hour=23, minute=59):
        d = curr.date()
        if curr.weekday() < 5: # Lundi-Vendredi
            h_j = 7.5 if curr.weekday() <= 1 else 7.0 # Lun, Mar = 7.5h | Mer, Jeu, Ven = 7.0h
            if d not in fr_h:
                theo += h_j * (1 - d_conges.get(d, 0))
        curr += timedelta(days=1)
    return theo

my_theo = calculate_due(curr_user, u_c, sol_date)
val_ajust = u_a['val'].sum() if not u_a.empty else 0
my_delta = USERS[curr_user]["base_sup"] + val_ajust
fait = my_theo + my_delta

# --- 5. INTERFACE : TABLEAU DE BORD ---
st.title(f"Hello {curr_user}")

# BARRE DE PROGRESSION
st.write(f"**Progression annuelle : {int(fait)}h / {int(OBJECTIF_ANNUEL)}h**")
st.progress(min(fait / OBJECTIF_ANNUEL, 1.0))

# BALANCE (Style original conservé)
h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color_delta = "#238636" if my_delta >= 0 else "#da3633"

st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:15px; text-align:center; border:2px solid {color_delta}; margin-bottom:10px;">
        <p style="margin:0; opacity:0.6; font-size:0.8em; color:white;">BALANCE</p>
        <h1 style="color:{color_delta}; font-size:3.5em; margin:5px 0;">{'+' if my_delta >= 0 else '-'}{h}h{m:02d}</h1>
    </div>
""", unsafe_allow_html=True)

# BULLE UNIQUE FAIT / DÛ
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:10px; border:1px solid rgba(255,255,255,0.1); display:flex; justify-content:space-around; align-items:center;">
        <div style="text-align:center;">
            <span style="opacity:0.5; font-size:0.7em; color:white; text-transform:uppercase;">Fait</span>
            <span style="font-size:0.9em; font-weight:bold; color:white; margin-left:5px;">{fait:.1f}h</span>
        </div>
        <div style="width:1px; height:15px; background:rgba(255,255,255,0.2);"></div>
        <div style="text-align:center;">
            <span style="opacity:0.5; font-size:0.7em; color:white; text-transform:uppercase;">Dû</span>
            <span style="font-size:0.9em; font-weight:bold; color:white; margin-left:5px;">{my_theo:.1f}h</span>
        </div>
    </div>
""", unsafe_allow_html=True)

st.write("---")

# --- 6. ONGLETS ---
t1, t2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with t1:
    with st.expander("➕ Enregistrer des heures", expanded=False):
        with st.form("h_form", clear_on_submit=True):
            typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
            dat = st.date_input("Date", value=date.today())
            c_h, c_m = st.columns(2)
            h_s = c_h.number_input("Heures", 0, 12, 0)
            m_s = c_m.number_input("Minutes", 0, 59, 0)
            if st.form_submit_button("Valider", use_container_width=True):
                val = (h_s + m_s/60) * (-1 if "Moins" in typ else 1)
                new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": val}])
                # SÉCURITÉ : On relit la feuille juste avant d'écrire pour ne rien écraser
                latest_df = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
                conn.update(worksheet="Feuille 1", data=pd.concat([latest_df, new], ignore_index=True))
                st.rerun()

    with st.expander("🗑️ Historique", expanded=False):
        if u_a.empty: st.info("Vide")
        else:
            for i in u_a.index[::-1]:
                row = u_a.loc[i]
                c_t, c_b = st.columns([4, 1])
                c_t.write(f"**{row['date']}** : {row['val']:+.2f}h")
                if c_b.button("🗑️", key=f"del_h_{i}"):
                    # SÉCURITÉ : On relit avant de supprimer
                    latest_df = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
                    conn.update(worksheet="Feuille 1", data=latest_df.drop(i))
                    st.rerun()

with t2:
    today = datetime.now()
    cal = calendar.monthcalendar(today.year, today.month)
    u_c['dt_temp'] = pd.to_datetime(u_c['date'], dayfirst=True, errors='coerce')
    posees = u_c[(u_c['dt_temp'].dt.month == today.month) & (u_c['dt_temp'].dt.year == today.year)]['dt_temp'].dt.day.tolist() if not u_c.empty else []

    st.write(f"📅 **{calendar.month_name[today.month]} {today.year}**")
    cal_html = "<div style='display:grid; grid-template-columns:repeat(7,1fr); gap:4px;'>"
    for d in ["L","M","M","J","V","S","D"]: cal_html += f"<b style='text-align:center; font-size:0.7em; color:white;'>{d}</b>"
    for week in cal:
        for day in week:
            if day == 0: cal_html += "<div></div>"
            else:
                bg = "#007bff" if day in posees else "rgba(255,255,255,0.05)"
                border = "2px solid #238636" if day == today.day else "none"
                cal_html += f"<div style='text-align:center; padding:8px 0; background:{bg}; border:{border}; border-radius:5px; color:white; font-size:0.8em;'>{day}</div>"
    cal_html += "</div>"
    st.markdown(cal_html, unsafe_allow_html=True)

    with st.expander("➕ Poser un congé", expanded=False):
        with st.form("c_form", clear_on_submit=True):
            d_c = st.date_input("Date", value=date.today())
            t_c = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
            if st.form_submit_button("Confirmer", use_container_width=True):
                v_c = 1.0 if t_c == "Journée" else 0.5
                new_c = pd.DataFrame([{"user": curr_user, "date": d_c.strftime("%d/%m/%Y"), "type": v_c}])
                # SÉCURITÉ : On relit avant d'ajouter
                latest_df_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')
                conn.update(worksheet="Conges", data=pd.concat([latest_df_c, new_c], ignore_index=True))
                st.rerun()

    with st.expander("🗑️ Liste des congés", expanded=False):
        if u_c.empty: st.info("Vide")
        else:
            for i in u_c.index[::-1]:
                row = u_c.loc[i]
                c_t, c_b = st.columns([4, 1])
                c_t.write(f"📅 {row['date']} ({row['type']}j)")
                if c_b.button("🗑️", key=f"del_c_{i}"):
                    # SÉCURITÉ : On relit avant de supprimer
                    latest_df_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')
                    conn.update(worksheet="Conges", data=latest_df_c.drop(i))
                    st.rerun()

if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()
