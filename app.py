import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import holidays
import uuid
from supabase import create_client
import base64
import os

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

# CSS pour le look moderne (Gris Anthracite pour le Dashboard)
design_css = """
    <style>
    /* FOND LOGIN : Noir Pur pour fusionner avec l'image */
    .stApp { background-color: #000000 !important; color: #EAEAEA; }
    header {visibility: hidden;}
    
    /* FOND DASHBOARD : Gris Anthracite Moderne (moins foncé) */
    body[data-authenticated="true"] .stApp {
        background-color: #1A1C23 !important; 
    }

    /* CARTES : Glassmorphism moderne */
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

    .balance-val {
        font-size: 5.5rem;
        font-weight: 800;
        letter-spacing: -3px;
        margin: 5px 0;
    }
    .pos { color: #2ECC71; }
    .neg { color: #FF4B4B; }

    .stMarkdown, p, small, label { color: #F0F2F6 !important; }
    .sub-text { color: #9BA1B0 !important; font-size: 0.85rem; font-weight: 500; }
    
    /* PROGRESS BAR */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #3498DB, #2ECC71);
        height: 10px;
        border-radius: 5px;
    }

    /* Style pour les badges de jours fériés épurés */
    .holiday-badge {
        display: inline-block;
        background: rgba(52, 152, 219, 0.15);
        color: #3498DB;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 8px;
        border: 1px solid rgba(52, 152, 219, 0.3);
    }

    /* LOGIN LOGO */
    .login-logo-container {
        display: flex;
        justify-content: center;
        margin-top: 40px;
        margin-bottom: 10px;
    }
    
    [data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    </style>
"""
st.markdown(design_css, unsafe_allow_html=True)

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

# Metriques calculées avec SOLIDARITÉ DYNAMIQUE
def calculate_metrics(df_conges, solidarity_day):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    dr = pd.date_range(start=start, end=now, freq='D')
    df = pd.DataFrame({'date': dr})
    df['wd'] = df['date'].dt.weekday
    df = df[df['wd'] < 5].copy()
    
    # Heures théoriques (L-M: 7.5h, Me-J-V: 7h)
    df['h_theo'] = np.where(df['wd'] <= 1, 7.5, 7.0)
    
    # Jours fériés (La journée de solidarité est TRAVAILLÉE donc h_theo reste > 0)
    fr_h = get_fr_holidays([sy, sy+1])
    # Correction de la logique : La journée de solidarité est TRAVAILLÉE, donc pas d'heures théoriques à 0
    df['is_h'] = df['date'].dt.date.apply(lambda x: x in fr_h and x != solidarity_day)
    df.loc[df['is_h'], 'h_theo'] = 0
    
    if not df_conges.empty:
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date']).dt.date
        c_map = df_conges.groupby('dt_temp')['type'].sum().to_dict()
        df['c_val'] = df['date'].dt.date.map(c_map).fillna(0)
        df['h_theo'] = np.maximum(0, df['h_theo'] * (1 - df['c_val']))
    return df['h_theo'].sum()

def load_img(path):
    with open(path, "rb") as f: return base64.b64encode(f.read()).decode()

# --- 3. AUTHENTIFICATION & PARAMÈTRES ---
USERS = {"Julien": {"password": "%Gfpass115", "base_sup": 20.5}}

if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'solidarity_date' not in st.session_state: st.session_state.solidarity_date = date(2026, 5, 25) # Par défaut Lundi Pentecôte

if not st.session_state.authenticated:
    img_path = "image_11.png" 
    if os.path.exists(img_path):
        st.markdown(f'<div class="login-logo-container"><img src="data:image/png;base64,{load_img(img_path)}" width="200"></div>', unsafe_allow_html=True)
    with st.form("login"):
        u, p = st.text_input("Identifiant"), st.text_input("Mot de passe", type="password")
        if st.form_submit_button("ENTRER"):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.authenticated, st.session_state.user_key = True, u
                st.rerun()
    st.stop()

