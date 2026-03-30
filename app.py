import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import holidays

# --- 1. CONFIGURATION ---
USERS = {
    "Julien": {"password": "123", "base_sup": 20.5, "full_name": "Julien", "role": "admin"}
}

st.set_page_config(page_title="Mon Annualisation", page_icon="📊", layout="centered")

if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'theme' not in st.session_state: st.session_state.theme = 'dark'

# --- 2. FONCTION CALENDRIER MOBILE (HTML FIX) ---
def draw_mobile_calendar(df_c):
    today = datetime.now()
    cal = calendar.monthcalendar(today.year, today.month)
    month_name = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"][today.month-1]
    
    posees = []
    if not df_c.empty:
        df_c['dt'] = pd.to_datetime(df_c['date'], dayfirst=True)
        posees = df_c[(df_c['dt'].dt.month == today.month) & (df_c['dt'].dt.year == today.year)]['dt'].dt.day.tolist()

    # Style CSS injecté pour forcer la grille sur mobile
    cal_html = f"""
    <style>
        .cal-grid {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 4px;
            margin: 10px 0;
            width: 100%;
        }}
        .cal-day {{
            text-align: center;
            padding: 10px 0;
            background: rgba(255,255,255,0.05);
            border-radius: 5px;
            font-size: 0.8em;
        }}
        .cal-header {{ font-weight: bold; opacity: 0.6; background: none; }}
        .cal-today {{ border: 1px solid #238636; }}
        .cal-conge {{ background: #007bff !important; color: white !important; font-weight: bold; }}
    </style>
    <h4 style='text-align:center;'>{month_name} {today.year}</h4>
    <div class='cal-grid'>
        <div class='cal-day cal-header'>L</div><div class='cal-day cal-header'>M</div>
        <div class='cal-day cal-header'>M</div><div class='cal-day cal-header'>J</div>
        <div class='cal-day cal-header'>V</div><div class='cal-day cal-header'>S</div>
        <div class='cal-day cal-header'>D</div>
    """
    
    for week in cal:
        for day in week:
            if day == 0:
                cal_html += "<div></div>"
            else:
                classes = "cal-day"
                indicator = ""
                if day == today.day: classes += " cal-today"
                if day in posees: 
                    classes += " cal-conge"
                    indicator = "🔵"
                cal_html += f"<div class='{classes}'>{day}{indicator}</div>"
    
    cal_html += "</div>"
    st.markdown(cal_html, unsafe_allow_html=True)

# --- 3. LOGIN ---
if not st.session_state.authenticated:
    st.title("🔐 Connexion")
    u_i = st.text_input("Identifiant")
    p_i = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter", use_container_width=True):
        if u_i in USERS and USERS[u_i]["password"] == p_i:
            st.session_state.authenticated, st.session_state.user_key = True, u_i
            st.rerun()
    st.stop()

curr_user = st.session_state.user_key
u_info = USERS[curr_user]

# --- 4. DATA & CALCULS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_stats(uid, df_a, df_c):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    fr_h = holidays.France(years=[sy, sy+1])
    d_conges = {pd.to_datetime(r['date'], dayfirst=True).date(): float(r['type']) for _, r in df_c[df_c['user']==uid].iterrows()} if 'user' in df_c.columns else {}
    
    theo = 0
    curr = start
    while curr <= now.replace(hour=23, minute=59):
        d = curr.date()
        if curr.weekday() < 5:
            h_j = 7.5 if curr.weekday() <= 1 else 7.0
            if not (d in fr_h and d != date(sy+1, 6, 1)):
                theo += h_j * (1 - d_conges.get(d, 0))
        curr += timedelta(days=1)
    
    val_ajust = df_a[df_a['user']==uid]['val'].sum() if 'user' in df_a.columns else 0
    return USERS[uid]["base_sup"] + val_ajust, theo

df_a = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
df_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')
my_delta, my_theo = get_stats(curr_user, df_a, df_c)

# --- 5. INTERFACE ---
st.title("Mon Annualisation")

# Carte Balance
color = "#238636" if my_delta >= 0 else "#da3633"
h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:20px; border-radius:15px; text-align:center; border:1px solid rgba(255,255,255,0.1);">
        <p style="opacity:0.6; margin:0;">Balance actuelle</p>
        <h1 style="color:{color}; font-size:3.5em; margin:10px 0;">{'+' if my_delta >= 0 else '-'}{h}h{m:02d}</h1>
    </div>
""", unsafe_allow_html=True)

# Admin View
if u_info['role'] == "admin":
    with st.expander("📊 Tableau de bord Equipe (Admin)"):
        for u in USERS:
            d, _ = get_stats(u, df_a, df_c)
            st.write(f"**{u}** : {d:+.2f}h")

st.write("---")
t1, t2 = st.tabs(["⚡ Réguler", "🌴 Congés"])

with t1:
    with st.form("f1", clear_on_submit=True):
        typ = st.selectbox("Type", ["Plus (+)", "Moins (-)"])
        dat = st.date_input("Date", value=date.today())
        hrs = st.number_input("Heures", 0, 12, 0)
        mnt = st.number_input("Minutes", 0, 59, 0)
        if st.form_submit_button("Enregistrer", use_container_width=True):
            v = (hrs + mnt/60) * (-1 if "Moins" in typ else 1)
            new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": v}])
            conn.update(worksheet="Feuille 1", data=pd.concat([df_a, new], ignore_index=True)[['user', 'date', 'val']])
            st.rerun()
    
    # Historique Heures
    u_h = df_a[df_a['user'] == curr_user].iloc[::-1].head(3)
    for i, r in u_h.iterrows():
        c_txt, c_del = st.columns([4, 1])
        c_txt.write(f"{r['date']} : {r['val']:+.2f}h")
        if c_del.button("🗑️", key=f"del_h_{i}"):
            conn.update(worksheet="Feuille 1", data=df_a.drop(i)[['user', 'date', 'val']])
            st.rerun()

with t2:
    draw_mobile_calendar(df_c[df_c['user']==curr_user] if 'user' in df_c.columns else pd.DataFrame())
    
    with st.form("f2", clear_on_submit=True):
        d_c = st.date_input("Date du congé", value=date.today())
        t_c = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
        if st.form_submit_button("Poser le congé", use_container_width=True):
            v_c = 1.0 if t_c == "Journée" else 0.5
            new_c = pd.DataFrame([{"user": curr_user, "date": d_c.strftime("%d/%m/%Y"), "type": v_c}])
            conn.update(worksheet="Conges", data=pd.concat([df_c, new_c], ignore_index=True)[['user', 'date', 'type']])
            st.rerun()

    # Historique Congés
    u_c = df_c[df_c['user'] == curr_user].iloc[::-1].head(3)
    for i, r in u_c.iterrows():
        c_txt, c_del = st.columns([4, 1])
        c_txt.write(f"📅 {r['date']} ({r['type']})")
        if c_del.button("🗑️", key=f"del_c_{i}"):
            conn.update(worksheet="Conges", data=df_c.drop(i)[['user', 'date', 'type']])
            st.rerun()
