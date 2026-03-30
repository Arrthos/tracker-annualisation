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
OBJECTIF_ANNUEL = 1652.0

st.set_page_config(page_title="Work Tracker Pro", page_icon="📊", layout="centered")

if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_key' not in st.session_state: st.session_state.user_key = None

# --- 2. FONCTIONS OPTIMISÉES ---
@st.cache_data(ttl=600)
def get_holidays(year):
    return holidays.France(years=[year, year + 1])

def get_stats(uid, df_a, df_c):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    fr_h = get_holidays(sy)
    
    u_c = df_c[df_c['user'] == uid] if 'user' in df_c.columns else pd.DataFrame()
    u_a = df_a[df_a['user'] == uid] if 'user' in df_a.columns else pd.DataFrame()
    
    d_conges = {pd.to_datetime(r['date'], dayfirst=True).date(): float(r['type']) for _, r in u_c.iterrows()}
    
    theo = 0
    curr = start
    end_calc = now.replace(hour=23, minute=59)
    
    while curr <= end_calc:
        d = curr.date()
        if curr.weekday() < 5:
            h_j = 7.5 if curr.weekday() <= 1 else 7.0
            if not (d in fr_h and d != date(sy+1, 6, 1)):
                theo += h_j * (1 - d_conges.get(d, 0))
        curr += timedelta(days=1)
    
    val_ajust = u_a['val'].sum() if not u_a.empty else 0
    return USERS[uid]["base_sup"] + val_ajust, theo, u_c, u_a

# --- 3. CONNEXION ---
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center;'>🔐 Connexion</h2>", unsafe_allow_html=True)
    with st.form("login"):
        u_i = st.text_input("Identifiant")
        p_i = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Entrer", use_container_width=True):
            if u_i in USERS and USERS[u_i]["password"] == p_i:
                st.session_state.authenticated, st.session_state.user_key = True, u_i
                st.rerun()
    st.stop()

# --- 4. DONNÉES ---
conn = st.connection("gsheets", type=GSheetsConnection)
df_a = conn.read(worksheet="Feuille 1", ttl="1m").dropna(how='all')
df_c = conn.read(worksheet="Conges", ttl="1m").dropna(how='all')

curr_user = st.session_state.user_key
my_delta, my_theo, my_conges_df, my_ajust_df = get_stats(curr_user, df_a, df_c)
fait = my_theo + my_delta

# --- 5. INTERFACE VISUELLE ---
st.title(f"Salut {curr_user} !")

# Barre de progression
prog = min(fait / OBJECTIF_ANNUEL, 1.0)
st.write(f"**Progression : {int(fait)}h / {int(OBJECTIF_ANNUEL)}h**")
st.progress(prog)

# Carte Balance
h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:20px; border-radius:15px; text-align:center; border:1px solid rgba(255,255,255,0.1); margin-bottom:20px;">
        <p style="opacity:0.6; margin:0; font-size:0.9em;">BALANCE ACTUELLE</p>
        <h1 style="color:{color}; font-size:3.5em; margin:10px 0;">{'+' if my_delta >= 0 else '-'}{h}h{m:02d}</h1>
        <p style="opacity:0.8; margin:0;">≃ {my_delta/7.2:.1f} jours de repos</p>
    </div>
""", unsafe_allow_html=True)

# Blocs Fait et Dû
c1, c2 = st.columns(2)
c1.metric("HEURES FAITES", f"{fait:.2f}h")
c2.metric("HEURES DUES", f"{my_theo:.2f}h")

st.divider()

# --- 6. ONGLETS DE SAISIE ---
t1, t2 = st.tabs(["⚡ Réguler", "🌴 Congés"])

with t1:
    with st.expander("📝 Ajouter des heures (+/-)", expanded=False):
        with st.form("h_form", clear_on_submit=True):
            typ = st.selectbox("Type", ["Heures Sup (+)", "Heures en moins (-)"])
            dat = st.date_input("Date", value=date.today())
            h_s, m_s = st.number_input("Heures", 0, 12, 0), st.number_input("Minutes", 0, 59, 0)
            if st.form_submit_button("Enregistrer", use_container_width=True):
                val = (h_s + m_s/60) * (-1 if "moins" in typ else 1)
                new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": val}])
                conn.update(worksheet="Feuille 1", data=pd.concat([df_a, new], ignore_index=True)[['user', 'date', 'val']])
                st.cache_data.clear()
                st.rerun()

    st.write("**Dernières saisies :**")
    for i, r in my_ajust_df.iloc[::-1].head(3).iterrows():
        col_t, col_b = st.columns([4, 1])
        col_t.write(f"{r['date']} : {r['val']:+.2f}h")
        if col_b.button("🗑️", key=f"h_{i}"):
            conn.update(worksheet="Feuille 1", data=df_a.drop(i)[['user', 'date', 'val']])
            st.cache_data.clear()
            st.rerun()

with t2:
    # Calendrier
    today = datetime.now()
    cal = calendar.monthcalendar(today.year, today.month)
    posees = pd.to_datetime(my_conges_df['date'], dayfirst=True).dt.day.tolist() if not my_conges_df.empty else []

    cal_html = "<div style='display:grid; grid-template-columns:repeat(7,1fr); gap:4px; margin-bottom:15px;'>"
    for d in ["L","M","M","J","V","S","D"]: cal_html += f"<b style='text-align:center; font-size:0.7em;'>{d}</b>"
    for week in cal:
        for day in week:
            if day == 0: cal_html += "<div></div>"
            else:
                bg = "#007bff" if day in posees else "rgba(255,255,255,0.05)"
                border = "1px solid #238636" if day == today.day else "none"
                cal_html += f"<div style='text-align:center; padding:8px 0; background:{bg}; border:{border}; border-radius:5px;'>{day}</div>"
    cal_html += "</div>"
    st.markdown(cal_html, unsafe_allow_html=True)

    with st.expander("🌴 Poser un congé / RTT", expanded=False):
        with st.form("c_form", clear_on_submit=True):
            d_c = st.date_input("Date", value=date.today())
            t_c = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
            if st.form_submit_button("Valider le congé", use_container_width=True):
                v_c = 1.0 if t_c == "Journée" else 0.5
                new_c = pd.DataFrame([{"user": curr_user, "date": d_c.strftime("%d/%m/%Y"), "type": v_c}])
                conn.update(worksheet="Conges", data=pd.concat([df_c, new_c], ignore_index=True)[['user', 'date', 'type']])
                st.cache_data.clear()
                st.rerun()

# Sidebar
with st.sidebar:
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
