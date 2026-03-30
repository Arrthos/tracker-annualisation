import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import holidays
import uuid
from supabase import create_client

# --- 1. CONFIG & DESIGN PREMIUM (GLASSMORPHISM) ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

st.markdown("""
    <style>
    /* Fond profond et épuré */
    .stApp { background-color: #0E1117; }
    header {visibility: hidden;}
    
    /* Design des cartes Glassmorphism vaporeuses */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 15px;
        border-radius: 15px;
        text-align: center;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
    }

    /* Style du chiffre clé (Jaune Pastel) */
    .glass-metric {
        font-size: 5rem;
        font-weight: 800;
        letter-spacing: -2px;
        margin: 10px 0;
        color: #F1C40F;
    }
    .balance-neg { color: #da3633; }

    /* Texte descriptif reposant */
    .stMarkdown, p, small { color: #EAEAEA; }

    /* Progress Bar fine Violette */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #7D2AE8, #9B59B6);
        height: 8px;
    }

    /* Boutons et Inputs épurés */
    .stButton>button {
        border-radius: 10px !important;
        background-color: transparent !important;
        border: 2px solid #F1C40F !important;
        color: #F1C40F !important;
        font-weight: bold !important;
        transition: 0.3s ease !important;
    }
    .stButton>button:hover {
        background-color: #F1C40F !important;
        color: #0E1117 !important;
    }
    
    /* Onglets épurés */
    .stTabs [data-baseweb="tab-list"] { gap: 15px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        background-color: transparent !important;
        border: none !important;
        color: #888 !important;
    }
    .stTabs [aria-selected="true"] { color: #EAEAEA !important; border-bottom: 2px solid #7D2AE8 !important; }
    </style>
""", unsafe_allow_html=True)

# --- LOGIQUE DE CALCUL THÉORIQUE ---
@st.cache_resource
def get_supabase(): return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
supabase = get_supabase()

@st.cache_data(ttl=3600)
def get_fr_holidays(years): return holidays.France(years=years)

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

# --- AUTHENTIFICATION ---
# Julien est configuré ici
USERS = {"Julien": {"password": "%Gfpass115", "base_sup": 20.5}}
if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align:center;'>Work Tracker Pro</h2>", unsafe_allow_html=True)
    with st.form("login"):
        u, p = st.text_input("Identifiant"), st.text_input("Mot de passe", type="password")
        if st.form_submit_button("ENTRER"):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.authenticated, st.session_state.user_key = True, u
                st.rerun()
    st.stop()

# --- CHARGEMENT DONNÉES ---
curr_user = st.session_state.user_key
h_data = supabase.table("heures").select("*").eq("user", curr_user).execute().data
c_data = supabase.table("conges").select("*").eq("user", curr_user).execute().data
u_a = pd.DataFrame(h_data) if h_data else pd.DataFrame(columns=['id', 'date', 'val'])
u_c = pd.DataFrame(c_data) if c_data else pd.DataFrame(columns=['id', 'date', 'type', 'group_id'])

# --- DASHBOARD VISUEL PREMIUM ---
sol_date = date(2026, 6, 1)
du = calculate_metrics(u_c.copy(), sol_date)
delta = USERS[curr_user]["base_sup"] + (u_a['val'].astype(float).sum() if not u_a.empty else 0)
fait = du + delta

st.markdown(f"<p style='text-align:center; color:#888; margin-bottom:-10px;'>Bonjour,</p><h2 style='text-align:center;'>{curr_user}</h2>", unsafe_allow_html=True)

# Grande carte de Balance
neg_class = "balance-neg" if delta < 0 else ""
st.markdown(f"""
    <div class="glass-card">
        <p style="color:#888; font-size:0.9rem; margin:0;">BALANCE HEURES SUP.</p>
        <div class="glass-metric {neg_class}">{to_hm(delta)}</div>
    </div>
""", unsafe_allow_html=True)

# Barre de progression épurée
col_a, col_b = st.columns([1, 1])
col_a.markdown(f"<small style='color:#888;'>DÛ : **{int(du)}h**</small>", unsafe_allow_html=True)
col_b.markdown(f"<p style='text-align:right;'><small style='color:#888;'>FAIT : **{to_hm(fait).replace('+','')}**</small></p>", unsafe_allow_html=True)
st.progress(min(max(fait / 1652.0, 0.0), 1.0))

