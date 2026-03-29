import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta

# --- CONFIGURATION ET STYLE CSS (DOUBLE THEME + SOBRE) ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

st.markdown("""
    <style>
    /* --- THEME SOMBRE (Dark Modern) par défaut --- */
    .stApp { background-color: #0d1117; }
    
    .main-card {
        background-color: #161b22;
        padding: 30px;
        border-radius: 12px;
        border: 1px solid #30363d;
        text-align: center;
        margin-bottom: 25px;
    }
    .stat-label { color: #8b949e; font-size: 0.9em; margin-bottom: 5px; }
    .stat-value { color: white; font-size: 1.8em; font-weight: bold; }
    .reward-text { color: #3fb950; font-weight: bold; font-size: 1.2em; }
    .progress-label { color: white; font-weight: bold; }
    
    .stButton>button { border-radius: 6px; font-weight: bold; border: 1px solid transparent; }
    /* Style bouton Standard */
    .stButton>button[key="std_btn"] { background-color: #238636; color: white; }
    
    /* Style de la barre de progression (Verte) */
    .stProgress > div > div > div > div { background-color: #238636; }
    
    /* Style Onglets */
    .stTabs [data-baseweb="tab-list"] { background-color: transparent; border-bottom: 1px solid #30363d; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; }
    .stTabs [data-baseweb="tab"]:hover { color: white; }
    
    /* --- AJUSTEMENTS POUR THEME LUMINEUX (Soft Pastel) --- */
    /* Streamlit Cloud change automatiquement 'data-theme' en 'light' */
    @media (prefers-color-scheme: light) {
        .stApp { background-color: #FAF5F0; }
        .main-card {
            background-color: #D0E1F9; /* Pastel Bleu */
            border-radius: 30px; /* Coins très arrondis */
            border: none;
            box-shadow: 0px 4px 15px rgba(0,0,0,0.05); /* Ombres douces */
        }
        .stat-label { color: #5c6c7c; }
        .stat-value { color: #2e3b47; }
        .reward-text { color: #A8E6CF; /* Pastel Menthe */ }
        .progress-label { color: #2e3b47; }
        
        .stButton>button[key="std_btn"] { background-color: #A8E6CF; color: #2e3b47; }
        .stProgress > div > div > div > div { background-color: #A8E6CF; }
        
        .stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #D0E1F9; }
        .stTabs [data-baseweb="tab"] { color: #5c6c7c; }
        .stTabs [data-baseweb="tab"]:hover { color: #2e3b47; }
    }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- LOGIQUE DE SAISON AUTOMATIQUE ---
now = datetime.now()
start_year = now.year if now.month >= 9 else now.year - 1
date_debut_saison = datetime(start_year, 9, 1)
date_fin_saison = datetime(start_year + 1, 8, 31)

st.sidebar.info(f"Saison active : {start_year}-{start_year+1}")

# --- CALCUL DU DÛ DYNAMIQUE ---
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
            if d in feries: pass
            elif d in dict_conges: total += h_jour * (1 - dict_conges[d])
            else: total += h_jour
        curr += timedelta(days=1)
    return total

# --- RÉCUPÉRATION ET FILTRAGE DES DONNÉES ---
df_heures_raw = conn.read(worksheet="Feuille 1", ttl=0)
df_conges_raw = conn.read(worksheet="Conges", ttl=0)

def filter_by_season(df, start_date, end_date):
    if df.empty: return df
    df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True)
    mask = (df['date_dt'] >= start_date) & (df['date_dt'] <= end_date)
    return df.loc[mask].drop(columns=['date_dt'])

df_heures = filter_by_season(df_heures_raw, date_debut_saison, date_fin_saison)
df_conges = filter_by_season(df_conges_raw, date_debut_saison, date_fin_saison)

# NOTE : La BASE_FAIT de 992.25h ne s'applique qu'à la saison 2025-2026
current_base = 992.25 if start_year == 2025 else 0.0
OBJECTIF_ANNUEL = 1607.0

theo = get_theo(df_conges, date_debut_saison)
total_saisi = df_heures['val'].sum() if not df_heures.empty else 0
fait = current_base + total_saisi
delta = fait - theo
jours_repos = delta / 7.2 if delta > 0 else 0

# --- INTERFACE ---
progression = min(fait / OBJECTIF_ANNUEL, 1.0)
st.markdown(f'<p class="progress-label">Progression Annuelle : {int(fait)}h / {int(OBJECTIF_ANNUEL)}h</p>', unsafe_allow_html=True)
st.progress(progression)

st.markdown("### Annualisation")
color = "#238636" if delta >= 0 else "#da3633"
h_delta = int(abs(delta))
m_delta = int((abs(delta) - h_delta) * 60)

st.markdown(f"""
    <div class="main-card">
        <p style="color: #8b949e; font-size: 0.9em;">Situation Actuelle</p>
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

# --- ONGLETS ---
tab_h, tab_c = st.tabs(["Saisie Heures", "Gestion Congés"])

with tab_h:
    today_wd = datetime.now().weekday()
    std_h, std_m = (7, 30) if today_wd <= 1 else (7, 0)
    
    if st.button(f"Valider journée standard ({std_h}h{std_m:02d})", use_container_width=True, type="primary", key="std_btn"):
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
        st.write("**Dernières saisies (Saison) :**")
        for i, row in df_heures.iloc[::-1].head(5).iterrows():
            col_t, col_b = st.columns([4, 1])
            col_t.write(f"Date : {row['date']} | Durée : {row['val']:.2f}h")
            if col_b.button("Suppr.", key=f"del_h_{i}"):
                df_heures_raw = df_heures_raw.drop(df_heures_raw[df_heures_raw['date'] == row['date']].index)
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
