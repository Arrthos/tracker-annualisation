import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import calendar
import holidays
import uuid
from supabase import create_client, Client

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: space-between !important;
        margin-bottom: -15px !important;
    }
    .stButton > button {
        padding: 4px 12px !important;
        margin-top: 0px !important;
    }
    .cal-dashboard {
        background: rgba(255,255,255,0.03);
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 20px;
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

# --- 2. CALCULS ---
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
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date']).dt.date
        conges_map = df_conges.dropna(subset=['dt_temp']).set_index('dt_temp')['type'].to_dict()
        df_dates['conge_val'] = df_dates['date'].dt.date.map(conges_map).fillna(0)
        df_dates['h_theo'] *= (1 - df_dates['conge_val'])
    return df_dates['h_theo'].sum()

# --- 3. AUTHENTIFICATION ---
USERS = {"Julien": {"password": "%Gfpass115", "base_sup": 20.5}}

if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Connexion")
    with st.form("login"):
        u = st.text_input("Identifiant")
        p = st.text_input("Pass", type="password")
        if st.form_submit_button("Entrer", use_container_width=True):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.authenticated, st.session_state.user_key = True, u
                st.rerun()
    st.stop()

# --- 4. DATA ---
curr_user = st.session_state.user_key
h_res = supabase.table("heures").select("*").eq("user", curr_user).execute()
c_res = supabase.table("conges").select("*").eq("user", curr_user).execute()
u_a = pd.DataFrame(h_res.data) if h_res.data else pd.DataFrame(columns=['id', 'user', 'date', 'val'])
u_c = pd.DataFrame(c_res.data) if c_res.data else pd.DataFrame(columns=['id', 'user', 'date', 'type', 'group_id'])

# --- 5. DASHBOARD ---
sol_date = date(2026, 6, 1)
my_theo = calculate_due_fast(u_c.copy(), sol_date)
val_ajust = u_a['val'].astype(float).sum() if not u_a.empty else 0
my_delta = USERS[curr_user]["base_sup"] + val_ajust
fait = my_theo + my_delta

st.title(f"Hello {curr_user}")
st.progress(min(max(fait / 1652.0, 0.0), 1.0))
color_delta = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f'<h1 style="text-align:center; color:{color_delta}; font-size:4em;">{to_hm(my_delta)}</h1>', unsafe_allow_html=True)

# Agenda simplifié
today = datetime.now().date()
posees_dates = pd.to_datetime(u_c['date']).dt.date.tolist() if not u_c.empty else []
st.markdown("<div class='cal-dashboard'><b>📅 Prochainement :</b><br>" + 
            (", ".join([d.strftime('%d/%m') for d in sorted([d for d in posees_dates if d >= today])[:5]]) or "Rien de prévu") + 
            "</div>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with tab1:
    with st.expander("➕ Ajouter des heures"):
        with st.form("h_f", clear_on_submit=True):
            typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
            dat = st.date_input("Date", value=date.today())
            c1, c2 = st.columns(2)
            hv, mv = c1.number_input("H", 0, 12, 0), c2.number_input("M", 0, 59, 0)
            if st.form_submit_button("Valider"):
                val = (hv + mv/60) * (-1 if "Moins" in typ else 1)
                supabase.table("heures").insert({"user": curr_user, "date": str(dat), "val": val}).execute()
                st.rerun()
    
    for _, row in u_a.iloc[::-1].iterrows():
        col1, col2 = st.columns([0.8, 0.2])
        col1.write(f"**{pd.to_datetime(row['date']).strftime('%d/%m/%Y')}** : `{to_hm(row['val'])}`")
        if col2.button("🗑️", key=f"h_{row['id']}"):
            supabase.table("heures").delete().eq("id", row['id']).execute()
            st.rerun()

with tab2:
    mode = st.radio("Saisie", ["Jour unique", "Période"], horizontal=True)
    with st.container(border=True):
        if mode == "Jour unique":
            sel_d = st.date_input("Jour", value=date.today())
            is_h = st.checkbox("Demi-journée")
            if st.button("Enregistrer Jour", use_container_width=True, type="primary"):
                if sel_d.weekday() < 5:
                    supabase.table("conges").insert({"user": curr_user, "date": str(sel_d), "type": 0.5 if is_h else 1.0, "group_id": str(uuid.uuid4())}).execute()
                    st.rerun()
        else:
            sel_r = st.date_input("Période", value=[date.today(), date.today() + timedelta(days=2)])
            if st.button("Enregistrer Période", use_container_width=True, type="primary"):
                if isinstance(sel_r, list) and len(sel_r) == 2:
                    g_id = str(uuid.uuid4())
                    dr = pd.date_range(sel_r[0], sel_r[1], freq='D').date
                    rows = [{"user": curr_user, "date": str(d), "type": 1.0, "group_id": g_id} for d in dr if d.weekday() < 5]
                    if rows: supabase.table("conges").insert(rows).execute(); st.rerun()

    st.subheader("Historique")
    if not u_c.empty:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        for gid, data in u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False):
            c1, c2 = st.columns([0.8, 0.2])
            s, e = data['dt'].min().strftime("%d/%m/%Y"), data['dt'].max().strftime("%d/%m/%Y")
            lbl = f"Du {s} au {e}" if len(data) > 1 else f"Le {s}" + (" (0.5j)" if data.iloc[0]['type'] == 0.5 else "")
            c1.write(f"🌴 {lbl}")
            if c2.button("🗑️", key=f"g_{gid}"):
                supabase.table("conges").delete().eq("group_id", gid).execute()
                st.rerun()
