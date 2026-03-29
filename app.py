import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import holidays

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Work Tracker Pro",
    page_icon="https://raw.githubusercontent.com/Arrthos/tracker-annualisation/main/image_11.png",
    layout="centered"
)

# --- 2. GESTION DU THÈME ET STYLE CSS ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

# CSS COMMUN (Suppression des icônes de chaînes/ancres)
common_css = """
    <style>
    .element-container h1 a, .element-container h2 a, .element-container h3 a {
        display: none !important;
    }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    .stProgress > div > div > div > div { background-color: #238636; }
    </style>
"""

dark_css = """
    .stApp { background: radial-gradient(circle at center, #1a2a40 0%, #0d1117 100%); background-attachment: fixed; }
    .main-card { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(20px); padding: 30px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; margin-bottom: 25px; }
    .stat-label { color: rgba(255, 255, 255, 0.6) !important; font-size: 0.9em; }
    .stat-value { color: white !important; font-size: 1.8em; font-weight: bold; }
    .reward-text { color: #3fb950 !important; font-weight: bold; font-size: 1.2em; }
    h1, h2, h3, p, span, .stMarkdown { color: white !important; }
"""

light_css = """
    .stApp { background-color: #FAF5F0; }
    .main-card { 
        background: white; 
        padding: 30px; border-radius: 20px; border: 1px solid #E2E8F0; 
        text-align: center; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    }
    .stat-label { color: #4A5568 !important; font-size: 0.9em; }
    .stat-value { color: #1A202C !important; font-size: 1.8em; font-weight: bold; }
    .reward-text { color: #2D3748 !important; font-weight: bold; font-size: 1.2em; }
    h1, h2, h3, p, span, .stMarkdown { color: #1A202C !important; }
    .stTabs [data-baseweb="tab"] { color: #4A5568 !important; }
"""

active_css = dark_css if st.session_state.theme == 'dark' else light_css
st.markdown(common_css, unsafe_allow_html=True)
st.markdown(f"<style>{active_css}</style>", unsafe_allow_html=True)

# --- 3. LOGIQUE DE CONNEXION ET SAISON ---
conn = st.connection("gsheets", type=GSheetsConnection)

now = datetime.now()
start_year = now.year if now.month >= 9 else now.year - 1
date_debut_saison = datetime(start_year, 9, 1)
date_fin_saison = datetime(start_year + 1, 8, 31)

with st.sidebar:
    st.button("🌓 Changer de Mode", on_click=toggle_theme, use_container_width=True)
    st.divider()
    st.info(f"Saison active : {start_year}-{start_year+1}")
    date_solidarite = st.date_input("Journée de Solidarité", value=date(start_year + 1, 6, 1))

# --- 4. FONCTION DE CALCUL DU THÉORIQUE ---
def get_theo(df_conges, start_date, solidarite_date):
    hier = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total, curr = 0, start_date
    fr_holidays = holidays.France(years=[start_year, start_year + 1])
    
    dict_conges = {}
    if not df_conges.empty:
        for _, row in df_conges.iterrows():
            try:
                d_obj = pd.to_datetime(row['date'], dayfirst=True).date()
                dict_conges[d_obj] = float(row['type'])
            except: continue

    while curr < hier:
        d = curr.date()
        if curr.weekday() < 5: 
            h_jour = 7.5 if curr.weekday() <= 1 else 7.0 
            if d in fr_holidays and d != solidarite_date:
                pass 
            else:
                if d in dict_conges: total += h_jour * (1 - dict_conges[d])
                else: total += h_jour
        curr += timedelta(days=1)
    return total

# --- 5. CHARGEMENT ET FILTRAGE ---
df_heures_raw = conn.read(worksheet="Feuille 1", ttl=0)
df_conges_raw = conn.read(worksheet="Conges", ttl=0)

def filter_by_season(df, start_date, end_date):
    if df.empty: return df.copy()
    df_copy = df.copy()
    df_copy['date_dt'] = pd.to_datetime(df_copy['date'], dayfirst=True)
    mask = (df_copy['date_dt'] >= start_date) & (df_copy['date_dt'] <= end_date)
    return df_copy.loc[mask].drop(columns=['date_dt'])

df_heures = filter_by_season(df_heures_raw, date_debut_saison, date_fin_saison)
df_conges = filter_by_season(df_conges_raw, date_debut_saison, date_fin_saison)

OBJECTIF_ANNUEL = 1652.0
current_base = 992.25 if start_year == 2025 else 0.0

