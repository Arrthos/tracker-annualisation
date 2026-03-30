import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import calendar
import holidays

# --- 1. CONFIGURATION ---
USERS = {"Julien": {"password": "123", "base_sup": 20.5, "full_name": "Julien", "role": "admin"}}
OBJECTIF_ANNUEL = 1652.0

st.set_page_config(page_title="Work Tracker Pro", layout="centered")

if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_key' not in st.session_state: st.session_state.user_key = None

# --- 2. LOGIQUE CONNEXION ---
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

# --- 3. CHARGEMENT ET CALCULS ---
conn = st.connection("gsheets", type=GSheetsConnection)
# On force le rafraîchissement avec ttl=0 pour être sûr de voir les suppressions
df_a = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
df_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')

curr_user = st.session_state.user_key
u_a = df_a[df_a['user'] == curr_user].copy()
u_c = df_c[df_c['user'] == curr_user].copy()

# Calcul de la balance (Simplifié pour éviter les erreurs)
val_ajust = u_a['val'].sum() if not u_a.empty else 0
my_delta = USERS[curr_user]["base_sup"] + val_ajust

# --- 4. INTERFACE ---
st.title(f"Tableau de {curr_user}")

# Affichage Balance
h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:20px; border-radius:15px; text-align:center; border:1px solid {color};">
        <p style="margin:0; opacity:0.6;">BALANCE ACTUELLE</p>
        <h1 style="color:{color}; font-size:3.5em; margin:10px 0;">{'+' if my_delta >= 0 else '-'}{h}h{m:02d}</h1>
    </div>
""", unsafe_allow_html=True)

t1, t2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with t1:
    st.subheader("📝 Ajouter des heures")
    with st.form("h_form", clear_on_submit=True):
        typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
        dat = st.date_input("Date", value=date.today())
        h_s = st.number_input("Heures", 0, 12, 0)
        m_s = st.number_input("Minutes", 0, 59, 0)
        if st.form_submit_button("Enregistrer", use_container_width=True):
            val = (h_s + m_s/60) * (-1 if "Moins" in typ else 1)
            new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": val}])
            updated_df = pd.concat([df_a, new], ignore_index=True)
            conn.update(worksheet="Feuille 1", data=updated_df)
            st.success("Enregistré !")
            st.rerun()

    st.write("---")
    st.subheader("🗑️ Historique & Suppression")
    if u_a.empty:
        st.info("Aucun historique")
    else:
        # On affiche les 5 dernières lignes de l'utilisateur
        for i in u_a.index[-5:]:
            row = u_a.loc[i]
            col_t, col_b = st.columns([4, 1])
            col_t.write(f"**{row['date']}** : {row['val']:+.2f}h")
            if col_b.button("🗑️", key=f"del_h_{i}"):
                # Suppression par index dans le dataframe global
                df_a_new = df_a.drop(i)
                conn.update(worksheet="Feuille 1", data=df_a_new)
                st.rerun()

with t2:
    # --- CALENDRIER RE-CONSTRUIT ---
    today = datetime.now()
    cal = calendar.monthcalendar(today.year, today.month)
    
    # Extraction des jours du mois actuel pour Julien
    posees_ce_mois = []
    if not u_c.empty:
        u_c['dt_temp'] = pd.to_datetime(u_c['date'], dayfirst=True, errors='coerce')
        posees_ce_mois = u_c[
            (u_c['dt_temp'].dt.month == today.month) & 
            (u_c['dt_temp'].dt.year == today.year)
        ]['dt_temp'].dt.day.tolist()

    st.write(f"📅 **{calendar.month_name[today.month]} {today.year}**")
    
    # Grille HTML pour mobile
    cal_html = "<div style='display:grid; grid-template-columns:repeat(7,1fr); gap:4px;'>"
    for d in ["L","M","M","J","V","S","D"]: cal_html += f"<b style='text-align:center; font-size:0.7em;'>{d}</b>"
    for week in cal:
        for day in week:
            if day == 0: cal_html += "<div></div>"
            else:
                bg = "#007bff" if day in posees_ce_mois else "rgba(255,255,255,0.1)"
                border = "2px solid #238636" if day == today.day else "none"
                cal_html += f"<div style='text-align:center; padding:10px 0; background:{bg}; border:{border}; border-radius:5px;'>{day}</div>"
    cal_html += "</div>"
    st.markdown(cal_html, unsafe_allow_html=True)

    st.write("---")
    st.subheader("🌴 Poser un congé")
    with st.form("c_form", clear_on_submit=True):
        d_c = st.date_input("Date", value=date.today())
        t_c = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
        if st.form_submit_button("Enregistrer le congé", use_container_width=True):
            v_c = 1.0 if t_c == "Journée" else 0.5
            new_c = pd.DataFrame([{"user": curr_user, "date": d_c.strftime("%d/%m/%Y"), "type": v_c}])
            updated_df_c = pd.concat([df_c, new_c], ignore_index=True)
            conn.update(worksheet="Conges", data=updated_df_c)
            st.rerun()

    st.subheader("🗑️ Supprimer un congé")
    if u_c.empty:
        st.info("Aucun congé")
    else:
        for i in u_c.index[-5:]:
            row = u_c.loc[i]
            col_t, col_b = st.columns([4, 1])
            col_t.write(f"📅 {row['date']} ({row['type']} j)")
            if col_b.button("🗑️", key=f"del_c_{i}"):
                df_c_new = df_c.drop(i)
                conn.update(worksheet="Conges", data=df_c_new)
                st.rerun()

if st.sidebar.button("🚪 Déconnexion"):
    st.session_state.authenticated = False
    st.rerun()
