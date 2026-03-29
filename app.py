import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta

# --- CONFIGURATION ET STYLE CSS ---
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
    .stButton>button { border-radius: 8px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- CALCUL DU DÛ DYNAMIQUE ---
def get_theo(df_conges):
    # On calcule jusqu'à hier soir.
    hier = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total, curr = 0, datetime(2025, 9, 1)
    
    dict_conges = {}
    if not df_conges.empty:
        for _, row in df_conges.iterrows():
            try:
                d_val = row['date']
                if isinstance(d_val, str):
                    d_obj = pd.to_datetime(d_val, dayfirst=True).date()
                else:
                    d_obj = d_val.date() if hasattr(d_val, 'date') else pd.to_datetime(d_val).date()
                dict_conges[d_obj] = float(row['type'])
            except: continue

    feries = [date(2025,11,11), date(2025,12,25), date(2026,1,1), date(2026,4,13), date(2026,5,1)]

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
df_heures = conn.read(worksheet="Feuille 1", ttl=0)
df_conges = conn.read(worksheet="Conges", ttl=0)

BASE_FAIT = 992.25
theo = get_theo(df_conges)
total_saisi = df_heures['val'].sum() if not df_heures.empty else 0
fait = BASE_FAIT + total_saisi
delta = fait - theo

# --- INTERFACE PRINCIPALE ---
st.markdown("### ⏱️ Annualisation")

# Affichage du Delta (Avance/Retard)
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
    st.markdown(f'<p class="stat-label">FAIT (Total)</p><p class="stat-value">{fait:.2f}h</p>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<p class="stat-label">DÛ (Théorique)</p><p class="stat-value">{theo:.2f}h</p>', unsafe_allow_html=True)

st.divider()

# --- ONGLETS ---
tab_h, tab_c = st.tabs(["🕒 Saisie Heures", "🌴 Gestion Congés"])

with tab_h:
    # Déterminer la journée type selon le jour actuel
    today_wd = datetime.now().weekday()
    std_h = 7
    std_m = 30 if today_wd <= 1 else 0 # 7h30 Lun/Mar, sinon 7h
    
    st.subheader("Saisie rapide")
    if st.button(f"🚀 Valider ma journée standard ({std_h}h{std_m:02d})", use_container_width=True, type="primary"):
        new_row = pd.DataFrame([{"date": datetime.now().strftime("%d/%m/%Y"), "val": std_h + std_m/60}])
        updated = pd.concat([df_heures, new_row], ignore_index=True) if not df_heures.empty else new_row
        conn.update(worksheet="Feuille 1", data=updated)
        st.success("Journée enregistrée !")
        st.rerun()

    st.write("---")
    with st.expander("Saisie précise (Heures Sup / Retard)"):
        c1, c2 = st.columns(2)
        h_in = c1.number_input("Heures", min_value=0, step=1, value=std_h)
        m_in = c2.number_input("Minutes", min_value=0, max_value=59, step=1, value=std_m)
        if st.button("Enregistrer la durée précise", use_container_width=True):
            new_row = pd.DataFrame([{"date": datetime.now().strftime("%d/%m/%Y"), "val": h_in + m_in/60}])
            updated = pd.concat([df_heures, new_row], ignore_index=True) if not df_heures.empty else new_row
            conn.update(worksheet="Feuille 1", data=updated)
            st.rerun()

    st.write("**Dernières saisies :**")
    if not df_heures.empty:
        # On affiche les 5 dernières lignes avec bouton supprimer
        last_5 = df_heures.iloc[::-1].head(5)
        for i, row in last_5.iterrows():
            c_txt, c_del = st.columns([4, 1])
            c_txt.write(f"📅 {row['date']} : {row['val']:.2f}h")
            if c_del.button("🗑️", key=f"del_h_{i}"):
                df_heures = df_heures.drop(i)
                conn.update(worksheet="Feuille 1", data=df_heures)
                st.rerun()

with tab_c:
    st.subheader("Déclarer un congé")
    date_abs = st.date_input("Date du congé", value=datetime.now())
    type_abs = st.radio("Durée", ["Journée entière", "Demi-journée"], horizontal=True)
    val_abs = 1.0 if type_abs == "Journée entière" else 0.5
    
    if st.button("Enregistrer l'absence", use_container_width=True):
        new_c = pd.DataFrame([{"date": date_abs.strftime("%d/%m/%Y"), "type": val_abs}])
        updated_c = pd.concat([df_conges, new_c], ignore_index=True) if not df_conges.empty else new_c
        conn.update(worksheet="Conges", data=updated_c)
        st.success("Congé ajouté !")
        st.rerun()

    st.write("---")
    if not df_conges.empty:
        st.write("**Congés enregistrés :**")
        for i, row in df_conges.iterrows():
            col_txt, col_del = st.columns([4, 1])
            col_txt.write(f"📅 {row['date']} ({'Entier' if row['type']==1 else 'Demi'})")
            if col_del.button("🗑️", key=f"del_c_{i}"):
                df_conges = df_conges.drop(i)
                conn.update(worksheet="Conges", data=df_conges)
                st.rerun()
