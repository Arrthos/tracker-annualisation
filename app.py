import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import holidays
import uuid
from supabase import create_client
import base64
import os

# --- 1. CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="Annualisation Gamba Rota", layout="centered")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_key' not in st.session_state:
    st.session_state.user_key = None
if 'solidarity_date' not in st.session_state:
    st.session_state.solidarity_date = date(2026, 5, 25)

# --- 2. CSS DESIGN ---
design_css = """
    <style>
    .stApp { background-color: #000000 !important; color: #EAEAEA; }
    header {visibility: hidden;}
    
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px;
        border-radius: 24px;
        text-align: center;
        backdrop-filter: blur(15px);
        margin: 15px 0;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    }

    .balance-val { font-size: 5.5rem; font-weight: 800; letter-spacing: -3px; margin: 5px 0; }
    .pos { color: #2ECC71; }
    .neg { color: #FF4B4B; }

    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #3498DB, #2ECC71);
        height: 10px;
        border-radius: 5px;
    }

    .holiday-badge {
        display: inline-block;
        background: rgba(52, 152, 219, 0.12);
        color: #3498DB;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 8px;
        border: 1px solid rgba(52, 152, 219, 0.2);
    }

    /* Style pour les lignes d'historique */
    .history-row {
        background: rgba(255,255,255,0.03); 
        padding: 12px; 
        border-radius: 12px; 
        display: flex; 
        align-items: center;
        height: 45px;
        margin-bottom: 8px;
    }
    
    /* Ajustement des boutons pour mobile */
    div[data-testid="column"] button {
        margin-top: 0px !important;
    }
    </style>
"""
st.markdown(design_css, unsafe_allow_html=True)

# --- 3. FONCTIONS LOGIQUE ---
@st.cache_resource
def get_supabase(): 
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

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

def load_img(path):
    if os.path.exists(path):
        with open(path, "rb") as f: 
            return base64.b64encode(f.read()).decode()
    return None

# --- 4. AUTHENTIFICATION ---
try:
    USERS = st.secrets["users"]
    supabase = get_supabase()
except Exception as e:
    st.error("Erreur de configuration (Secrets manquants ?)")
    st.stop()

if not st.session_state.authenticated:
    img_base64 = load_img("image_11.png")
    if img_base64:
        st.markdown(f'<div style="display:flex;justify-content:center;margin-top:40px;"><img src="data:image/png;base64,{img_base64}" width="200"></div>', unsafe_allow_html=True)
    
    with st.form("login"):
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Connexion"):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.authenticated = True
                st.session_state.user_key = u
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect")
    st.stop()

# --- 5. CHARGEMENT DES DONNÉES ---
curr_user = st.session_state.user_key
user_config = USERS[curr_user]

h_data = supabase.table("heures").select("*").eq("user", curr_user).execute().data
c_data = supabase.table("conges").select("*").eq("user", curr_user).execute().data

u_a = pd.DataFrame(h_data) if h_data else pd.DataFrame(columns=['id', 'date', 'val'])
u_c = pd.DataFrame(c_data) if c_data else pd.DataFrame(columns=['id', 'date', 'type', 'group_id'])

try:
    du = calculate_metrics(u_c.copy(), st.session_state.solidarity_date)
    h_sup_total = u_a['val'].astype(float).sum() if not u_a.empty else 0
    delta = user_config["base_sup"] + h_sup_total
    fait = du + delta
    h_contrat = user_config["contrat"]
except Exception as e:
    st.error(f"Erreur de calcul : {e}")
    st.stop()

# --- 6. INTERFACE DASHBOARD ---
st.markdown(f"<p style='text-align:center; color:#9BA1B0; margin-bottom:0;'>Bonjour,</p><h2 style='text-align:center; margin-top:0;'>{curr_user}</h2>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; margin-bottom:5px;'><small>Progression : <b>{int(fait)}</b> / {h_contrat}h</small></p>", unsafe_allow_html=True)
st.progress(min(max(fait / float(h_contrat), 0.0), 1.0))

status_color = "pos" if delta >= 0 else "neg"
st.markdown(f'<div class="glass-card"><small style="color:#9BA1B0">BALANCE HEURES SUP.</small><div class="balance-val {status_color}">{to_hm(delta)}</div></div>', unsafe_allow_html=True)

