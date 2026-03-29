import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta

# --- CONFIGURATION INITIALE ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

# --- CONFIGURATION DE L'ICÔNE MOBILE (HEAD HTML) ---
# Utilisation du lien "Raw" de ton GitHub pour l'image_11.png
icon_url = "https://raw.githubusercontent.com/Arrthos/tracker-annualisation/main/image_11.png"

st.markdown(f"""
    <head>
        <link rel="apple-touch-icon" href="{icon_url}">
        <link rel="icon" href="{icon_url}">
    </head>
    """, unsafe_allow_html=True)

# --- GESTION DU THEME ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

with st.sidebar:
    st.button("Switch Mode (Clair/Sombre)", on_click=toggle_theme, use_container_width=True)
    st.markdown("<style>.stButton>button { box-shadow: 0px 2px 5px rgba(0,0,0,0.1); }</style>", unsafe_allow_html=True)

# --- CSS DYNAMIQUE ET GLASSY ---
dark_css = """
    .stApp { background: radial-gradient(circle at center, #1a2a40 0%, #0d1117 100%); background-attachment: fixed; }
    .main-card {
        background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        padding: 30px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1);
        text-align: center; margin-bottom: 25px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    .stat-label { color: rgba(255, 255, 255, 0.6); font-size: 0.9em; }
    .stat-value { color: white; font-size: 1.8em; font-weight: bold; }
    .reward-text { color: #3fb950; font-weight: bold; font-size: 1.2em; }
    .progress-label { color: white; font-weight: bold; }
    h3 { color: white !important; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; }
    .stButton>button[key="std_btn"] { background-color: #238636; color: white; box-shadow: 0px 4px 10px rgba(0,0,0,0.3); }
    .stProgress > div > div > div > div { background-color: #238636; }
"""

light_css = """
    .stApp { background-color: #FAF5F0; }
    .main-card {
        background: rgba(208, 225, 249, 0.8); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
        padding: 30px; border-radius: 30px; border: 1px solid rgba(255, 255, 255, 0.4);
        text-align: center; margin-bottom: 25px; box-shadow: 0px 6px 20px rgba(0,0,0,0.08);
    }
    .stat-label { color: #4A5568; font-size: 0.9em; }
    .stat-value { color: #1A202C; font-size: 1.8em; font-weight: bold; }
    .reward-text { color: #2D3748; font-weight: bold; font-size: 1.2em; }
    .progress-label { color: #2D3748; font-weight: bold; }
    h3 { color: #2D3748 !important; }
    .stTabs [data-baseweb="tab"] { color: #4A5568 !important; }
    .stButton>button[key="std_btn"] { background-color: #8FD9BF; color: #1A202C; box-shadow: 0px 4px 10px rgba(0,0,0,0.1); }
    .stProgress > div > div > div > div { background-color: #8FD9BF; }
"""

active_css = dark_css if st.session_state.theme == 'dark' else light_css

st.markdown(f"<style>{active_css} .stButton>button {{ border-radius: 6px; font-weight: bold; }}</style>", unsafe_allow_html=True)

# --- CONNEXION ET CALCULS ---
conn = st.connection("gsheets", type=GSheetsConnection)

now = datetime.now()
start_year = now.year if now.month >= 9 else now.year - 1
date_debut_saison = datetime(start_year, 9, 1)
date_fin_saison = datetime(start_year + 1, 8, 31)

with st.sidebar:
    st.info(f"Saison active : {start_year}-{start_year+1}")

def get_theo(df_conges, start_date):
    hier = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total, curr = 0, start_date
    dict_conges = {}
    if not df_conges.empty:
        for _, row in df_conges.iterrows():
            try:
                d_val = row['date']
                d_obj = pd.to_datetime(d_val, dayfirst=True).date() if isinstance(d_val, str) else d_val.date()
                dict_conges[d_obj] = float(row['type'])
            except: continue
    feries = [date(start_year,11,11), date(start_year,12,25), date(start_year+1,1,1), date(start_year+1,5,1)]
    while curr < hier:
        d = curr.date()
        if curr.weekday() < 5:
            h_jour = 7.5 if curr.weekday() <= 1 else 7.0
            if d not in feries:
                if d in dict_conges: total += h_jour * (1 - dict_conges[d])
                else: total += h_jour
        curr += timedelta(days=1)
    return total

df_heures_raw = conn.read(worksheet="Feuille 1", ttl=0)
df_conges_raw = conn.read(worksheet="Conges", ttl=0)

