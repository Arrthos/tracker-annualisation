import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import holidays  # Bibliothèque pour les jours fériés

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Work Tracker Pro",
    page_icon="https://raw.githubusercontent.com/Arrthos/tracker-annualisation/main/image_11.png",
    layout="centered"
)

# --- 2. GESTION DU THÈME ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

# --- 3. LOGIQUE DE SAISON ET SOLIDARITÉ ---
now = datetime.now()
# Saison commence au 1er Septembre
start_year = now.year if now.month >= 9 else now.year - 1
date_debut_saison = datetime(start_year, 9, 1)
date_fin_saison = datetime(start_year + 1, 8, 31)

with st.sidebar:
    st.button("🌓 Switch Mode", on_click=toggle_theme, use_container_width=True)
    st.divider()
    st.info(f"Saison active : {start_year}-{start_year+1}")
    
    # CHOIX DE LA JOURNÉE DE SOLIDARITÉ
    st.subheader("Paramètres")
    date_solidarite = st.date_input(
        "Journée de Solidarité", 
        value=date(start_year + 1, 6, 9), # Par défaut Lundi de Pentecôte 2026 par ex.
        help="Cette date sera considérée comme travaillée (non fériée) dans le calcul du temps dû."
    )

# --- 4. CALCULS DES HEURES DUES ---
def get_theo(df_conges, start_date, date_solidarite):
    hier = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total, curr = 0, start_date
    
    # Récupération auto des jours fériés pour les deux années de la saison
    fr_holidays = holidays.France(years=[start_year, start_year + 1])
    
    # Transformation des congés en dictionnaire pour accès rapide
    dict_conges = {}
    if not df_conges.empty:
        for _, row in df_conges.iterrows():
            try:
                d_val = row['date']
                d_obj = pd.to_datetime(d_val, dayfirst=True).date() if isinstance(d_val, str) else d_val.date()
                dict_conges[d_obj] = float(row['type'])
            except: continue

    while curr < hier:
        d = curr.date()
        if curr.weekday() < 5: # Lundi à Vendredi
            # 7.5h Lun-Mar, 7.0h Mer-Jeu-Ven (Total 36h)
            h_jour = 7.5 if curr.weekday() <= 1 else 7.0
            
            # Un jour est dû si : ce n'est pas un férié OU si c'est la journée de solidarité
            est_ferie_chome = (d in fr_holidays) and (d != date_solidarite)
            
            if not est_ferie_chome:
                if d in dict_conges:
                    total += h_jour * (1 - dict_conges[d])
                else:
                    total += h_jour
        curr += timedelta(days=1)
    return total

# --- 5. CONNEXION ET TRAITEMENT ---
conn = st.connection("gsheets", type=GSheetsConnection)

def filter_by_season(df, start_date, end_date):
    if df.empty: return df
    df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True)
    mask = (df['date_dt'] >= start_date) & (df['date_dt'] <= end_date)
    return df.loc[mask].drop(columns=['date_dt'])

df_heures_raw = conn.read(worksheet="Feuille 1", ttl=0)
df_conges_raw = conn.read(worksheet="Conges", ttl=0)

df_heures = filter_by_season(df_heures_raw, date_debut_saison, date_fin_saison)
df_conges = filter_by_season(df_conges_raw, date_debut_saison, date_fin_saison)

# Paramètres de base
OBJECTIF_ANNUEL = 1652.0
current_base = 992.25 if start_year == 2025 else 0.0 # À ajuster selon tes archives

theo = get_theo(df_conges, date_debut_saison, date_solidarite)
total_saisi = df_heures['val'].sum() if not df_heures.empty else 0
fait = current_base + total_saisi
delta = fait - theo
jours_repos = delta / 7.2 if delta > 0 else 0

# --- 6. INTERFACE (STYLE CSS ET AFFICHAGE) ---
# ... (Garder tes styles CSS actifs ici) ...

st.markdown(f"### Progression Annuelle : {int(fait)}h / {int(OBJECTIF_ANNUEL)}h")
st.progress(min(fait / OBJECTIF_ANNUEL, 1.0))

color = "#238636" if delta >= 0 else "#da3633"
h_delta, m_delta = int(abs(delta)), int((abs(delta) - int(abs(delta))) * 60)

st.markdown(f"""
    <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 15px; text-align: center; border: 1px solid rgba(255,255,255,0.1);">
        <p style="margin:0; opacity:0.7;">Balance (Annualisation)</p>
        <h1 style="color: {color}; font-size: 3.5em; margin: 10px 0;">
            {'+' if delta >= 0 else '-'}{h_delta}h {m_delta:02d}
        </h1>
        {f'<p style="color:#3fb950;">≃ {jours_repos:.1f} jours de repos</p>' if delta > 0 else ''}
    </div>
    """, unsafe_allow_html=True)

# --- 7. ONGLETS ET SAISIE ---
# (Le reste du code de saisie reste identique à ta version précédente)