st.write("---")

# --- 7. FÉRIÉS & SOLIDARITÉ ---
st.markdown("#### 📅 Jours Fériés")
fr_h = get_fr_holidays([datetime.now().year])
badges = []
for d_h, name in sorted(fr_h.items()):
    if date.today() <= d_h <= (date.today() + timedelta(days=30)):
        badges.append(f'<span class="holiday-badge">{d_h.strftime("%d/%m")} : {name}</span>')

if badges:
    st.markdown(f'<div>{" ".join(badges)}</div>', unsafe_allow_html=True)
else:
    st.info("Aucun férié dans les 30 prochains jours.")

with st.expander("⚙️ Journée de solidarité"):
    new_sol = st.date_input("Date de la journée travaillée :", st.session_state.solidarity_date)
    if new_sol != st.session_state.solidarity_date:
        st.session_state.solidarity_date = new_sol
        st.rerun()

st.write("")

# --- 8. SAISIE DES DONNÉES & HISTORIQUE ---
t1, t2 = st.tabs(["⚡ Heures supp", "🌴 Congés / Arret"])

with t1:
    with st.expander("➕ Enregistrer des heures"):
        with st.form("h_f", clear_on_submit=True):
            typ = st.radio("Sens", ["Plus (+)", "Moins (-)"], horizontal=True)
            d = st.date_input("Date", date.today())
            h_col, m_col = st.columns(2)
            hv = h_col.number_input("H", 0, 12, 0)
            mv = m_col.number_input("M", 0, 59, 0)
            if st.form_submit_button("Valider"):
                val = (hv + mv/60) * (-1 if "Moins" in typ else 1)
                supabase.table("heures").insert({"user": curr_user, "date": str(d), "val": val}).execute()
                st.rerun()
    
    if not u_a.empty:
        for _, row in u_a.sort_values('date', ascending=False).iterrows():
            col1, col2 = st.columns([0.8, 0.2])
            col1.markdown(f"<div class='history-row'>📅 {pd.to_datetime(row['date']).strftime('%d/%m')} : &nbsp;<b>{to_hm(row['val'])}</b></div>", unsafe_allow_html=True)
            if col2.button("🗑️", key=f"h_{row['id']}", use_container_width=True):
                supabase.table("heures").delete().eq("id", row['id']).execute()
                st.rerun()

with t2:
    mode_periode = st.toggle("Mode Période", value=False)
    if not mode_periode:
        d_u = st.date_input("Jour", date.today())
        half = st.checkbox("Demi-journée")
        if st.button("Enregistrer", use_container_width=True):
            if d_u.weekday() < 5:
                supabase.table("conges").insert({"user": curr_user, "date": str(d_u), "type": 0.5 if half else 1.0, "group_id": str(uuid.uuid4())}).execute()
                st.rerun()
    else:
        cs, ce = st.columns(2)
        ds = cs.date_input("Début", date.today())
        de = ce.date_input("Fin", date.today() + timedelta(days=1))
        if st.button("Enregistrer période", use_container_width=True):
            gid = str(uuid.uuid4())
            days = pd.date_range(ds, de, freq='D').date
            rows = [{"user": curr_user, "date": str(day), "type": 1.0, "group_id": gid} for day in days if day.weekday() < 5]
            if rows:
                supabase.table("conges").insert(rows).execute()
                st.rerun()

    st.write("")
    if not u_c.empty:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        for gid, data in u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False):
            col1, col2 = st.columns([0.8, 0.2])
            s, e = data['dt'].min(), data['dt'].max()
            lbl = f"{s.strftime('%d/%m')} → {e.strftime('%d/%m')}" if len(data) > 1 else f"{s.strftime('%d/%m')}"
            if len(data) == 1 and data.iloc[0]['type'] == 0.5: lbl += " (1/2)"
            
            col1.markdown(f"<div class='history-row'>🌴 {lbl}</div>", unsafe_allow_html=True)
            if col2.button("🗑️", key=f"g_{gid}", use_container_width=True):
                supabase.table("conges").delete().eq("group_id", gid).execute()
                st.rerun()
