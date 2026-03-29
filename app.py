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

# --- 2. CONFIGURATION DE L'ICÔNE ET THÈME ---
icon_url = "https://raw.githubusercontent.com/Arrthos/tracker-annualisation/main/image_11.png?v=5"
st.markdown(f'<head><link rel="apple-touch-icon" href="{icon_url}"><link rel="icon" href="{icon_url}"></head>', unsafe_allow_html=True)

if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

# --- 3. STYLE CSS ---
dark_css = """
    .stApp { background: radial-gradient(circle at center, #1a2a40 0%, #0d1117 100%); background-attachment: fixed; }
    .main-card { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(20px); padding: 30px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; margin-bottom: 25px; }
    .stat-label { color: rgba(255, 255, 255, 0.6); font-size: 0.9em; }
    .stat-value { color: white; font-size: 1.8em; font-weight: bold; }
    .reward-text { color: #3fb950; font-weight: bold; font-size: 1.2em; }
"""
light_css = """
    .stApp { background-color: #FAF5F0; }
    .main-card { background: rgba(208, 225, 249, 0.8); backdrop-filter: blur(15px); padding: 30px; border-radius: 30px; border: 1px solid rgba(255, 255, 255, 0.4); text-align: center; margin-bottom: 25px; }
    .stat-label { color: #4A5568; font-size: 0.9em; }
    .stat-value { color: #1A202C; font-size: 1.8em; font-weight: bold; }
    .reward-text { color: #2D3748; font-weight: bold; font-size: 1.2em; }
"""
active_css = dark_css if st.session_state.theme == 'dark' else light_css
st.markdown(f"<style>{active_css} .stButton>button {{ border-radius: 6px; font-weight: bold; }}</style>", unsafe_allow_html=True)

# --- 4. LOGIQUE DE CALCUL ---
conn = st.connection("gsheets", type=GSheetsConnection)

now = datetime.now()
start_year = now.year if now.month >= 9 else now.year - 1
date_debut_saison = datetime(start_year, 9, 1)
date_fin_saison = datetime(start_year + 1, 8, 31)

with st.sidebar:
    st.button("🌓 Switch Mode", on_click=toggle_theme, use_container_width=True)
    st.info(f"Saison active : {start_year}-{start_year+1}")
    date_solidarite = st.date_input("Journée de Solidarité", value=date(start_year + 1, 6, 1))

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
    df = df.copy()
    df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True)
    mask = (df['date_dt'] >= start_date) & (df['date_dt'] <= end_date)
    return df.loc[mask].drop(columns=['date_dt'])

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
        <h1 style="color: {color}; font-size: 3.5em; margin: 10px 0;">
            {'+' if delta >= 0 else '-'}{h_delta}h {m_delta:02d}
        </h1>
        {f'<p class="reward-text">≃ {jours_repos:.1f} jours de repos</p>' if delta > 0 else ''}
    </div>
    """, unsafe_allow_html=True)

# --- 7. ONGLETS ---
tab_h, tab_c = st.tabs(["🕒 Saisie Heures", "🌴 Gestion Congés"])

with tab_h:
    today_wd = datetime.now().weekday()
    std_h, std_m = (7, 30) if today_wd <= 1 else (7, 0)
    
    if st.button(f"Valider journée standard ({std_h}h{std_m:02d})", use_container_width=True):
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
            c_t, c_b = st.columns([4, 1])
            c_t.write(f"{row['date']} | {row['val']:.2f}h")
            if c_b.button("🗑️", key=f"del_h_{i}"):
                df_heures_raw = df_heures_raw.drop(i)
                conn.update(worksheet="Feuille 1", data=df_heures_raw)
                st.rerun()

with tab_c:
    st.subheader("Déclarer une absence")
    date_abs = st.date_input("Date du congé", value=datetime.now())
    type_abs = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
    
    if st.button("Enregistrer le congé", use_container_width=True):
        new_c = pd.DataFrame([{"date": date_abs.strftime("%d/%m/%Y"), "type": 1.0 if type_abs == "Journée" else 0.5}])
        updated_c = pd.concat([df_conges_raw, new_c], ignore_index=True)
        conn.update(worksheet="Conges", data=updated_c)
        st.rerun()

    st.divider()
    if not df_conges.empty:
        st.write("**Congés enregistrés (Saison) :**")
        for i, row in df_conges.iloc[::-1].iterrows():
            c_t, c_b = st.columns([4, 1])
            txt = "Journée" if row['type'] == 1.0 else "Demi-journée"
            c_t.write(f"📅 {row['date']} ({txt})")
            if c_b.button("🗑️", key=f"del_c_{i}"):
                # On supprime la ligne correspondante dans le fichier global
                df_conges_raw = df_conges_raw.drop(i)
                conn.update(worksheet="Conges", data=df_conges_raw)
                st.rerun()
