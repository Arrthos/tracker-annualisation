import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
from datetime import datetime, date
import calendar
import holidays

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

@st.cache_data(ttl=3600)
def get_fr_holidays(years):
    return holidays.France(years=years)

# --- 2. LOGIQUE DE CALCUL VECTORISÉE (PERFORMANCE) ---
def calculate_due_fast(df_conges, solidarity_day):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    
    # Création du range de dates
    dr = pd.date_range(start=start, end=now, freq='D')
    df_dates = pd.DataFrame({'date': dr})
    df_dates['weekday'] = df_dates['date'].dt.weekday
    
    # Garder uniquement Lun-Ven (0-4)
    df_dates = df_dates[df_dates['weekday'] < 5].copy()
    
    # Heures théoriques : Lun-Mar = 7.5h | Mer-Jeu-Ven = 7.0h
    df_dates['h_theo'] = np.where(df_dates['weekday'] <= 1, 7.5, 7.0)
    
    # Jours fériés (en excluant la journée de solidarité choisie)
    fr_h = get_fr_holidays([sy, sy+1])
    df_dates['is_holiday'] = df_dates['date'].dt.date.apply(lambda x: x in fr_h and x != solidarity_day)
    df_dates.loc[df_dates['is_holiday'], 'h_theo'] = 0
    
    # Déduction des congés
    if not df_conges.empty:
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date'], dayfirst=True, errors='coerce').dt.date
        conges_map = df_conges.dropna(subset=['dt_temp']).set_index('dt_temp')['type'].to_dict()
        df_dates['conge_val'] = df_dates['date'].dt.date.map(conges_map).fillna(0)
        df_dates['h_theo'] *= (1 - df_dates['conge_val'])
        
    return df_dates['h_theo'].sum()

# --- 3. AUTHENTIFICATION ---
USERS = {"Julien": {"password": "123", "base_sup": 20.5}}

if 'authenticated' not in st.session_state: 
    st.session_state.authenticated = False

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

# --- 4. CHARGEMENT DES DONNÉES ---
conn = st.connection("gsheets", type=GSheetsConnection)
df_a = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
df_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')

curr_user = st.session_state.user_key
u_a = df_a[df_a['user'] == curr_user].copy()
u_c = df_c[df_c['user'] == curr_user].copy()

# --- 5. PARAMÈTRES & CALCULS ---
st.sidebar.title("⚙️ Paramètres")
# Journée de solidarité (Lundi de Pentecôte 2026 par défaut)
sol_date = st.sidebar.date_input("Journée de Solidarité", value=date(2026, 6, 1))

my_theo = calculate_due_fast(u_c.copy(), sol_date)
val_ajust = u_a['val'].sum() if not u_a.empty else 0
my_delta = USERS[curr_user]["base_sup"] + val_ajust
fait = my_theo + my_delta
objectif = 1652.0

# --- 6. INTERFACE DASHBOARD ---
st.title(f"Hello {curr_user}")

# Ligne Progression optimisée (Texte + Chiffres sur une seule ligne)
st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: -5px;">
        <p style="margin: 0; font-weight: bold; color: white;">Progression annuelle</p>
        <p style="margin: 0; opacity: 0.8; color: white;"><b>{int(fait)}h</b> / {int(objectif)}h</p>
    </div>
""", unsafe_allow_html=True)

st.progress(min(max(fait / objectif, 0.0), 1.0))

# Bloc Balance
h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color_delta = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:15px; text-align:center; border:2px solid {color_delta}; margin: 15px 0 10px 0;">
        <p style="margin:0; opacity:0.6; font-size:0.8em; color:white;">BALANCE</p>
        <h1 style="color:{color_delta}; font-size:3.5em; margin:5px 0;">{'+' if my_delta >= 0 else '-'}{h}h{m:02d}</h1>
    </div>
    <div style="display:flex; justify-content:space-around; background:rgba(255,255,255,0.02); padding:10px; border-radius:10px; border:1px solid rgba(255,255,255,0.1); margin-bottom:20px;">
        <div style="text-align:center;"><small style="opacity:0.5; color:white;">FAIT</small><br><b style="color:white;">{fait:.1f}h</b></div>
        <div style="width:1px; background:rgba(255,255,255,0.1);"></div>
        <div style="text-align:center;"><small style="opacity:0.5; color:white;">DÛ</small><br><b style="color:white;">{my_theo:.1f}h</b></div>
    </div>
""", unsafe_allow_html=True)

