import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta

# --- CONFIGURATION ET STYLE ---
st.set_page_config(page_title="Work Tracker", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; }
    .main-card {
        background-color: #161b22;
        padding: 30px;
        border-radius: 15px;
        border: 1px solid #30363d;
        text-align: center;
        margin-bottom: 25px;
    }
    .stat-label { color: #8b949e; font-size: 0.9em; margin-bottom: 5px; }
    .stat-value { color: white; font-size: 1.8em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- CALCUL DU DÛ DYNAMIQUE ---
def get_theo(df_conges):
    # On calcule jusqu'à hier soir pour ne pas être en retard sur la journée en cours
    hier = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total, curr = 0, datetime(2025, 9, 1)
    
    # On transforme les congés saisis en dictionnaire {date: valeur}
    dict_conges = {}
    if not df_conges.empty:
        for _, row in df_conges.iterrows():
            try:
                # Gestion du format de date européen
                d_obj = pd.to_datetime(row['date'], dayfirst=True).date()
                dict_conges[d_obj] = float(row['type'])
            except: continue

    feries = [date(2025,11,11), date(2025,12,25), date(2026,1,1), date(2026,4,13), date(2026,5,1)]

    while curr < hier:
        d = curr.date()
        if curr.weekday() < 5: # Lundi à Vendredi
            # Lun-Mar = 7.5h | Mer-Jeu-Ven = 7h
            h_jour = 7.5 if curr.weekday() <= 1 else 7.0
            
            if d in feries: 
                pass # 0h dues
            elif d in dict_conges: 
                total += h_jour * (1 - dict_conges[d]) # Ex: si 1.0 de congé, on ajoute 0h
            else: 
                total += h_jour
        curr += timedelta(days=1)
    return total

# --- RÉCUPÉRATION DES DONNÉES ---
# On lit les deux feuilles distinctes
df_heures = conn.read(worksheet="Feuille 1", ttl=0)
df_conges = conn.read(worksheet="Conges", ttl=0)

BASE_FAIT = 992.25
theo = get_theo(df_conges)
total_saisi = df_heures['val'].sum() if not df_heures.empty else 0
fait = BASE_FAIT + total_saisi
delta = fait - theo

# --- INTERFACE PRINCIPALE ---
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

col1, col2 = st.columns(2)
with col1:
    st.markdown(f'<p class="stat-label">FAIT</p><p class="stat-value">{fait:.2f}h</p>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<p class="stat-label">DÛ (- congés)</p><p class="stat-value">{theo:.2f}h</p>', unsafe_allow_html=True)

st.divider()

# --- NAVIGATION ---
tab_h, tab_c = st.tabs(["🕒 Saisie Heures", "🌴 Gestion Congés"])

with tab_h:
    st.subheader("Ajouter du temps")
    c1, c2 = st.columns(2)
    h_in = c1.number_input("Heures", min_value=0, step=1, key="h_input")
    m_in = c2.number_input("Minutes", min_value=0, max_value=59, step=1, key="m_input")
    
    if st.button("Valider la saisie", use_container_width=True):
        new_row = pd.DataFrame([{"date": datetime.now().strftime("%d/%m/%Y"), "val": h_in + m_in/60}])
        updated_df = pd.concat([df_heures, new_row], ignore_index=True) if not df_heures.empty else new_row
        conn.update(worksheet="Feuille 1", data=updated_df)
        st.success("Heures enregistrées !")
        st.rerun()

    st.write("---")
    st.write("**Historique récent**")
    if not df_heures.empty:
        st.dataframe(df_heures.iloc[::-1].head(5), use_container_width=True)

with tab_c:
    st.subheader("Déclarer une absence")
    date_abs = st.date_input("Date de l'absence", value=datetime.now())
    type_abs = st.radio("Durée", ["Journée entière", "Demi-journée"], horizontal=True)
    val_abs = 1.0 if type_abs == "Journée entière" else 0.5
    
    if st.button("Enregistrer le congé", use_container_width=True):
        new_c = pd.DataFrame([{"date": date_abs.strftime("%d/%m/%Y"), "type": val_abs}])
        updated_c = pd.concat([df_conges, new_c], ignore_index=True) if not df_conges.empty else new_c
        conn.update(worksheet="Conges", data=updated_c)
        st.success("Congé pris en compte !")
        st.rerun()

    st.write("---")
    if not df_conges.empty:
        st.write("**Congés enregistrés :**")
        # On affiche un bouton de suppression pour chaque congé pour pouvoir corriger
        for i, row in df_conges.iterrows():
            col_txt, col_del = st.columns([4, 1])
            txt = "Entier" if row['type'] == 1.0 else "Demi"
            col_txt.write(f"📅 {row['date']} ({txt})")
            if col_del.button("🗑️", key=f"del_c_{i}"):
                df_conges = df_conges.drop(i)
                conn.update(worksheet="Conges", data=df_conges)
                st.rerun()
