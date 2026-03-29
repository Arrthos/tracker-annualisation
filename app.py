import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta

# --- CONFIGURATION ET STYLE CSS ---
st.set_page_config(page_title="Work Tracker", layout="centered")

st.markdown("""
    <style>
    /* Fond principal */
    .stApp { background-color: #0d1117; }
    
    /* Carte Situation Actuelle */
    .main-card {
        background-color: #161b22;
        padding: 30px;
        border-radius: 15px;
        border: 1px solid #30363d;
        text-align: center;
        margin-bottom: 25px;
    }
    
    /* Libellés FAIT / DÛ */
    .stat-label { color: #8b949e; font-size: 0.9em; margin-bottom: 5px; }
    .stat-value { color: white; font-size: 1.8em; font-weight: bold; }
    
    /* Bouton Valider */
    .stButton>button {
        background-color: #238636;
        color: white;
        border-radius: 8px;
        width: 100%;
        border: none;
        height: 45px;
        font-weight: bold;
    }
    .stButton>button:hover { background-color: #2ea043; border: none; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- CONNEXION ET CALCULS ---
# Remplacer l'ancienne ligne de connexion par celle-ci :
conn = st.connection("gsheets", type=GSheetsConnection)

def get_theo():
    hier = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total, curr = 0, datetime(2025, 9, 1)
    conges = {date(2025,10,14): 0.5, date(2025,10,20): 1.0, date(2026,2,18): 0.5}
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

# --- RÉCUPÉRATION DONNÉES ---
df = conn.read(ttl=0)
BASE_FAIT = 992.25
theo = get_theo()
total_saisi = df['val'].sum() if not df.empty else 0
fait = BASE_FAIT + total_saisi
delta = fait - theo

# --- INTERFACE ---
st.markdown("### ⏱️ Annualisation")

# Bloc Situation Actuelle
color = "#238636" if delta >= 0 else "#da3633"
h_delta = int(abs(delta))
m_delta = int((abs(delta) - h_delta) * 60)

st.markdown(f"""
    <div class="main-card">
        <p style="color: #8b949e; font-size: 0.9em;">Situation Actuelle</p>
        <h1 style="color: {color}; font-size: 4em; margin: 10px 0;">
            {'+' if delta >= 0 else '-'}{h_delta}h {m_delta:02d}
        </h1>
    </div>
    """, unsafe_allow_html=True)

# Ligne FAIT / DÛ
col1, col2 = st.columns(2)
with col1:
    st.markdown(f'<p class="stat-label">FAIT</p><p class="stat-value">{fait:.2f}h</p>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<p class="stat-label">DÛ</p><p class="stat-value">{theo:.2f}h</p>', unsafe_allow_html=True)

st.divider()

# Section Saisie
st.markdown("#### Ajouter des heures")
c1, c2 = st.columns(2)
h_in = c1.number_input("Heures", min_value=0, step=1, key="h")
m_in = c2.number_input("Minutes", min_value=0, max_value=59, step=1, key="m")

if st.button("Valider la saisie"):
    # 1. Préparation de la nouvelle ligne
    new_row = pd.DataFrame([{
        "date": datetime.now().strftime("%d/%m/%Y"), 
        "val": h_in + m_in/60
    }])
    
    # 2. Fusion avec les anciennes données
    if df.empty:
        updated_df = new_row
    else:
        updated_df = pd.concat([df, new_row], ignore_index=True)
    
    # 3. C'est CETTE LIGNE qui fait la mise à jour vers Google Sheets
    conn.update(data=updated_df) 
    
    st.success("Enregistré dans Google Sheets !")
    st.rerun()
# Section Historique
st.markdown("#### Historique des saisies")
if not df.empty:
    for i, row in df.iloc[::-1].iterrows(): # Affichage du plus récent au plus ancien
        with st.container():
            col_t, col_b = st.columns([4, 1])
            col_t.markdown(f"📅 {row['date']} : **{row['val']:.2f}h**")
            if col_b.button("🗑️", key=f"del_{i}"):
                df = df.drop(i)
                conn.update(data=df)
                st.rerun()
else:
    st.info("Aucune saisie pour le moment.")
