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

# --- 2. LOGIQUE DE CALCUL RAPIDE ---
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
        # On prend la dernière valeur si plusieurs entrées pour la même date
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

# --- 5. CALCULS ET DASHBOARD ---
st.sidebar.title("⚙️ Paramètres")
sol_date = st.sidebar.date_input("Journée de Solidarité", value=date(2024, 5, 20))

my_theo = calculate_due_fast(u_c.copy(), sol_date)
val_ajust = u_a['val'].sum() if not u_a.empty else 0
my_delta = USERS[curr_user]["base_sup"] + val_ajust
fait = my_theo + my_delta

st.title(f"Hello {curr_user}")

# Barre de progression
st.write(f"**Progression : {int(fait)}h / 1652h**")
st.progress(min(max(fait / 1652.0, 0.0), 1.0))

# Balance (HTML/CSS)
h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color_delta = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:15px; text-align:center; border:2px solid {color_delta}; margin-bottom:10px;">
        <p style="margin:0; opacity:0.6; font-size:0.8em; color:white;">BALANCE</p>
        <h1 style="color:{color_delta}; font-size:3.5em; margin:5px 0;">{'+' if my_delta >= 0 else '-'}{h}h{m:02d}</h1>
    </div>
""", unsafe_allow_html=True)

# Bulle Fait / Dû
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.03); padding:8px; border-radius:10px; border:1px solid rgba(255,255,255,0.1); display:flex; justify-content:space-around; align-items:center; margin-bottom:20px;">
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

# --- 6. FRAGMENTS POUR INTERACTION RAPIDE ---

@st.fragment
def section_heures(all_data, user_data):
    with st.expander("➕ Enregistrer des heures", expanded=False):
        with st.form("h_form", clear_on_submit=True):
            typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
            dat = st.date_input("Date", value=date.today())
            c1, c2 = st.columns(2)
            h_s = c1.number_input("Heures", 0, 12, 0)
            m_s = c2.number_input("Minutes", 0, 59, 0)
            if st.form_submit_button("Valider", use_container_width=True):
                val = (h_s + m_s/60) * (-1 if "Moins" in typ else 1)
                new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": val}])
                # On recharge pour éviter d'écraser
                latest = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
                conn.update(worksheet="Feuille 1", data=pd.concat([latest, new], ignore_index=True))
                st.rerun()

    st.write("### 🗑️ Historique Heures")
    if user_data.empty:
        st.info("Aucun historique.")
    else:
        for i in user_data.index[::-1]:
            row = user_data.loc[i]
            col_t, col_b = st.columns([4, 1])
            col_t.write(f"**{row['date']}** : {row['val']:+.2f}h")
            if col_b.button("🗑️", key=f"del_h_{i}"):
                latest = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
                conn.update(worksheet="Feuille 1", data=latest.drop(i))
                st.rerun()

@st.fragment
def section_conges(all_data_c, user_data_c):
    with st.expander("➕ Poser un congé", expanded=False):
        with st.form("c_form", clear_on_submit=True):
            d_c = st.date_input("Date congé", value=date.today())
            t_c = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
            if st.form_submit_button("Confirmer", use_container_width=True):
                v_c = 1.0 if t_c == "Journée" else 0.5
                new_c = pd.DataFrame([{"user": curr_user, "date": d_c.strftime("%d/%m/%Y"), "type": v_c}])
                latest_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')
                conn.update(worksheet="Conges", data=pd.concat([latest_c, new_c], ignore_index=True))
                st.rerun()

    st.write("### 🗑️ Historique Congés")
    if user_data_c.empty:
        st.info("Aucun congé posé.")
    else:
        for i in user_data_c.index[::-1]:
            row = user_data_c.loc[i]
            col_t, col_b = st.columns([4, 1])
            col_t.write(f"📅 {row['date']} ({row['type']}j)")
            if col_b.button("🗑️", key=f"del_c_{i}"):
                latest_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')
                conn.update(worksheet="Conges", data=latest_c.drop(i))
                st.rerun()

# --- 7. AFFICHAGE DES ONGLETS ---
tab1, tab2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with tab1:
    section_heures(df_a, u_a)

with tab2:
    section_conges(df_c, u_c)

if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()