theo = get_theo(df_conges, date_debut_saison, date_solidarite)
total_saisi = df_heures['val'].sum() if not df_heures.empty else 0
fait = current_base + total_saisi
delta = fait - theo
jours_repos = delta / 7.2 if delta > 0 else 0

# --- 6. AFFICHAGE ---
st.markdown(f"### Progression : {int(fait)}h / {int(OBJECTIF_ANNUEL)}h")
st.progress(min(fait / OBJECTIF_ANNUEL, 1.0))

color = "#238636" if delta >= 0 else "#da3633"
h_delta, m_delta = int(abs(delta)), int((abs(delta) - int(abs(delta))) * 60)

st.markdown(f"""
    <div class="main-card">
        <p class="stat-label">Balance Annualisation</p>
        <h1 style="color: {color} !important; font-size: 3.5em; margin: 10px 0;">
            {'+' if delta >= 0 else '-'}{h_delta}h{m_delta:02d}
        </h1>
        {f'<p class="reward-text">≃ {jours_repos:.1f} jours de repos</p>' if delta > 0 else ''}
    </div>
    """, unsafe_allow_html=True)

col_a, col_b = st.columns(2)
col_a.markdown(f'<p class="stat-label">HEURES FAITES</p><p class="stat-value">{fait:.2f}h</p>', unsafe_allow_html=True)
col_b.markdown(f'<p class="stat-label">HEURES DUES</p><p class="stat-value">{theo:.2f}h</p>', unsafe_allow_html=True)

st.divider()

# --- 7. ONGLETS ---
tab1, tab2 = st.tabs(["🕒 Saisie Heures", "🌴 Gestion Congés"])

with tab1:
    wd = datetime.now().weekday()
    std_h, std_m = (7, 30) if wd <= 1 else (7, 0)
    
    if st.button(f"Valider journée standard ({std_h}h{std_m:02d})", use_container_width=True):
        new_row = pd.DataFrame([{"date": datetime.now().strftime("%d/%m/%Y"), "val": std_h + std_m/60}])
        updated = pd.concat([df_heures_raw, new_row], ignore_index=True)
        conn.update(worksheet="Feuille 1", data=updated)
        st.rerun()

    with st.expander("Saisie personnalisée"):
        d_input = st.date_input("Date", value=datetime.now())
        c1, c2 = st.columns(2)
        h_in = c1.number_input("Heures", 0, 24, std_h)
        m_in = c2.number_input("Minutes", 0, 59, std_m)
        if st.button("Enregistrer l'heure", use_container_width=True):
            new_row = pd.DataFrame([{"date": d_input.strftime("%d/%m/%Y"), "val": h_in + m_in/60}])
            updated = pd.concat([df_heures_raw, new_row], ignore_index=True)
            conn.update(worksheet="Feuille 1", data=updated)
            st.rerun()

    if not df_heures.empty:
        st.write("**Dernières saisies :**")
        for i, row in df_heures.iloc[::-1].head(5).iterrows():
            c_text, c_del = st.columns([4, 1])
            c_text.write(f"{row['date']} : {row['val']:.2f}h")
            if c_del.button("🗑️", key=f"del_h_{i}"):
                df_heures_raw = df_heures_raw.drop(i)
                conn.update(worksheet="Feuille 1", data=df_heures_raw)
                st.rerun()

with tab2:
    st.subheader("Ajouter un congé")
    c_date = st.date_input("Date du congé", value=datetime.now(), key="cong_date")
    c_type = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
    if st.button("Confirmer le congé", use_container_width=True):
        new_c = pd.DataFrame([{"date": c_date.strftime("%d/%m/%Y"), "type": 1.0 if c_type == "Journée" else 0.5}])
        updated_c = pd.concat([df_conges_raw, new_c], ignore_index=True)
        conn.update(worksheet="Conges", data=updated_c)
        st.rerun()

    st.divider()
    if not df_conges.empty:
        st.write("**Historique des congés :**")
        for i, row in df_conges.iloc[::-1].iterrows():
            ct, cd = st.columns([4, 1])
            label = "Journée" if row['type'] == 1.0 else "Demi"
            ct.write(f"📅 {row['date']} ({label})")
            if cd.button("🗑️", key=f"del_c_{i}"):
                df_conges_raw = df_conges_raw.drop(i)
                conn.update(worksheet="Conges", data=df_conges_raw)
                st.rerun()
