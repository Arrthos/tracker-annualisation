import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import calendar
import holidays
import uuid
from supabase import create_client, Client

# --- 1. CONFIGURATION & CSS DE FORCE ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

st.markdown("""
    <style>
    /* Force l'alignement de la corbeille sur la même ligne */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        flex-wrap: nowrap !important;
    }
    .stButton > button {
        padding: 2px 10px !important;
        margin-top: 0px !important;
    }
    /* Style Table Calendrier pour éviter le décalage mobile */
    .cal-table {
        width: 100%;
        border-collapse: collapse;
        text-align: center;
        table-layout: fixed;
    }
    .cal-table td, .cal-table th {
        padding: 10px 2px;
        font-size: 0.85em;
    }
    .day-box {
        background: rgba(255,255,255,0.05);
        border-radius: 6px;
        padding: 8px 0;
    }
    .day-off { background: #007bff !important; color: white; }
    .day-today { border: 2px solid #238636 !important; }
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
USERS = {"Julien": {"password": "%Gfpass115", "base_sup": 20.5}} # Modifie ici
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

# --- 4. CHARGEMENT DONNÉES ---
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

st.markdown(f"<h1 style='text-align: center;'>Hello {curr_user}</h1>", unsafe_allow_html=True)
st.progress(min(max(fait / 1652.0, 0.0), 1.0))
balance_str = to_hm(my_delta)
color_delta = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f'<h1 style="text-align:center; color:{color_delta}; font-size:4em;">{balance_str}</h1>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with tab1:
    with st.expander("➕ Ajouter des heures"):
        with st.form("h_form", clear_on_submit=True):
            typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
            dat = st.date_input("Date", value=date.today())
            c1, c2 = st.columns(2)
            h_v, m_v = c1.number_input("H", 0, 12, 0), c2.number_input("M", 0, 59, 0)
            if st.form_submit_button("Valider"):
                val = (h_v + m_v/60) * (-1 if "Moins" in typ else 1)
                supabase.table("heures").insert({"user": curr_user, "date": str(dat), "val": val}).execute()
                st.rerun()
    
    st.subheader("Historique")
    for _, row in u_a.iloc[::-1].iterrows():
        c1, c2 = st.columns([0.85, 0.15])
        dt_str = pd.to_datetime(row['date']).strftime("%d/%m/%Y")
        c1.write(f"**{dt_str}** : `{to_hm(row['val'])}`")
        if c2.button("🗑️", key=f"h_{row['id']}"):
            supabase.table("heures").delete().eq("id", row['id']).execute()
            st.rerun()

with tab2:
    # --- CALENDRIER TABLE HTML (INCASSABLE) ---
    today_dt = datetime.now()
    posees = pd.to_datetime(u_c['date']).dt.day.tolist() if not u_c.empty else []
    
    cal_html = f"<b>{calendar.month_name[today_dt.month]} {today_dt.year}</b>"
    cal_html += "<table class='cal-table'><tr>"
    for d in ["L","M","M","J","V","S","D"]: cal_html += f"<th>{d}</th>"
    cal_html += "</tr>"
    
    for week in calendar.monthcalendar(today_dt.year, today_dt.month):
        cal_html += "<tr>"
        for day in week:
            if day == 0: cal_html += "<td></td>"
            else:
                cls = "day-box"
                if day in posees: cls += " day-off"
                if day == today_dt.day: cls += " day-today"
                cal_html += f"<td><div class='{cls}'>{day}</div></td>"
        cal_html += "</tr>"
    st.markdown(cal_html + "</table><br>", unsafe_allow_html=True)

    with st.expander("➕ Poser une période"):
        with st.form("c_form", clear_on_submit=True):
            sel = st.date_input("Dates", value=[date.today()])
            if st.form_submit_button("Confirmer"):
                g_id = str(uuid.uuid4())
                if isinstance(sel, (list, tuple)) and len(sel) > 1:
                    dr = pd.date_range(sel[0], sel[1], freq='D').date
                else: dr = [sel[0] if isinstance(sel, (list, tuple)) else sel]
                rows = [{"user": curr_user, "date": str(d), "type": 1.0, "group_id": g_id} for d in dr if d.weekday() < 5]
                if rows:
                    supabase.table("conges").insert(rows).execute()
                    st.rerun()

    st.subheader("Liste des congés")
    if not u_c.empty:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        groups = u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False)
        for gid, data in groups:
            c1, c2 = st.columns([0.85, 0.15])
            s, e = data['dt'].min().strftime("%d/%m/%Y"), data['dt'].max().strftime("%d/%m/%Y")
            txt = f"Du {s} au {e}" if len(data) > 1 else f"Le {s}"
            c1.write(f"🌴 {txt}")
            if c2.button("🗑️", key=f"g_{gid}"):
                supabase.table("conges").delete().eq("group_id", gid).execute()
                st.rerun()
