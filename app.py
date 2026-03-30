import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import holidays
import uuid
from supabase import create_client

# --- 1. CONFIG & DESIGN SOFT PRO (SANS BANANES) ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

# CSS Custom pour le look épuré et professionnel (Noir & Or doux)
st.markdown("""
    <style>
    /* Fond profond Noir Bleuté */
    .stApp { background-color: #0E1117; color: #EAEAEA; }
    header {visibility: hidden;}
    
    /* Design des cartes Glassmorphism (Vaporeuses) */
    .metric-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 25px;
        border-radius: 20px;
        text-align: center;
        backdrop-filter: blur(15px);
        margin-bottom: 25px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    }

    /* Style du chiffre clé (Or Doux) */
    .balance-val {
        font-size: 5.5rem;
        font-weight: 800;
        letter-spacing: -3px;
        margin: 10px 0;
        color: #F1C40F; /* Or Doux, non brillant */
    }
    .balance-neg {
        color: #E74C3C; /* Rouge doux pour le négatif */
    }

    /* Texte descriptif reposant (Blanc cassé) */
    .stMarkdown, p, small {
        color: #EAEAEA !important;
    }

    /* Progress Bar fine Bleu-Gris */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #34495E, #7D2AE8);
        height: 6px;
    }

    /* Boutons épurés (Jaune doux vers Violet foncé) */
    .stButton>button {
        border-radius: 12px !important;
        border: none !important;
        background: linear-gradient(135deg, #F1C40F 0%, #7D2AE8 100%) !important;
        color: #0E1117 !important; /* Texte sombre sur bouton clair */
        font-weight: 700 !important;
        letter-spacing: 1px;
        transition: 0.3s ease !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(241, 196, 15, 0.3);
    }
    
    /* Onglets épurés et sombres */
    .stTabs [data-baseweb="tab-list"] { gap: 20px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        background-color: transparent !important;
        border: none !important;
        color: #888 !important;
    }
    .stTabs [aria-selected="true"] { 
        color: #EAEAEA !important; 
        border-bottom: 2px solid #F1C40F !important; 
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIQUE (Identique et robuste) ---
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

# --- 3. AUTHENTIFICATION ---
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

# --- 4. CHARGEMENT DONNÉES ---
curr_user = st.session_state.user_key
h_data = supabase.table("heures").select("*").eq("user", curr_user).execute().data
c_data = supabase.table("conges").select("*").eq("user", curr_user).execute().data
u_a = pd.DataFrame(h_data) if h_data else pd.DataFrame(columns=['id', 'date', 'val'])
u_c = pd.DataFrame(c_data) if c_data else pd.DataFrame(columns=['id', 'date', 'type', 'group_id'])

# --- 5. DASHBOARD VISUEL PURE ---
sol_date = date(2026, 6, 1)
du = calculate_metrics(u_c.copy(), sol_date)
delta = USERS[curr_user]["base_sup"] + (u_a['val'].astype(float).sum() if not u_a.empty else 0)
fait = du + delta

# Bonjour Julien (texte adouci)
st.markdown(f"<p style='text-align:center; color:#888; margin-bottom:-10px;'>Bonjour,</p><h2 style='text-align:center; color:#EAEAEA;'>{curr_user}</h2>", unsafe_allow_html=True)

# Grande carte de Balance (Or Doux)
neg_class = "balance-neg" if delta < 0 else ""
st.markdown(f"""
    <div class="metric-card">
        <p style="color:#888; font-size:0.9rem; margin:0; letter-spacing:1px;">BALANCE HEURES SUPPLÉMENTAIRES</p>
        <div class="balance-val {neg_class}">{to_hm(delta)}</div>
    </div>
""", unsafe_allow_html=True)

# Barre de progression épurée
col_a, col_b = st.columns([1, 1])
col_a.markdown(f"<small style='color:#888;'>DÛ (Théorique) : **{int(du)}h**</small>", unsafe_allow_html=True)
col_b.markdown(f"<p style='text-align:right;'><small style='color:#888;'>FAIT (Réel) : **{to_hm(fait).replace('+','')}**</small></p>", unsafe_allow_html=True)
st.progress(min(max(fait / 1652.0, 0.0), 1.0))

st.write("") # Espacement

# Agenda en mode horizontal (épuré, sans icônes de fête)
st.markdown("<small style='color:#666; font-weight:bold; letter-spacing:1px;'>PROCHAINEMENT</small>", unsafe_allow_html=True)
today = date.today()
fr_h = get_fr_holidays([today.year])
posees = pd.to_datetime(u_c['date']).dt.date.tolist() if not u_c.empty else []
agenda_cols = st.columns(5)
for i in range(5):
    d = today + timedelta(days=i)
    bg = "rgba(255,255,255,0.03)" # Fond très discret par défaut
    
    if d in fr_h: 
        bg = "rgba(243, 156, 18, 0.15)" # Orange très doux pour Férié
    elif d in posees: 
        bg = "rgba(125, 42, 232, 0.15)" # Violet très doux pour Congé
        
    agenda_cols[i].markdown(f"""
        <div style='background:{bg}; padding:12px; border-radius:12px; text-align:center;'>
            <small style='color:#888;'>{d.strftime('%a').upper()}</small><br>
            <b style='color:#EAEAEA; font-size:1.1rem;'>{d.strftime('%d/%m')}</b>
        </div>
    """, unsafe_allow_html=True)

st.write("")

# --- TABS ---
tab1, tab2 = st.tabs(["⚡ SAISIE HEURES", "🌴 SAISIE CONGÉS"])

with tab1:
    with st.expander("Enregistrer des heures supplémentaires"):
        with st.form("h_f", clear_on_submit=True):
            typ = st.radio("Sens", ["Plus (+)", "Moins (-)"], horizontal=True)
            d = st.date_input("Date", today)
            c_h, c_m = st.columns(2)
            hv, mv = c_h.number_input("H", 0, 12, 0), c_m.number_input("M", 0, 59, 0)
            if st.form_submit_button("VALIDER L'ENTRÉE"):
                supabase.table("heures").insert({"user": curr_user, "date": str(d), "val": (hv + mv/60) * (-1 if "Moins" in typ else 1)}).execute()
                st.rerun()
    
    # Historique Heures épuré
    st.write("")
    st.markdown("<small style='color:#666; font-weight:bold;'>HISTORIQUE RÉCENT</small>", unsafe_allow_html=True)
    for _, row in u_a.iloc[::-1].iterrows():
        cx, cy = st.columns([0.85, 0.15])
        # Petit bloc arrondi discret pour chaque entrée
        cx.markdown(f"<div style='background:rgba(255,255,255,0.02); padding:10px; border-radius:10px; margin-bottom:5px; color:#EAEAEA;'>📅 {pd.to_datetime(row['date']).strftime('%d/%m')} &nbsp;&nbsp; <b>{to_hm(row['val'])}</b></div>", unsafe_allow_html=True)
        if cy.button("🗑️", key=f"h_{row['id']}"):
            supabase.table("heures").delete().eq("id", row['id']).execute(); st.rerun()

with tab2:
    is_p = st.toggle("Activer mode Période (plusieurs jours)", value=False)
    with st.container(border=True):
        if not is_p:
            st.subheader("📍 Jour unique")
            d_u = st.date_input("Date du congé", today)
            half = st.checkbox("Demi-journée (0.5j)")
            if st.button("CONFIRMER LE JOUR", type="primary"):
                if d_u.weekday() < 5:
                    supabase.table("conges").insert({"user": curr_user, "date": str(d_u), "type": 0.5 if half else 1.0, "group_id": str(uuid.uuid4())}).execute()
                    st.rerun()
                else:
                    st.error("Impossible de poser un congé le week-end.")
        else:
            st.subheader("📅 Période")
            c1, c2 = st.columns(2)
            d_s, d_e = c1.date_input("Du", today), c2.date_input("Au", today + timedelta(days=1))
            if st.button("CONFIRMER LA PÉRIODE", type="primary"):
                if d_s <= d_e:
                    g_id = str(uuid.uuid4())
                    days = pd.date_range(d_s, d_e, freq='D').date
                    rows = [{"user": curr_user, "date": str(day), "type": 1.0, "group_id": g_id} for day in days if day.weekday() < 5]
                    if rows: supabase.table("conges").insert(rows).execute(); st.rerun()
                else:
                    st.error("La date de fin doit être après la date de début.")

    # Historique Congés groupé épuré
    st.write("")
    st.markdown("<small style='color:#666; font-weight:bold;'>CONGÉS ENREGISTRÉS</small>", unsafe_allow_html=True)
    if not u_c.empty:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        for gid, data in u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False):
            c1, c2 = st.columns([0.85, 0.15])
            s, e = data['dt'].min(), data['dt'].max()
            lbl = f"{s.strftime('%d/%m')} → {e.strftime('%d/%m')}" if len(data) > 1 else f"{s.strftime('%d/%m')}"
            if len(data) == 1 and data.iloc[0]['type'] == 0.5: lbl += " (1/2 journée)"
            
            # Petit bloc arrondi avec fond violet très discret
            c1.markdown(f"<div style='background:rgba(125, 42, 232, 0.08); padding:10px; border-radius:10px; margin-bottom:5px; color:#EAEAEA;'>🌴 {lbl}</div>", unsafe_allow_html=True)
            if c2.button("🗑️", key=f"g_{gid}"):
                supabase.table("conges").delete().eq("group_id", gid).execute(); st.rerun()
    else:
        st.info("Aucun congé enregistré.")

# --- 7. DÉCONNEXION (Sidebar discret) ---
if st.sidebar.button("Se déconnecter", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()
