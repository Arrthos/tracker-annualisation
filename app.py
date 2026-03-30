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
    with st.form("login"):
        u_i = st.text_input("Identifiant")
        p_i = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Entrer"):
            if u_i in USERS and USERS[u_i]["password"] == p_i:
                st.session_state.authenticated, st.session_state.user_key = True, u_i
                st.rerun()
    st.stop()

# --- 3. DATA ---
conn = st.connection("gsheets", type=GSheetsConnection)
df_a = conn.read(worksheet="Feuille 1", ttl="1m").dropna(how='all')
df_c = conn.read(worksheet="Conges", ttl="1m").dropna(how='all')

# Calculs (Version simplifiée pour la fluidité)
curr_user = st.session_state.user_key
u_a = df_a[df_a['user'] == curr_user].copy()
u_c = df_c[df_c['user'] == curr_user].copy()

# (Simulons les totaux pour l'affichage)
my_delta = USERS[curr_user]["base_sup"] + u_a['val'].sum()
fait = 1200 # Exemple
my_theo = 1180 # Exemple

# --- 4. INTERFACE ---
st.title(f"Suivi de {curr_user}")

h, m = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"<div style='text-align:center; padding:20px; border:1px solid #333; border-radius:15px;'><h1 style='color:{color};'>{'+' if my_delta >= 0 else '-'}{h}h{m:02d}</h1></div>", unsafe_allow_html=True)

t1, t2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with t1:
    # FORMULAIRE TOUJOURS VISIBLE
    st.subheader("📝 Nouvelle saisie")
    with st.form("h_form", clear_on_submit=True):
        typ = st.selectbox("Action", ["Plus (+)", "Moins (-)"])
        dat = st.date_input("Date", value=date.today())
        h_s = st.number_input("Heures", 0, 12, 0)
        if st.form_submit_button("Enregistrer"):
            val = h_s * (-1 if "moins" in typ else 1)
            new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": val}])
            conn.update(worksheet="Feuille 1", data=pd.concat([df_a, new], ignore_index=True))
            st.rerun()

    st.write("---")
    st.subheader("🗑️ Historique (Suppression)")
    for i, r in u_a.iloc[::-1].head(5).iterrows():
        c1, c2 = st.columns([4, 1])
        c1.write(f"{r['date']} : {r['val']:+.2f}h")
        if c2.button("🗑️", key=f"del_h_{i}"):
            conn.update(worksheet="Feuille 1", data=df_a.drop(i))
            st.rerun()

with t2:
    # CALENDRIER FILTRÉ
    today = datetime.now()
    st.write(f"📅 **Calendrier {today.month}/{today.year}**")
    # ... (Code du calendrier Grid ici) ...
    
    st.write("---")
    st.subheader("🌴 Poser un congé")
    with st.form("c_form", clear_on_submit=True):
        d_c = st.date_input("Date du repos", value=date.today())
        if st.form_submit_button("Valider"):
            new_c = pd.DataFrame([{"user": curr_user, "date": d_c.strftime("%d/%m/%Y"), "type": 1.0}])
            conn.update(worksheet="Conges", data=pd.concat([df_c, new_c], ignore_index=True))
            st.rerun()

    st.subheader("🗑️ Liste des congés")
    for i, r in u_c.iloc[::-1].head(5).iterrows():
        c1, c2 = st.columns([4, 1])
        c1.write(f"📅 {r['date']}")
        if c2.button("🗑️", key=f"del_c_{i}"):
            conn.update(worksheet="Conges", data=df_c.drop(i))
            st.rerun()
