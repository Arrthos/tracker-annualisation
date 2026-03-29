import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Work Tracker", layout="centered")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- FONCTION DE CALCUL DU DÛ (Recalcule tout) ---
def get_theo(df_conges):
    hier = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total, curr = 0, datetime(2025, 9, 1)
    
    # Transformation des congés du GSheet en dictionnaire pour le calcul
    dict_conges = {}
    if not df_conges.empty:
        for _, row in df_conges.iterrows():
            try:
                d_obj = pd.to_datetime(row['date'], dayfirst=True).date()
                dict_conges[d_obj] = float(row['type'])
            except: continue

    feries = [date(2025,11,11), date(2025,12,25), date(2026,1,1)]

    while curr < hier:
        d = curr.date()
        if curr.weekday() < 5: # Lundi-Vendredi
            h_jour = 7.5 if curr.weekday() <= 1 else 7.0
            if d in feries: pass
            elif d in dict_conges: total += h_jour * (1 - dict_conges[d])
            else: total += h_jour
        curr += timedelta(days=1)
    return total

# --- RÉCUPÉRATION DES DONNÉES ---
df_heures = conn.read(worksheet="Feuille 1", ttl=0) # Ta feuille d'heures
df_conges = conn.read(worksheet="Conges", ttl=0)   # Ta nouvelle feuille

BASE_FAIT = 992.25
theo = get_theo(df_conges)
fait = BASE_FAIT + (df_heures['val'].sum() if not df_heures.empty else 0)
delta = fait - theo

# --- INTERFACE ---
st.title("⏱️ Annualisation")

# Affichage du Delta
color = "#238636" if delta >= 0 else "#da3633"
h_delta = int(abs(delta))
m_delta = int((abs(delta) - h_delta) * 60)
st.markdown(f"<div style='text-align:center; background:#161b22; padding:20px; border-radius:15px; border:1px solid #30363d;'><h1 style='color:{color}; font-size:4em;'>{'+' if delta>=0 else '-'}{h_delta}h {m_delta:02d}</h1></div>", unsafe_allow_html=True)

# ONGLETS POUR SÉPARER SAISIE HEURES / CONGÉS
tab1, tab2 = st.tabs(["🕒 Heures", "🌴 Congés"])

with tab1:
    st.subheader("Ajouter des heures")
    c1, c2 = st.columns(2)
    h_in = c1.number_input("Heures", min_value=0, step=1)
    m_in = c2.number_input("Minutes", min_value=0, max_value=59, step=1)
    if st.button("Valider les heures"):
        new_row = pd.DataFrame([{"date": datetime.now().strftime("%d/%m/%Y"), "val": h_in + m_in/60}])
        updated = pd.concat([df_heures, new_row], ignore_index=True)
        conn.update(worksheet="Feuille 1", data=updated)
        st.rerun()

with tab2:
    st.subheader("Déclarer un congé")
    date_c = st.date_input("Date du congé")
    type_c = st.selectbox("Type", ["Journée entière", "Demi-journée"], index=0)
    val_c = 1.0 if type_c == "Journée entière" else 0.5
    
    if st.button("Enregistrer le congé"):
        new_c = pd.DataFrame([{"date": date_c.strftime("%d/%m/%Y"), "type": val_c}])
        updated_c = pd.concat([df_conges, new_c], ignore_index=True)
        conn.update(worksheet="Conges", data=updated_c)
        st.rerun()
    
    st.write("---")
    st.write("Historique congés :")
    st.dataframe(df_conges, use_container_width=True)
