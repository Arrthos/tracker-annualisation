import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
from datetime import datetime, date
import calendar
import holidays

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

@st.cache_data(ttl=3600)
def get_fr_holidays(years):
    return holidays.France(years=years)

# --- 2. CALCULS VECTORISÉS ---
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
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date'], dayfirst=True, errors='coerce').dt.date
        conges_map = df_conges.dropna(subset=['dt_temp']).set_index('dt_temp')['type'].to_dict()
        df_dates['conge_val'] = df_dates['date'].dt.date.map(conges_map).fillna(0)
        df_dates['h_theo'] *= (1 - df_dates['conge_val'])
        
    return df_dates['h_theo'].sum()

# --- 3. AUTHENTIFICATION ---
USERS = {"Julien": {"password": "123", "base_sup": 20.5}}
if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Connexion")
    with st.form("login"):
        u_i = st.text_input("Identifiant")
        p_i = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Entrer", use_container_width=True):
            if u_i in USERS and USERS[u_i]["password"] == p_i:
                st.session_state.authenticated, st.session_state.user_key = True, u_i
                st.rerun()
    st.stop()

# --- 4. CHARGEMENT DATA ---
conn = st.connection("gsheets", type=GSheetsConnection)
df_a = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
df_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')

curr_user = st.session_state.user_key
u_a = df_a[df_a['user'] == curr_user].copy()
u_c = df_c[df_c['user'] == curr_user].copy()

# --- 5. DASHBOARD ---
st.sidebar.title("⚙️ Paramètres")
sol_date = st.sidebar.date_input("Journée de Solidarité", value=date(2024, 5, 20))

my_theo = calculate_due_fast(u_c.copy(), sol_date)
my_delta = USERS[curr_user]["base_sup"] + (u_a['val'].sum() if not u_a.empty else 0)
fait = my_theo + my_delta

st.title(f"Hello {curr_user}")
st.progress(min(max(fait / 1652.0, 0.0), 1.0))

# Balance & Stats
h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color_delta = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:15px; text-align:center; border:2px solid {color_delta}; margin-bottom:10px;">
        <h1 style="color:{color_delta}; font-size:3.5em; margin:0;">{'+' if my_delta >= 0 else '-'}{h}h{m:02d}</h1>
    </div>
    <div style="display:flex; justify-content:space-around; margin-bottom:20px; background:rgba(255,255,255,0.02); padding:10px; border-radius:10px;">
        <div style="text-align:center;"><small style="opacity:0.5;">FAIT</small><br><b>{fait:.1f}h</b></div>
        <div style="text-align:center;"><small style="opacity:0.5;">DÛ</small><br><b>{my_theo:.1f}h</b></div>
    </div>
""", unsafe_allow_html=True)

# --- 6. ONGLETS ---
tab1, tab2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with tab1:
    @st.fragment
    def frag_h():
        with st.expander("➕ Ajouter des heures"):
            with st.form("h_f", clear_on_submit=True):
                typ = st.radio("Type", ["+", "-"], horizontal=True)
                dat = st.date_input("Date", value=date.today())
                c1, c2 = st.columns(2)
                h_v = c1.number_input("H", 0, 12, 0)
                m_v = c2.number_input("M", 0, 59, 0)
                if st.form_submit_button("Valider"):
                    val = (h_v + m_v/60) * (-1 if typ == "-" else 1)
                    new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": val}])
                    conn.update(worksheet="Feuille 1", data=pd.concat([conn.read(worksheet="Feuille 1", ttl=0), new]))
                    st.rerun()
        
        for i in u_a.index[::-1]:
            cols = st.columns([4, 1])
            cols[0].write(f"**{u_a.loc[i, 'date']}** : {u_a.loc[i, 'val']:+.2f}h")
            if cols[1].button("🗑️", key=f"h_{i}"):
                conn.update(worksheet="Feuille 1", data=df_a.drop(i))
                st.rerun()
    frag_h()

with tab2:
    # --- CALENDRIER ---
    today = datetime.now()
    u_c['dt_temp'] = pd.to_datetime(u_c['date'], dayfirst=True, errors='coerce')
    posees = u_c[(u_c['dt_temp'].dt.month == today.month) & (u_c['dt_temp'].dt.year == today.year)]['dt_temp'].dt.day.tolist() if not u_c.empty else []
    
    st.write(f"📅 **{calendar.month_name[today.month]} {today.year}**")
    cal_html = "<div style='display:grid; grid-template-columns:repeat(7,1fr); gap:4px;'>"
    for d in ["L","M","M","J","V","S","D"]: cal_html += f"<b style='text-align:center; font-size:0.7em;'>{d}</b>"
    for week in calendar.monthcalendar(today.year, today.month):
        for day in week:
            if day == 0: cal_html += "<div></div>"
            else:
                bg = "#007bff" if day in posees else "rgba(255,255,255,0.05)"
                border = "2px solid #238636" if day == today.day else "none"
                cal_html += f"<div style='text-align:center; padding:8px 0; background:{bg}; border:{border}; border-radius:5px;'>{day}</div>"
    st.markdown(cal_html + "</div>", unsafe_allow_html=True)

    @st.fragment
    def frag_c():
        with st.expander("➕ Poser un congé"):
            with st.form("c_f", clear_on_submit=True):
                d_v = st.date_input("Jour", value=date.today())
                t_v = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
                if st.form_submit_button("Confirmer"):
                    val_c = 1.0 if t_v == "Journée" else 0.5
                    new_c = pd.DataFrame([{"user": curr_user, "date": d_v.strftime("%d/%m/%Y"), "type": val_c}])
                    conn.update(worksheet="Conges", data=pd.concat([conn.read(worksheet="Conges", ttl=0), new_c]))
                    st.rerun()

        for i in u_c.index[::-1]:
            cols = st.columns([4, 1])
            cols[0].write(f"📅 {u_c.loc[i, 'date']} ({u_c.loc[i, 'type']}j)")
            if cols[1].button("🗑️", key=f"c_{i}"):
                conn.update(worksheet="Conges", data=df_c.drop(i))
                st.rerun()
    frag_c()

st.sidebar.button("🚪 Déconnexion", on_click=lambda: st.session_state.update({"authenticated": False}))
