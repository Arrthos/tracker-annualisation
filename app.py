import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Work Tracker", layout="centered")

# Connexion à Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CALCULS ---
BASE_FAIT = 992.25
DATE_DEBUT = datetime(2025, 9, 1)

def get_theo():
    hier = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total, curr = 0, DATE_DEBUT
    # ... (tes calculs habituels de congés et jours fériés)
    return total

# --- LOGIQUE DE DONNÉES ---
# Lire les données depuis Google Sheets
df = conn.read(ttl=0) # ttl=0 pour forcer la lecture fraîche

# --- INTERFACE ---
st.title("⏱️ Work Tracker")

fait = BASE_FAIT + (df['val'].sum() if not df.empty else 0)
theo = get_theo()
delta = fait - theo

# Affichage du Delta (Gros compteur)
color = "#238636" if delta >= 0 else "#da3633"
st.markdown(f"<h1 style='text-align:center; color:{color};'>{' + ' if delta>=0 else ' - '}{abs(delta):.2f}h</h1>", unsafe_allow_html=True)

# Saisie
st.subheader("Ajouter des heures")
c1, c2 = st.columns(2)
h_in = c1.number_input("Heures", min_value=0, step=1)
m_in = c2.number_input("Minutes", min_value=0, max_value=59, step=1)

if st.button("Valider la saisie"):
    new_row = pd.DataFrame([{"date": datetime.now().strftime("%d/%m/%Y"), "val": h_in + m_in/60}])
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(data=updated_df)
    st.rerun()

# Historique avec suppression
st.subheader("Historique")
for i, row in df.iterrows():
    col_t, col_b = st.columns([4, 1])
    col_t.write(f"{row['date']} : {row['val']}h")
    if col_b.button("🗑️", key=f"del_{i}"):
        df = df.drop(i)
        conn.update(data=df)
        st.rerun()