st.write("") # Espacement

# Agenda en mode horizontal (Timeline)
st.markdown("<small style='color:#666; font-weight:bold; letter-spacing:1px;'>AGENDA</small>", unsafe_allow_html=True)
today = date.today()
fr_h = get_fr_holidays([today.year])
posees = pd.to_datetime(u_c['date']).dt.date.tolist() if not u_c.empty else []
agenda_cols = st.columns(5)
for i in range(5):
    d = today + timedelta(days=i)
    bg = "rgba(255,255,255,0.05)"
    icon = ""
    if d in fr_h: bg = "rgba(241, 196, 15, 0.15)"; icon="🎉"
    if d in posees: bg = "rgba(125, 42, 232, 0.15)"; icon="🌴"
    agenda_cols[i].markdown(f"<div style='background:{bg}; padding:10px; border-radius:10px; text-align:center;'><small style='color:#888;'>{d.strftime('%a')}</small><br><b>{d.strftime('%d/%m')}</b><br>{icon}</div>", unsafe_allow_html=True)

st.write("")

# --- TABS ---
tab1, tab2 = st.tabs(["⚡ HEURES", "🌴 CONGÉS"])

with tab1:
    with st.expander("Saisir des heures supplémentaires"):
        with st.form("h_f", clear_on_submit=True):
            typ = st.radio("Sens", ["Plus (+)", "Moins (-)"], horizontal=True)
            d = st.date_input("Date", today)
            c_h, c_m = st.columns(2)
            hv, mv = c_h.number_input("H", 0, 12, 0), c_m.number_input("M", 0, 59, 0)
            if st.form_submit_button("VALIDER"):
                supabase.table("heures").insert({"user": curr_user, "date": str(d), "val": (hv + mv/60) * (-1 if "Moins" in typ else 1)}).execute()
                st.rerun()
    
    # Historique Heures épuré
    for _, row in u_a.iloc[::-1].iterrows():
        cx, cy = st.columns([0.8, 0.2])
        cx.write(f"📅 {pd.to_datetime(row['date']).strftime('%d/%m')} : &nbsp; <b>{to_hm(row['val'])}</b>", unsafe_allow_html=True)
        if cy.button("🗑️", key=f"h_{row['id']}"):
            supabase.table("heures").delete().eq("id", row['id']).execute(); st.rerun()

with tab2:
    is_p = st.toggle("Activer mode Période", value=False)
    with st.container(border=True):
        if not is_p:
            d_u = st.date_input("Date du congé", today)
            half = st.checkbox("Demi-journée")
            if st.button("CONFIRMER LE JOUR", type="primary"):
                if d_u.weekday() < 5:
                    supabase.table("conges").insert({"user": curr_user, "date": str(d_u), "type": 0.5 if half else 1.0, "group_id": str(uuid.uuid4())}).execute()
                    st.rerun()
        else:
            c1, c2 = st.columns(2)
            d_s, d_e = c1.date_input("Du", today), c2.date_input("Au", today + timedelta(days=1))
            if st.button("CONFIRMER LA PÉRIODE", type="primary"):
                if d_s <= d_e:
                    g_id = str(uuid.uuid4())
                    days = pd.date_range(d_s, d_e, freq='D').date
                    rows = [{"user": curr_user, "date": str(day), "type": 1.0, "group_id": g_id} for day in days if day.weekday() < 5]
                    if rows: supabase.table("conges").insert(rows).execute(); st.rerun()

    # Historique Congés épuré
    if not u_c.empty:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        for gid, data in u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False):
            c1, c2 = st.columns([0.8, 0.2])
            s, e = data['dt'].min(), data['dt'].max()
            lbl = f"{s.strftime('%d/%m')} → {e.strftime('%d/%m')}" if len(data) > 1 else f"{s.strftime('%d/%m')}"
            if len(data) == 1 and data.iloc[0]['type'] == 0.5: lbl += " (1/2)"
            c1.write(f"🌴 {lbl}")
            if c2.button("🗑️", key=f"g_{gid}"):
                supabase.table("conges").delete().eq("group_id", gid).execute(); st.rerun()