# --- 7. ONGLETS & FRAGMENTS ---
tab1, tab2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with tab1:
    @st.fragment
    def section_heures():
        with st.expander("➕ Enregistrer des heures", expanded=False):
            with st.form("h_form", clear_on_submit=True):
                typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
                dat = st.date_input("Date", value=date.today())
                c1, c2 = st.columns(2)
                h_v = c1.number_input("Heures", 0, 12, 0)
                m_v = c2.number_input("Minutes", 0, 59, 0)
                if st.form_submit_button("Valider", use_container_width=True):
                    val = (h_v + m_v/60) * (-1 if "Moins" in typ else 1)
                    new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": val}])
                    # Recharge sécurisée
                    latest = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
                    conn.update(worksheet="Feuille 1", data=pd.concat([latest, new], ignore_index=True))
                    st.rerun()
        
        st.subheader("🗑️ Historique")
        if u_a.empty:
            st.info("Aucune donnée enregistrée.")
        else:
            for i in u_a.index[::-1]:
                c_t, c_b = st.columns([4, 1])
                c_t.write(f"**{u_a.loc[i, 'date']}** : {u_a.loc[i, 'val']:+.2f}h")
                if c_b.button("🗑️", key=f"del_h_{i}"):
                    latest = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
                    conn.update(worksheet="Feuille 1", data=latest.drop(i))
                    st.rerun()
    section_heures()

with tab2:
    # --- CALENDRIER VISUEL ---
    today = datetime.now()
    u_c['dt_temp'] = pd.to_datetime(u_c['date'], dayfirst=True, errors='coerce')
    posees = u_c[(u_c['dt_temp'].dt.month == today.month) & (u_c['dt_temp'].dt.year == today.year)]['dt_temp'].dt.day.tolist() if not u_c.empty else []
    
    st.write(f"📅 **{calendar.month_name[today.month]} {today.year}**")
    cal_html = "<div style='display:grid; grid-template-columns:repeat(7,1fr); gap:4px; margin-bottom:15px;'>"
    for d in ["L","M","M","J","V","S","D"]: cal_html += f"<b style='text-align:center; font-size:0.7em; color:white;'>{d}</b>"
    for week in calendar.monthcalendar(today.year, today.month):
        for day in week:
            if day == 0: cal_html += "<div></div>"
            else:
                bg = "#007bff" if day in posees else "rgba(255,255,255,0.05)"
                border = "2px solid #238636" if day == today.day else "none"
                cal_html += f"<div style='text-align:center; padding:8px 0; background:{bg}; border:{border}; border-radius:5px; color:white; font-size:0.8em;'>{day}</div>"
    st.markdown(cal_html + "</div>", unsafe_allow_html=True)

    @st.fragment
    def section_conges():
        with st.expander("➕ Poser un congé", expanded=False):
            with st.form("c_form", clear_on_submit=True):
                d_v = st.date_input("Date du congé", value=date.today())
                t_v = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
                if st.form_submit_button("Confirmer", use_container_width=True):
                    val_c = 1.0 if t_v == "Journée" else 0.5
                    new_c = pd.DataFrame([{"user": curr_user, "date": d_v.strftime("%d/%m/%Y"), "type": val_c}])
                    latest_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')
                    conn.update(worksheet="Conges", data=pd.concat([latest_c, new_c], ignore_index=True))
                    st.rerun()

        st.subheader("🗑️ Liste des congés")
        if u_c.empty:
            st.info("Aucun congé enregistré.")
        else:
            for i in u_c.index[::-1]:
                c_t, c_b = st.columns([4, 1])
                c_t.write(f"📅 {u_c.loc[i, 'date']} ({u_c.loc[i, 'type']}j)")
                if c_b.button("🗑️", key=f"del_c_{i}"):
                    latest_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')
                    conn.update(worksheet="Conges", data=latest_c.drop(i))
                    st.rerun()
    section_conges()

# --- 8. DÉCONNEXION ---
if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()
