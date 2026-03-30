import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import calendar
import holidays
from supabase import create_client, Client

# --- 1. CONFIGURATION & STYLE CSS (FORCE L'ALIGNEMENT) ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

# Ce bloc CSS force les éléments à rester sur la même ligne et alignés au centre
st.markdown("""
    <style>
    /* Aligne le bouton et le texte sur la même ligne verticale */
    [data-testid="column"] {
        display: flex;
        align-items: center;
        justify-content: flex-start;
    }
    /* Supprime l'espace blanc au-dessus des boutons dans les colonnes */
    .stButton button {
        margin-top: 0px !important;
        padding: 5px 10px !important;
    }
    /* Réduit l'espace entre les lignes de l'historique */
    .element-container {
        margin-bottom: 0.2rem !important;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = get_supabase()

@st.cache_data(ttl=3600)
def get_fr_holidays(years):
    return holidays.France(years=years)

def to_hm(decimal_hours):
    abs_h = abs(decimal_hours)
    h = int(abs_h)
    m = int(round((abs_h - h) * 60))
    if m == 60: h += 1; m = 0
    sign = "-" if decimal_hours < 0 else ("+" if decimal_hours > 0 else "")
    return f"{sign}{h}h{m:02d}"

# --- 2. LOGIQUE DE CALCUL ---
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
    if not df_conges.empty and 'date' in df_conges.columns:
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date']).dt.date
        conges_map = df_conges.dropna(subset=['dt_temp']).set_index('dt_temp')['type'].to_dict()
        df_dates['conge_val'] = df_dates['date'].dt.date.map(conges_map).fillna(0)
        df_dates['h_theo'] *= (1 - df_dates['conge_val'])
    return df_dates['h_theo'].sum()

# --- 3. AUTHENTIFICATION ---
USERS = {"Julien": {"password": "%Gfpass115", "base_sup": 20.5}}
if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center;'>🔐 Connexion</h1>", unsafe_allow_html=True)
    with st.form("login"):
        u_i = st.text_input("Identifiant")
        p_i = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Entrer", use_container_width=True):
            if u_i in USERS and USERS[u_i]["password"] == p_i:
                st.session_state.authenticated, st.session_state.user_key = True, u_i
                st.rerun()
    st.stop()

# --- 4. DATA ---
curr_user = st.session_state.user_key
h_res = supabase.table("heures").select("*").eq("user", curr_user).execute()
c_res = supabase.table("conges").select("*").eq("user", curr_user).execute()
u_a = pd.DataFrame(h_res.data) if h_res.data else pd.DataFrame(columns=['id', 'user', 'date', 'val'])
u_c = pd.DataFrame(c_res.data) if c_res.data else pd.DataFrame(columns=['id', 'user', 'date', 'type'])

# --- 5. CALCULS ---
sol_date = date(2026, 6, 1)
my_theo = calculate_due_fast(u_c.copy(), sol_date)
val_ajust = u_a['val'].astype(float).sum() if not u_a.empty else 0
my_delta = USERS[curr_user]["base_sup"] + val_ajust
fait = my_theo + my_delta

# --- 6. INTERFACE ---
st.markdown(f"<h1 style='text-align: center; margin-bottom: 20px;'>Hello {curr_user}</h1>", unsafe_allow_html=True)

# Bloc Balance
balance_str = to_hm(my_delta)
color_delta = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:15px; text-align:center; border:2px solid {color_delta}; margin-bottom: 20px;">
        <p style="margin:0; opacity:0.6; font-size:0.8em; color:white;">BALANCE</p>
        <h1 style="color:{color_delta}; font-size:3.5em; margin:5px 0;">{balance_str}</h1>
    </div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with tab1:
    with st.expander("➕ Ajouter"):
        with st.form("h_form", clear_on_submit=True):
            typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
            dat = st.date_input("Date", value=date.today())
            c1, c2 = st.columns(2)
            h_v, m_v = c1.number_input("H", 0, 12, 0), c2.number_input("M", 0, 59, 0)
            if st.form_submit_button("Valider"):
                val = (h_v + m_v/60) * (-1 if "Moins" in typ else 1)
                supabase.table("heures").insert({"user": curr_user, "date": str(dat), "val": val}).execute()
                st.rerun()
    
    st.write("---")
    if u_a.empty: st.info("Vide")
    else:
        for _, row in u_a.iloc[::-1].iterrows():
            # Colonnes très déséquilibrées pour forcer l'alignement à droite
            c_txt, c_btn = st.columns([0.85, 0.15])
            d_f = pd.to_datetime(row['date']).strftime("%d/%m")
            c_txt.markdown(f"**{d_f}** : `{to_hm(row['val'])}`")
            if c_btn.button("🗑️", key=f"h_{row['id']}"):
                supabase.table("heures").delete().eq("id", row['id']).execute()
                st.rerun()

with tab2:
    # Calendrier et Formulaire (simplifiés pour l'exemple)
    with st.expander("➕ Poser"):
        with st.form("c_form", clear_on_submit=True):
            sel = st.date_input("Dates", value=[date.today()])
            if st.form_submit_button("Valider"):
                # Logique insertion...
                st.rerun()
    
    st.write("---")
    if u_c.empty: st.info("Vide")
    else:
        for _, row in u_c.iloc[::-1].iterrows():
            c_txt, c_btn = st.columns([0.85, 0.15])
            d_f = pd.to_datetime(row['date']).strftime("%d/%m")
            c_txt.markdown(f"📅 **{d_f}** : `{row['type']}j`")
            if c_btn.button("🗑️", key=f"c_{row['id']}"):
                supabase.table("conges").delete().eq("id", row['id']).execute()
                st.rerun()
