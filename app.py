import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import json
import os

# --- CONFIGURATION ET STYLE ---
st.set_page_config(page_title="Annualisation G&R", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #0d1117; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #238636; color: white; }
    .delta-box { padding: 20px; border-radius: 15px; background-color: #161b22; text-align: center; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIQUE DE CALCUL ---
BASE_FAIT = 992.25
DATE_DEBUT = datetime(2025, 9, 1)

def get_theo():
    hier = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total, curr = 0, DATE_DEBUT
    conges = {date(2025,10,14): 0.5, date(2025,10,20): 1.0, date(2026,2,18): 0.5}
    # Ajout automatique des congés de janvier 2026
    for i in range(12):
        d = date(2026,1,19) + timedelta(days=i)
        if d.weekday() < 5: conges[d] = 1.0
    feries = [date(2025,11,11), date(2025,12,25), date(2026,1,1)]

    while curr < hier:
        d = curr.date()
        if curr.weekday() < 5:
            h_jour = 7.5 if curr.weekday() <= 1 else 7.0
            if d in feries: pass
            elif d in conges: total += h_jour * (1 - conges[d])
            else: total += h_jour
        curr += timedelta(days=1)
    return total

# --- GESTION DES DONNÉES ---
DATA_FILE = "data.json"
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f: json.dump({"entries": []}, f)

def load_data():
    with open(DATA_FILE, "r") as f: return json.load(f)["entries"]

def save_entry(h, m):
    data = load_data()
    val = h + (m/60)
    new_entry = {
        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "val": round(val, 2)
    }
    data.insert(0, new_entry)
    with open(DATA_FILE, "w") as f: json.dump({"entries": data}, f)

# --- INTERFACE ---
st.title("⏱️ Annualisation")

entries = load_data()
fait = BASE_FAIT + sum(e["val"] for e in entries)
theo = get_theo()
delta = fait - theo

# Affichage du Delta
color = "#238636" if delta >= 0 else "#da3633"
signe = "+" if delta >= 0 else "-"
h_delta = int(abs(delta))
m_delta = int((abs(delta) - h_delta) * 60)

st.markdown(f"""
    <div class="delta-box">
        <p style="color: #8b949e; margin-bottom: 5px;">Situation Actuelle</p>
        <h1 style="color: {color}; font-size: 3.5em; margin: 0;">{signe}{h_delta}h {m_delta:02d}</h1>
    </div>
    """, unsafe_allow_html=True)

col1, col2 = st.columns(2)
col1.metric("FAIT", f"{fait:.2f}h")
col2.metric("DÛ", f"{theo:.2f}h")

st.divider()

# Saisie
st.subheader("Ajouter des heures")
c1, c2 = st.columns(2)
h_in = c1.number_input("Heures", min_value=0, max_value=23, step=1)
m_in = c2.number_input("Minutes", min_value=0, max_value=59, step=1)

if st.button("Valider la saisie"):
    if h_in + m_in > 0:
        save_entry(h_in, m_in)
        st.success("Ajouté !")
        st.rerun()

# Historique avec option de suppression
st.subheader("Historique des saisies")
if entries:
    for i, entry in enumerate(entries):
        cols = st.columns([3, 2, 1])
        cols[0].write(f"📅 {entry['date']}")
        cols[1].write(f"**+{entry['val']}h**")
        
        # Bouton de suppression unique pour chaque ligne
        if cols[2].button("🗑️", key=f"del_{i}"):
            # On retire l'entrée de la liste
            entries.pop(i)
            # On réenregistre le fichier JSON
            with open(DATA_FILE, "w") as f:
                json.dump({"entries": entries}, f)
            st.rerun()
else:
    st.info("Aucune saisie pour le moment.")