def filter_by_season(df, start_date, end_date):
    if df.empty: return df
    df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True)
    mask = (df['date_dt'] >= start_date) & (df['date_dt'] <= end_date)
    return df.loc[mask].drop(columns=['date_dt'])

df_heures = filter_by_season(df_heures_raw, date_debut_saison, date_fin_saison)
df_conges = filter_by_season(df_conges_raw, date_debut_saison, date_fin_saison)

current_base = 992.25 if start_year == 2025 else 0.0
OBJECTIF_ANNUEL = 1607.0

theo = get_theo(df_conges, date_debut_saison)
total_saisi = df_heures['val'].sum() if not df_heures.empty else 0
fait = current_base + total_saisi
delta = fait - theo
jours_repos = delta / 7.2 if delta > 0 else 0

# --- AFFICHAGE ---
prog = min(fait / OBJECTIF_ANNUEL, 1.0)
st.markdown(f'<p class="progress-label">Progression Annuelle : {int(fait)}h / {int(OBJECTIF_ANNUEL)}h</p>', unsafe_allow_html=True)
st.progress(prog)

st.markdown("### Annualisation")
color = "#238636" if delta >= 0 else "#da3633"
h_delta, m_delta = int(abs(delta)), int((abs(delta) - int(abs(delta))) * 60)

st.markdown(f"""
    <div class="main-card">
        <p class="stat-label">Situation Actuelle</p>
        <h1 style="color: {color}; font-size: 4em; margin: 10px 0;">
            {'+' if delta >= 0 else '-'}{h_delta}h {m_delta:02d}
        </h1>
        {f'<p class="reward-text">Équivalent à {jours_repos:.1f} jours de repos</p>' if delta > 0 else ''}
    </div>
    """, unsafe_allow_html=True)

c1, c2 = st.columns(2)
c1.markdown(f'<p class="stat-label">FAIT (Saison)</p><p class="stat-value">{fait:.2f}h</p>', unsafe_allow_html=True)
c2.markdown(f'<p class="stat-label">DÛ (Saison)</p><p class="stat-value">{theo:.2f}h</p>', unsafe_allow_html=True)

st.divider()

tab_h, tab_c = st.tabs(["Saisie Heures", "Gestion Congés"])

with tab_h:
    today_wd = datetime.now().weekday()
    std_h, std_m = (7, 30) if today_wd <= 1 else (7, 0)
    if st.button(f"Valider journée standard ({std_h}h{std_m:02d})", use_container_width=True, key="std_btn"):
        new_row = pd.DataFrame([{"date": datetime.now().strftime("%d/%m/%Y"), "val": std_h + std_m/60}])
        updated = pd.concat([df_heures_raw, new_row], ignore_index=True)
        conn.update(worksheet="Feuille 1", data=updated)
        st.rerun()

    with st.expander("Saisie précise"):
        h_in = st.number_input("Heures", min_value=0, step=1, value=std_h)
        m_in = st.number_input("Minutes", min_value=0, max_value=59, step=1, value=std_m)
        if st.button("Enregistrer précisément", use_container_width=True):
            new_row = pd.DataFrame([{"date": datetime.now().strftime("%d/%m/%Y"), "val": h_in + m_in/60}])
            updated = pd.concat([df_heures_raw, new_row], ignore_index=True)
            conn.update(worksheet="Feuille 1", data=updated)
            st.rerun()

    if not df_heures.empty:
        st.write("**Dernières saisies :**")
        for i, row in df_heures.iloc[::-1].head(5).iterrows():
            col_t, col_b = st.columns([4, 1])
            col_t.write(f"Date : {row['date']} | {row['val']:.2f}h")
            if col_b.button("Suppr.", key=f"del_h_{i}"):
                idx_to_drop = df_heures_raw[df_heures_raw['date'] == row['date']].index
                df_heures_raw = df_heures_raw.drop(idx_to_drop)
                conn.update(worksheet="Feuille 1", data=df_heures_raw)
                st.rerun()

with tab_c:
    st.subheader("Déclarer un congé")
    date_abs = st.date_input("Date", value=datetime.now())
    type_abs = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
    if st.button("Enregistrer l'absence", use_container_width=True):
        new_c = pd.DataFrame([{"date": date_abs.strftime("%d/%m/%Y"), "type": 1.0 if type_abs == "Journée" else 0.5}])
        updated_c = pd.concat([df_conges_raw, new_c], ignore_index=True)
        conn.update(worksheet="Conges", data=updated_c)
        st.rerun()
