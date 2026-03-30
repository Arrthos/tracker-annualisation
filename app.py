import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import holidays
import uuid
from supabase import create_client

# --- CONFIG & CSS ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

st.markdown("""
    <style>
    /* Optimisation Mobile */
    .stButton > button { width: 100% !important; border-radius: 10px !important; height: 3em !important; }
    div[data-testid="stHorizontalBlock"] { align-items: center !important; margin-bottom: -10px !important; }
    .status-box { background: rgba(255,255,255,0.05); padding: 15px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 20px; }
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

# --- AUTH ---
USERS = {"Julien": {"password": "%Gfpass115", "base_sup": 20.5}}
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

# --- DATA ---
curr_user = st.session_state.user_key
h_res = supabase.table("heures").select("*").eq("user", curr_user).execute()
c_res = supabase.table("conges").select("*").eq("user", curr_user).execute()
u_a = pd.DataFrame(h_res.data) if h_res.data else pd.DataFrame(columns=['id', 'date', 'val'])
u_c = pd.DataFrame(c_res.data) if c_res.data else pd.DataFrame(columns=['id', 'date', 'type', 'group_id'])

# --- DASHBOARD ---
st.title(f"Hello {curr_user}")
val_ajust = u_a['val'].astype(float).sum() if not u_a.empty else 0
my_delta = USERS[curr_user]["base_sup"] + val_ajust
color = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f'<h1 style="text-align:center; color:{color}; font-size:4em; margin-top:-20px;">{to_hm(my_delta)}</h1>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with tab1:
    with st.expander("➕ Enregistrer des heures"):
        with st.form("h_f", clear_on_submit=True):
            typ = st.radio("Sens", ["Plus (+)", "Moins (-)"], horizontal=True)
            d = st.date_input("Date", date.today())
            c1, c2 = st.columns(2)
            hv = c1.number_input("Heures", 0, 12, 0)
            mv = c2.number_input("Min", 0, 59, 0)
            if st.form_submit_button("Valider"):
                val = (hv + mv/60) * (-1 if "Moins" in typ else 1)
                supabase.table("heures").insert({"user": curr_user, "date": str(d), "val": val}).execute()
                st.rerun()
    
    for _, row in u_a.iloc[::-1].iterrows():
        c1, c2 = st.columns([0.8, 0.2])
        c1.write(f"**{pd.to_datetime(row['date']).strftime('%d/%m/%Y')}** : `{to_hm(row['val'])}`")
        if c2.button("🗑️", key=f"h_{row['id']}"):
            supabase.table("heures").delete().eq("id", row['id']).execute(); st.rerun()

with tab2:
    # --- SAISIE ERGONOMIQUE ---
    mode = st.toggle("Passer en mode Période (plusieurs jours)", value=False)
    
    with st.container(border=True):
        if not mode:
            # MODE JOUR UNIQUE
            st.subheader("📍 Jour unique")
            d_unique = st.date_input("Sélectionner le jour", value=date.today())
            d_type = st.radio("Durée", ["Journée entière", "Demi-journée"], horizontal=True)
            if st.button("Enregistrer le jour", type="primary"):
                if d_unique.weekday() < 5:
                    supabase.table("conges").insert({
                        "user": curr_user, "date": str(d_unique), 
                        "type": 0.5 if "Demi" in d_type else 1.0, 
                        "group_id": str(uuid.uuid4())
                    }).execute()
                    st.rerun()
                else: st.error("C'est un week-end !")
        else:
            # MODE PÉRIODE
            st.subheader("📅 Période")
            st.caption("Sélectionnez le premier et le dernier jour")
            range_d = st.date_input("Dates de début et fin", value=[date.today(), date.today()])
            if st.button("Enregistrer la période", type="primary"):
                if isinstance(range_d, list) and len(range_d) == 2:
                    g_id = str(uuid.uuid4())
                    dr = pd.date_range(range_d[0], range_d[1], freq='D').date
                    rows = [{"user": curr_user, "date": str(d), "type": 1.0, "group_id": g_id} for d in dr if d.weekday() < 5]
                    if rows: supabase.table("conges").insert(rows).execute(); st.rerun()
                else: st.warning("Sélectionnez bien deux dates (début et fin).")

    st.subheader("Historique")
    if not u_c.empty:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        groups = u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False)
        for gid, data in groups:
            c1, c2 = st.columns([0.8, 0.2])
            start, end = data['dt'].min(), data['dt'].max()
            lbl = f"Du {start.strftime('%d/%m/%Y')} au {end.strftime('%d/%m/%Y')}" if len(data) > 1 else f"Le {start.strftime('%d/%m/%Y')}"
            if len(data) == 1 and data.iloc[0]['type'] == 0.5: lbl += " (Demi)"
            c1.write(f"🌴 {lbl}")
            if c2.button("🗑️", key=f"g_{gid}"):
                supabase.table("conges").delete().eq("group_id", gid).execute(); st.rerun()
