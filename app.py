import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import holidays
import uuid
from supabase import create_client

# --- 1. CONFIG & CSS ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

st.markdown("""
    <style>
    .stButton > button { width: 100% !important; border-radius: 10px !important; }
    .status-box { background: rgba(255,255,255,0.05); padding: 15px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 20px; }
    .ferie-tag { color: #f39c12; font-weight: bold; }
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
    h, m = int(abs_h), int(round((abs_h - int(abs_h)) * 60))
    if m == 60: h += 1; m = 0
    sign = "-" if decimal_hours < 0 else "+" if decimal_hours > 0 else ""
    return f"{sign}{h}h{m:02d}"

# --- 2. CALCULS (DÛ / FAIT) ---
def calculate_metrics(df_conges, solidarity_day):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    
    dr = pd.date_range(start=start, end=now, freq='D')
    df_dates = pd.DataFrame({'date': dr})
    df_dates['weekday'] = df_dates['date'].dt.weekday
    df_dates = df_dates[df_dates['weekday'] < 5].copy()
    
    # Heures théoriques (L-M: 7.5h, Mer-Ven: 7h)
    df_dates['h_theo'] = np.where(df_dates['weekday'] <= 1, 7.5, 7.0)
    
    # Jours fériés
    fr_h = get_fr_holidays([sy, sy+1])
    df_dates['is_holiday'] = df_dates['date'].dt.date.apply(lambda x: x in fr_h and x != solidarity_day)
    df_dates.loc[df_dates['is_holiday'], 'h_theo'] = 0
    
    # Déduction des congés
    if not df_conges.empty:
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date']).dt.date
        conges_map = df_conges.groupby('dt_temp')['type'].sum().to_dict()
        df_dates['conge_val'] = df_dates['date'].dt.date.map(conges_map).fillna(0)
        df_dates['h_theo'] = np.maximum(0, df_dates['h_theo'] * (1 - df_dates['conge_val']))
        
    due = df_dates['h_theo'].sum()
    return due

# --- 3. AUTH ---
USERS = {"Julien": {"password": "123", "base_sup": 20.5}}
if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.form("login"):
        u = st.text_input("Utilisateur")
        p = st.text_input("Mots de passe", type="password")
        if st.form_submit_button("Connexion"):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.authenticated, st.session_state.user_key = True, u
                st.rerun()
    st.stop()

# --- 4. DATA ---
curr_user = st.session_state.user_key
h_res = supabase.table("heures").select("*").eq("user", curr_user).execute()
c_res = supabase.table("conges").select("*").eq("user", curr_user).execute()
u_a = pd.DataFrame(h_res.data) if h_res.data else pd.DataFrame(columns=['id', 'date', 'val', 'user'])
u_c = pd.DataFrame(c_res.data) if c_res.data else pd.DataFrame(columns=['id', 'date', 'type', 'group_id', 'user'])

# --- 5. DASHBOARD ---
sol_date = date(2026, 6, 1)
du = calculate_metrics(u_c.copy(), sol_date)
val_ajust = u_a['val'].astype(float).sum() if not u_a.empty else 0
delta = USERS[curr_user]["base_sup"] + val_ajust
fait = du + delta

st.title(f"Hello {curr_user}")

# Affichage Dû et Fait
c1, c2 = st.columns(2)
c1.metric("Dû (Théorique)", f"{int(du)}h")
c2.metric("Fait (Réel)", f"{to_hm(fait).replace('+','')}")

st.progress(min(max(fait / 1652.0, 0.0), 1.0))

color = "#238636" if delta >= 0 else "#da3633"
st.markdown(f'<h1 style="text-align:center; color:{color}; font-size:4em; margin-top:-10px;">{to_hm(delta)}</h1>', unsafe_allow_html=True)

# Agenda
st.markdown("<div class='status-box'><b>📅 Agenda Prochainement</b>", unsafe_allow_html=True)
today = datetime.now().date()
fr_h = get_fr_holidays([today.year])
posees = pd.to_datetime(u_c['date']).dt.date.tolist() if not u_c.empty else []
items = []
for i in range(15):
    d = today + timedelta(days=i)
    if d in fr_h: items.append(f"• {d.strftime('%d/%m')} : <span class='ferie-tag'>{fr_h.get(d)}</span>")
    if d in posees: items.append(f"• {d.strftime('%d/%m')} : 🌴 Congé")
st.markdown("<br>".join(items[:5]) if items else "Rien de prévu", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# --- 6. ONGLETS ---
tab1, tab2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with tab1:
    with st.expander("➕ Enregistrer des heures"):
        with st.form("h_f", clear_on_submit=True):
            typ = st.radio("Sens", ["Plus (+)", "Moins (-)"], horizontal=True)
            d = st.date_input("Date", date.today())
            cols = st.columns(2)
            hv = cols[0].number_input("Heures", 0, 12, 0)
            mv = cols[1].number_input("Min", 0, 59, 0)
            if st.form_submit_button("Valider"):
                v = (hv + mv/60) * (-1 if "Moins" in typ else 1)
                supabase.table("heures").insert({"user": curr_user, "date": str(d), "val": v}).execute()
                st.rerun()
    
    for _, row in u_a.iloc[::-1].iterrows():
        cx, cy = st.columns([0.8, 0.2])
        cx.write(f"**{pd.to_datetime(row['date']).strftime('%d/%m/%Y')}** : `{to_hm(row['val'])}`")
        if cy.button("🗑️", key=f"h_{row['id']}"):
            supabase.table("heures").delete().eq("id", row['id']).execute(); st.rerun()

with tab2:
    is_period = st.toggle("Mode Période", value=False)
    with st.container(border=True):
        if not is_period:
            st.subheader("📍 Jour unique")
            d_u = st.date_input("Choisir le jour", date.today(), key="single_d")
            half = st.checkbox("Demi-journée")
            if st.button("Enregistrer Jour", type="primary"):
                if d_u.weekday() < 5:
                    supabase.table("conges").insert({
                        "user": curr_user, "date": str(d_u), 
                        "type": 0.5 if half else 1.0, 
                        "group_id": str(uuid.uuid4())
                    }).execute()
                    st.rerun()
        else:
            st.subheader("📅 Période")
            # Correction ici pour l'enregistrement
            d_range = st.date_input("Début et fin", [date.today(), date.today()], key="range_d")
            if st.button("Enregistrer Période", type="primary"):
                if isinstance(d_range, list) and len(d_range) == 2:
                    g_id = str(uuid.uuid4())
                    all_days = pd.date_range(d_range[0], d_range[1], freq='D').date
                    rows = []
                    for day in all_days:
                        if day.weekday() < 5:
                            rows.append({"user": curr_user, "date": str(day), "type": 1.0, "group_id": g_id})
                    if rows:
                        supabase.table("conges").insert(rows).execute()
                        st.rerun()

    st.subheader("Historique")
    if not u_c.empty:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        for gid, data in u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False):
            c1, c2 = st.columns([0.8, 0.2])
            start, end = data['dt'].min(), data['dt'].max()
            lbl = f"Du {start.strftime('%d/%m/%Y')} au {end.strftime('%d/%m/%Y')}" if len(data) > 1 else f"Le {start.strftime('%d/%m/%Y')}"
            if len(data) == 1 and data.iloc[0]['type'] == 0.5: lbl += " (Demi)"
            c1.write(f"🌴 {lbl}")
            if c2.button("🗑️", key=f"g_{gid}"):
                supabase.table("conges").delete().eq("group_id", gid).execute(); st.rerun()