# Changement de couleur de fond post-auth
st.markdown('<script>document.body.setAttribute("data-authenticated", "true");</script>', unsafe_allow_html=True)

# --- 4. PARAMÈTRES (Sidebar discret) ---
with st.sidebar:
    st.markdown("### ⚙️ Paramètres")
    # Option pour changer la journée de solidarité
    new_sol_date = st.date_input("Journée de Solidarité (Travaillée)", st.session_state.solidarity_date)
    if new_sol_date != st.session_state.solidarity_date:
        st.session_state.solidarity_date = new_sol_date
        st.rerun()
    st.write("---")
    if st.button("Se déconnecter"):
        st.session_state.authenticated = False
        st.rerun()

# --- 5. DATA & CALCULS ---
curr_user = st.session_state.user_key
h_data = supabase.table("heures").select("*").eq("user", curr_user).execute().data
c_data = supabase.table("conges").select("*").eq("user", curr_user).execute().data
u_a = pd.DataFrame(h_data) if h_data else pd.DataFrame(columns=['id', 'date', 'val'])
u_c = pd.DataFrame(c_data) if c_data else pd.DataFrame(columns=['id', 'date', 'type', 'group_id'])

# Utilisation de la date de solidarité stockée en session
du = calculate_metrics(u_c.copy(), st.session_state.solidarity_date)
h_sup_total = u_a['val'].astype(float).sum() if not u_a.empty else 0
delta = USERS[curr_user]["base_sup"] + h_sup_total
fait = du + delta

# --- 6. DASHBOARD ---
st.markdown(f"<p style='text-align:center; color:#9BA1B0; margin-bottom:0;'>Bonjour,</p><h2 style='text-align:center; margin-top:0;'>{curr_user}</h2>", unsafe_allow_html=True)

# Progression Annuelle épurée (à gauche)
st.markdown(f"<p style='text-align:center; margin-bottom:5px;'><small>Fait : <b>{int(fait)}</b> / 1652h</small></p>", unsafe_allow_html=True)
st.progress(min(max(fait / 1652.0, 0.0), 1.0))

# Carte Balance
status_color = "pos" if delta >= 0 else "neg"
st.markdown(f"""
    <div class="glass-card">
        <small class="sub-text">BALANCE HEURES SUP.</small>
        <div class="balance-val {status_color}">{to_hm(delta)}</div>
    </div>
""", unsafe_allow_html=True)

# Dû / Fait
c1, c2 = st.columns(2)
c1.markdown(f"<p style='text-align:left;'><small class='sub-text'>DÛ :</small> <b>{int(du)}h</b></p>", unsafe_allow_html=True)
c2.markdown(f"<p style='text-align:right;'><small class='sub-text'>FAIT :</small> <b>{to_hm(fait).replace('+', '')}</b></p>", unsafe_allow_html=True)

st.write("---")

# --- 7. JOURS FÉRIÉS ÉPURÉS (Look Badges) ---
st.markdown("#### 📅 Prochains Jours Fériés (2 semaines)")
fr_h = get_fr_holidays([datetime.now().year])
future_h = []
# On filtre sur les 14 prochains jours
for d_h, name in sorted(fr_h.items()):
    if date.today() <= d_h <= (date.today() + timedelta(days=14)):
        future_h.append(f'<span class="holiday-badge">{d_h.strftime("%d/%m")} : {name}</span>')

if future_h:
    # Affichage des badges épurés sur une ligne
    st.markdown(f'<div>{" ".join(future_h)}</div>', unsafe_allow_html=True)
else:
    st.info("Aucun jour férié dans les 2 prochaines semaines.")

st.write("")

# --- 8. ONGLETS DE SAISIE ---
t1, t2 = st.tabs(["⚡ SAISIE HEURES", "🌴 SAISIE CONGÉS"])

# ... (Le reste du code pour les onglets est identique à la v3.0) ...
