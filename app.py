import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
from datetime import datetime, date
import holidays

# --- 1. CONFIG ET CACHE ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

@st.cache_data(ttl=3600)
def get_fr_holidays(years):
    return holidays.France(years=years)

# --- 2. LOGIQUE DE CALCUL (RAPIDE) ---
def calculate_due_fast(df_conges, solidarity_day):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    dr = pd.date_range(start=start, end=now, freq='D')
    df_dates = pd.DataFrame({'date': dr})
    df_dates['weekday'] = df_dates['date'].dt.weekday
    df_dates = df_dates[df_dates['weekday'] < 5].copy()
    df_dates['h_theo'] = np.where(df_dates['weekday'] <= 1, 7.5, 7.0)
    
    fr_h = get_fr_holidays([sy, sy+1])
    df_dates['is_holiday'] = df_dates['date'].dt.date.apply(lambda x: x in fr_h and x != solidarity_day)
    df_dates.loc[df_dates['is_holiday'], 'h_theo'] = 0
    
    if not df_conges.empty:
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date'], dayfirst=True, errors='coerce').dt.date
        conges_map = df_conges.dropna(subset=['dt_temp']).set_index('dt_temp')['type'].to_dict()
        df_dates['conge_val'] = df_dates['date'].dt.date.map(conges_map).fillna(0)
        df_dates['h_theo'] *= (1 - df_dates['conge_val'])
        
    return df_dates['h_theo'].sum()

# --- 3. AUTHENTIFICATION ---
USERS = {"Julien": {"password": "123", "base_sup": 20.5}}

if 'authenticated' not in st.session_state: st.session_state.authenticated = False

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

# --- 5. SIDEBAR & CALCULS ---
st.sidebar.title("⚙️ Paramètres")
sol_date = st.sidebar.date_input("Journée de Solidarité", value=date(2024, 5, 20))

my_theo = calculate_due_fast(u_c.copy(), sol_date)
my_delta = USERS[curr_user]["base_sup"] + (u_a['val'].sum() if not u_a.empty else 0)
fait = my_theo + my_delta

# --- 6. DASHBOARD (L'AFFICHAGE QUI MANQUAIT) ---
st.title(f"Hello {curr_user}")

st.write(f"**Progression : {int(fait)}h / 1652h**")
st.progress(min(fait / 1652.0, 1.0))

h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color_delta = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f'<div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:15px; text-align:center; border:2px solid {color_delta}; margin-bottom:10px;"><p style="margin:0; opacity:0.6; font-size:0.8em; color:white;">BALANCE</p><h1 style="color:{color_delta}; font-size:3.5em; margin:5px 0;">{"+" if my_delta >= 0 else "-"}{h}h{m:02d}</h1></div>', unsafe_allow_html=True)

# --- 7. FRAGMENTS (FONCTIONS) ---
@st.fragment
def fragment_heures(df_global, u_data):
    with st.expander("➕ Enregistrer des heures"):
        with st.form("h_form", clear_on_submit=True):
            typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
            dat = st.date_input("Date", value=date.today())
            c1, c2 = st.columns(2)
            h_s = c1.number_input("H", 0, 12, 0)
            m_s = c2.number_input("M", 0, 59, 0)
            if st.form_submit_button("Valider"):
                val = (h_s + m_s/60) * (-1 if "Moins" in typ else 1)
                new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": val}])
                conn.update(worksheet="Feuille 1", data=pd.concat([df_global, new], ignore_index=True))
                st.rerun()
    
    for i in u_data.index[::-1]:
        row = u_data.loc[i]
        c_t, c_b = st.columns([4, 1])
        c_t.write(f"**{row['date']}** : {row['val']:+.2f}h")
        if c_b.button("🗑️", key=f"del_h_{i}"):
            conn.update(worksheet="Feuille 1", data=df_global.drop(i))
            st.rerun()

@st.fragment
def fragment_conges(df_global_c, u_data_c):
    with st.expander("➕ Poser un congé"):
        with st.form("c_form", clear_on_submit=True):
            d_c = st.date_input("Date", value=date.today())
            t_c = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
            if st.form_submit_button("Confirmer"):
                v_c = 1.0 if t_c == "Journée" else 0.5
                new_c = pd.DataFrame([{"user": curr_user, "date": d_c.strftime("%d/%m/%Y"), "type": v_c}])
                conn.update(worksheet="Conges", data=pd.concat([df_global_c, new_c], ignore_index=True))
                st.rerun()
    
    for i in u_data_c.index[::-1]:
        row = u_data_c.loc[i]
        st.write(f"📅 {row['date']} ({row['type']}j)")

# --- 8. APPEL DES ONGLETS ---
t1, t2 = st.tabs(["⚡ Heures", "🌴 Congés"])
with t1:
    fragment_heures(df_a, u_a)
with t2:
    fragment_conges(df_c, u_c)

if st.sidebar.button("🚪 Déconnexion"):
    st.session_state.authenticated = False
    st.rerun()
