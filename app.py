import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import holidays
import uuid
from supabase import create_client
import base64

# --- 1. CONFIGURATION & DESIGN ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #EAEAEA; }
    header {visibility: hidden;}
    
    /* Carte de balance Glassmorphism */
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 20px;
        text-align: center;
        backdrop-filter: blur(10px);
        margin: 10px 0;
    }

    .balance-val {
        font-size: 5rem;
        font-weight: 800;
        letter-spacing: -2px;
        margin: 5px 0;
    }
    .pos { color: #2ECC71; } /* Vert si positif */
    .neg { color: #E74C3C; } /* Rouge si negatif */

    /* Progress bar */
    .stProgress > div > div > div > div {
        background-color: #3498DB;
        height: 8px;
    }

    .stMarkdown, p, small { color: #EAEAEA !important; }
    .sub-text { color: #888 !important; font-size: 0.8rem; }
    
    /* Centrage de l'image de login */
    .login-logo {
        display: flex;
        justify-content: center;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. FONCTIONS LOGIQUES ---
@st.cache_resource
def get_supabase(): 
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = get_supabase()

@st.cache_data(ttl=3600)
def get_fr_holidays(years): 
    return holidays.France(years=years)

def to_hm(decimal_hours):
    abs_h = abs(decimal_hours)
    h, m = int(abs_h), int(round((abs_h - int(abs_h)) * 60))
    if m == 60: h += 1; m = 0
    return f"{'-' if decimal_hours < 0 else '+'}{h}h{m:02d}"

def calculate_metrics(df_conges, solidarity_day):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    dr = pd.date_range(start=start, end=now, freq='D')
    df = pd.DataFrame({'date': dr})
    df['wd'] = df['date'].dt.weekday
    df = df[df['wd'] < 5].copy()
    df['h_theo'] = np.where(df['wd'] <= 1, 7.5, 7.0)
    fr_h = get_fr_holidays([sy, sy+1])
    df['is_h'] = df['date'].dt.date.apply(lambda x: x in fr_h and x != solidarity_day)
    df.loc[df['is_h'], 'h_theo'] = 0
    if not df_conges.empty:
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date']).dt.date
        c_map = df_conges.groupby('dt_temp')['type'].sum().to_dict()
        df['c_val'] = df['date'].dt.date.map(c_map).fillna(0)
        df['h_theo'] = np.maximum(0, df['h_theo'] * (1 - df['c_val']))
    return df['h_theo'].sum()

def load_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# --- 3. AUTHENTIFICATION ---
USERS = {"Julien": {"password": "%Gfpass115", "base_sup": 20.5}}

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    # Affichage Logo image_11.png
    try:
        img_base64 = load_image("image_11.png")
        st.markdown(f'<div class="login-logo"><img src="data:image/png;base64,{img_base64}" width="150"></div>', unsafe_allow_html=True)
    except:
        st.write("---")
        
    with st.form("login"):
        st.markdown("<h3 style='text-align:center;'>Connexion</h3>", unsafe_allow_html=True)
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("SE CONNECTER"):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.authenticated = True
                st.session_state.user_key = u
                st.rerun()
            else:
                st.error("Identifiants incorrects")
    st.stop()

# --- 4. RÉCUPÉRATION DATA ---
curr_user = st.session_state.user_key
h_data = supabase.table("heures").select("*").eq("user", curr_user).execute().data
c_data = supabase.table("conges").select("*").eq("user", curr_user).execute().data
u_a = pd.DataFrame(h_data) if h_data else pd.DataFrame(columns=['id', 'date', 'val'])
u_c = pd.DataFrame(c_data) if c_data else pd.DataFrame(columns=['id', 'date', 'type', 'group_id'])

# --- 5. CALCULS DASHBOARD ---
sol_date = date(2026, 6, 1)
du = calculate_metrics(u_c.copy(), sol_date)
h_sup_total = u_a['val'].astype(float).sum() if not u_a.empty else 0
delta = USERS[curr_user]["base_sup"] + h_sup_total
fait = du + delta

# --- 6. INTERFACE UTILISATEUR ---

# Header
st.markdown(f"<p style='text-align:center; color:#888; margin-bottom:0;'>Bonjour,</p><h2 style='text-align:center; margin-top:0;'>{curr_user}</h2>", unsafe_allow_html=True)

# Barre de progression en haut
st.markdown(f"<p style='text-align:center; margin-bottom:5px;'><small><b>{int(fait)}h</b> / 1652h</small></p>", unsafe_allow_html=True)
st.progress(min(max(fait / 1652.0, 0.0), 1.0))

# Carte Balance (Vert/Rouge)
status_color = "pos" if delta >= 0 else "neg"
st.markdown(f"""
    <div class="glass-card">
        <small class="sub-text">BALANCE ACTUELLE</small>
        <div class="balance-val {status_color}">{to_hm(delta)}</div>
    </div>
""", unsafe_allow_html=True)

# Dû et Fait sur la même ligne
col1, col2 = st.columns(2)
col1.markdown(f"<p style='text-align:left;'><small class='sub-text'>DÛ :</small> <b>{int(du)}h</b></p>", unsafe_allow_html=True)
col2.markdown(f"<p style='text-align:right;'><small class='sub-text'>FAIT :</small> <b>{to_hm(fait).replace('+', '')}</b></p>", unsafe_allow_html=True)

st.write("---")

# --- 7. ONGLETS ---
tab1, tab2 = st.tabs(["⚡ HEURES", "🌴 CONGÉS"])

with tab1:
    with st.expander("➕ Enregistrer des heures"):
        with st.form("h_form", clear_on_submit=True):
            typ = st.radio("Sens", ["Plus (+)", "Moins (-)"], horizontal=True)
            d = st.date_input("Date", date.today())
            h_col, m_col = st.columns(2)
            hv = h_col.number_input("Heures", 0, 12, 0)
            mv = m_col.number_input("Minutes", 0, 59, 0)
            if st.form_submit_button("VALIDER"):
                val_final = (hv + mv/60) * (-1 if "Moins" in typ else 1)
                supabase.table("heures").insert({"user": curr_user, "date": str(d), "val": val_final}).execute()
                st.rerun()
    
    # Historique
    for _, row in u_a.iloc[::-1].iterrows():
        c_txt, c_del = st.columns([0.85, 0.15])
        c_txt.markdown(f"<div style='background:rgba(255,255,255,0.02); padding:10px; border-radius:10px; margin-bottom:5px;'>📅 {pd.to_datetime(row['date']).strftime('%d/%m')} : <b>{to_hm(row['val'])}</b></div>", unsafe_allow_html=True)
        if c_del.button("🗑️", key=f"h_{row['id']}"):
            supabase.table("heures").delete().eq("id", row['id']).execute()
            st.rerun()

with tab2:
    mode_p = st.toggle("Mode Période", value=False)
    if not mode_p:
        d_u = st.date_input("Choisir le jour", date.today())
        half = st.checkbox("Demi-journée")
        if st.button("ENREGISTRER JOUR"):
            if d_u.weekday() < 5:
                supabase.table("conges").insert({"user": curr_user, "date": str(d_u), "type": 0.5 if half else 1.0, "group_id": str(uuid.uuid4())}).execute()
                st.rerun()
    else:
        c_start, c_end = st.columns(2)
        ds = c_start.date_input("Du", date.today())
        de = c_end.date_input("Au", date.today() + timedelta(days=1))
        if st.button("ENREGISTRER PÉRIODE"):
            if ds <= de:
                gid = str(uuid.uuid4())
                days = pd.date_range(ds, de, freq='D').date
                rows = [{"user": curr_user, "date": str(day), "type": 1.0, "group_id": gid} for day in days if day.weekday() < 5]
                if rows:
                    supabase.table("conges").insert(rows).execute()
                    st.rerun()

    if not u_c.empty:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        for gid, data in u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False):
            cx, cy = st.columns([0.85, 0.15])
            s, e = data['dt'].min(), data['dt'].max()
            lbl = f"{s.strftime('%d/%m')} → {e.strftime('%d/%m')}" if len(data) > 1 else f"{s.strftime('%d/%m')}"
            if len(data) == 1 and data.iloc[0]['type'] == 0.5: lbl += " (1/2)"
            cx.markdown(f"<div style='background:rgba(255,255,255,0.02); padding:10px; border-radius:10px; margin-bottom:5px;'>🌴 {lbl}</div>", unsafe_allow_html=True)
            if cy.button("🗑️", key=f"g_{gid}"):
                supabase.table("conges").delete().eq("group_id", gid).execute()
                st.rerun()
