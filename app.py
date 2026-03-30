import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import calendar
import holidays
import uuid
from supabase import create_client, Client

# --- 1. CONFIGURATION & CSS ROBUSTE ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

st.markdown("""
    <style>
    /* Force l'alignement horizontal des historiques sur mobile */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: space-between !important;
        margin-bottom: -10px !important;
    }
    /* Style des boutons corbeille */
    .stButton > button {
        margin-top: 0px !important;
        padding: 2px 10px !important;
        background-color: rgba(255, 75, 75, 0.1);
        border: 1px solid rgba(255, 75, 75, 0.2);
    }
    /* Grille du calendrier personnalisée pour éviter les bugs d'affichage */
    .cal-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 5px;
        text-align: center;
        margin-top: 10px;
    }
    .cal-day-name { font-weight: bold; font-size: 0.7em; color: #888; padding-bottom: 5px; }
    .cal-day {
        padding: 10px 0;
        border-radius: 8px;
        font-size: 0.9em;
        background: rgba(255,255,255,0.05);
        color: white;
    }
    .cal-today { border: 2px solid #238636 !important; }
    .cal-off { background: #007bff !important; color: white !important; }
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
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.title("🔐 Connexion")
    with st.form("login"):
        u = st.text_input("Utilisateur")
        p = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Entrer", use_container_width=True):
            if u == "Julien" and p == "123": # Change ici si besoin
                st.session_state.authenticated, st.session_state.user_key = True, u
                st.rerun()
    st.stop()

# --- 4. CHARGEMENT DONNÉES ---
curr_user = st.session_state.user_key
h_res = supabase.table("heures").select("*").eq("user", curr_user).execute()
c_res = supabase.table("conges").select("*").eq("user", curr_user).execute()
u_a = pd.DataFrame(h_res.data) if h_res.data else pd.DataFrame(columns=['id', 'user', 'date', 'val'])
u_c = pd.DataFrame(c_res.data) if c_res.data else pd.DataFrame(columns=['id', 'user', 'date', 'type', 'group_id'])

# --- 5. CALCULS DASHBOARD ---
sol_date = date(2026, 6, 1)
my_theo = calculate_due_fast(u_c.copy(), sol_date)
val_ajust = u_a['val'].astype(float).sum() if not u_a.empty else 0
my_delta = 20.5 + val_ajust 
fait = my_theo + my_delta
objectif = 1652.0

# --- 6. INTERFACE ---
st.markdown(f"<h1 style='text-align: center; margin-bottom: 20px;'>Hello {curr_user}</h1>", unsafe_allow_html=True)

# Barre de progression
fait_str = to_hm(fait).replace("+", "")
st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: -5px;">
        <p style="margin: 0; font-weight: bold; color: white;">Progression annuelle</p>
        <p style="margin: 0; opacity: 0.8; color: white;"><b>{fait_str}</b> / {int(objectif)}h</p>
    </div>
""", unsafe_allow_html=True)
st.progress(min(max(fait / objectif, 0.0), 1.0))

# Balance
balance_str = to_hm(my_delta)
color_delta = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:15px; text-align:center; border:2px solid {color_delta}; margin: 15px 0 20px 0;">
        <p style="margin:0; opacity:0.6; font-size:0.8em; color:white;">BALANCE</p>
        <h1 style="color:{color_delta}; font-size:3.5em; margin:5px 0;">{balance_str}</h1>
    </div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with tab1:
    with st.expander("➕ Enregistrer des heures"):
        with st.form("h_f", clear_on_submit=True):
            typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
            d = st.date_input("Date", value=date.today())
            c1, c2 = st.columns(2)
            hv, mv = c1.number_input("H", 0, 12, 0), c2.number_input("M", 0, 59, 0)
            if st.form_submit_button("Valider", use_container_width=True):
                val = (hv + mv/60) * (-1 if "Moins" in typ else 1)
                supabase.table("heures").insert({"user": curr_user, "date": str(d), "val": val}).execute()
                st.rerun()
    
    st.subheader("🗑️ Historique")
    if u_a.empty: st.info("Vide")
    else:
        for _, row in u_a.iloc[::-1].iterrows():
            cols = st.columns([0.85, 0.15])
            dt = pd.to_datetime(row['date']).strftime("%d/%m")
            cols[0].write(f"**{dt}** : `{to_hm(row['val'])}`")
            if cols[1].button("🗑️", key=f"h_{row['id']}"):
                supabase.table("heures").delete().eq("id", row['id']).execute()
                st.rerun()

with tab2:
    # Calendrier Robuste
    today = datetime.now()
    st.write(f"📅 **{calendar.month_name[today.month]} {today.year}**")
    posees_jours = pd.to_datetime(u_c['date']).dt.day.tolist() if not u_c.empty else []
    
    cal_head = "".join([f"<div class='cal-day-name'>{d}</div>" for d in ["L","M","M","J","V","S","D"]])
    cal_body = ""
    for week in calendar.monthcalendar(today.year, today.month):
        for day in week:
            if day == 0: cal_body += "<div></div>"
            else:
                classes = "cal-day"
                if day in posees_jours: classes += " cal-off"
                if day == today.day: classes += " cal-today"
                cal_body += f"<div class='{classes}'>{day}</div>"
    
    st.markdown(f"<div class='cal-grid'>{cal_head}{cal_body}</div><br>", unsafe_allow_html=True)

    with st.expander("➕ Poser une période"):
        with st.form("c_f", clear_on_submit=True):
            sel = st.date_input("Dates", value=[date.today()])
            if st.form_submit_button("Confirmer", use_container_width=True):
                g_id = str(uuid.uuid4())
                if isinstance(sel, (list, tuple)) and len(sel) > 1:
                    dr = pd.date_range(sel[0], sel[1], freq='D').date
                else: dr = [sel[0] if isinstance(sel, (list, tuple)) else sel]
                
                rows = [{"user": curr_user, "date": str(d), "type": 1.0, "group_id": g_id} for d in dr if d.weekday() < 5]
                if rows:
                    supabase.table("conges").insert(rows).execute()
                    st.rerun()

    st.subheader("🗑️ Liste des congés")
    if u_c.empty: st.info("Aucun congé.")
    else:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        # Tri et groupement pour affichage propre
        groups = u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False)
        for gid, data in groups:
            cols = st.columns([0.85, 0.15])
            start, end = data['dt'].min(), data['dt'].max()
            if len(data) > 1:
                lbl = f"Du {start.strftime('%d/%m')} au {end.strftime('%d/%m')}"
            else:
                lbl = f"Le {start.strftime('%d/%m')}"
            
            cols[0].write(f"🌴 **{lbl}**")
            if cols[1].button("🗑️", key=f"g_{gid}"):
                supabase.table("conges").delete().eq("group_id", gid).execute()
                st.rerun()

if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()
