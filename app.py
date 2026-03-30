import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
from datetime import datetime, date
import holidays

# --- 1. CONFIGURATION & CACHE ---
st.set_page_config(page_title="Work Tracker Pro 2026", layout="centered")

@st.cache_data(ttl=3600) # On cache la liste des jours fériés pour 1h
def get_fr_holidays(years):
    return holidays.France(years=years)

# --- 2. LOGIQUE MÉTIER VECTORISÉE (Gain de performance ++ ) ---
def calculate_due_fast(df_conges, solidarity_day):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    
    # Création d'un range de dates complet jusqu'à aujourd'hui
    dr = pd.date_range(start=start, end=now, freq='D')
    df_dates = pd.DataFrame({'date': dr})
    df_dates['weekday'] = df_dates['date'].dt.weekday
    
    # Filtrer les week-ends (0-4 = Lun-Ven)
    df_dates = df_dates[df_dates['weekday'] < 5].copy()
    
    # Attribution des heures théoriques
    # Lun, Mar (0,1) = 7.5h | Mer, Jeu, Ven (2,3,4) = 7.0h
    df_dates['h_theo'] = np.where(df_dates['weekday'] <= 1, 7.5, 7.0)
    
    # Gestion jours fériés (excluant solidarité)
    fr_h = get_fr_holidays([sy, sy+1])
    df_dates['is_holiday'] = df_dates['date'].dt.date.apply(lambda x: x in fr_h and x != solidarity_day)
    df_dates.loc[df_dates['is_holiday'], 'h_theo'] = 0
    
    # Mapping des congés (plus rapide que la boucle)
    if not df_conges.empty:
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date'], dayfirst=True).dt.date
        conges_map = df_conges.set_index('dt_temp')['type'].to_dict()
        df_dates['conge_val'] = df_dates['date'].dt.date.map(conges_map).fillna(0)
        df_dates['h_theo'] *= (1 - df_dates['conge_val'])
        
    return df_dates['h_theo'].sum()

# --- 3. CONNEXION & AUTH ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False

# (Le bloc de connexion reste identique, on passe à l'essentiel)
# ... [Code connexion simplifié pour l'exemple] ...
if not st.session_state.authenticated:
    # ... (ton code de login précédent)
    st.session_state.authenticated = True # Bypass pour démo
    st.session_state.user_key = "Julien"

# --- 4. DATA LOADING ---
conn = st.connection("gsheets", type=GSheetsConnection)
# On ne lit qu'une fois au début
df_a = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
df_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')

curr_user = st.session_state.user_key
u_a = df_a[df_a['user'] == curr_user]
u_c = df_c[df_c['user'] == curr_user]

# --- 5. DASHBOARD (STATIQUE & RAPIDE) ---
sol_date = st.sidebar.date_input("Journée de Solidarité", value=date(2024, 5, 20))
my_theo = calculate_due_fast(u_c.copy(), sol_date)
my_delta = 20.5 + (u_a['val'].sum() if not u_a.empty else 0)
fait = my_theo + my_delta

st.title(f"Hello {curr_user}")
# ... [Tes blocs HTML de dashboard restent ici car ils sont légers] ...

# --- 6. FRAGMENTS (LA MAGIE DE 2026) ---
# En isolant ces fonctions, cliquer sur "Ajouter" ne recharge pas tout le dashboard

@st.fragment
def form_heures():
    with st.expander("➕ Enregistrer des heures"):
        with st.form("h_form", clear_on_submit=True):
            typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
            dat = st.date_input("Date", value=date.today())
            c_h, c_m = st.columns(2)
            h_s = c_h.number_input("Heures", 0, 12, 0)
            m_s = c_m.number_input("Minutes", 0, 59, 0)
            if st.form_submit_button("Valider"):
                val = (h_s + m_s/60) * (-1 if "Moins" in typ else 1)
                new = pd.DataFrame([{"user": curr_user, "date": dat.strftime("%d/%m/%Y"), "val": val}])
                latest = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
                conn.update(worksheet="Feuille 1", data=pd.concat([latest, new]))
                st.rerun()

@st.fragment
def form_conges():
    with st.expander("➕ Poser un congé"):
        with st.form("c_form", clear_on_submit=True):
            d_c = st.date_input("Date", value=date.today())
            t_c = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
            if st.form_submit_button("Confirmer"):
                v_c = 1.0 if t_c == "Journée" else 0.5
                new_c = pd.DataFrame([{"user": curr_user, "date": d_c.strftime("%d/%m/%Y"), "type": v_c}])
                latest_c = conn.read(worksheet="Conges", ttl=0).dropna(how='all')
                conn.update(worksheet="Conges", data=pd.concat([latest_c, new_c]))
                st.rerun()

# Affichage des onglets
t1, t2 = st.tabs(["⚡ Heures", "🌴 Congés"])
with t1:
    form_heures()
    # ... historique ...
with t2:
    form_conges()
    # ... calendrier ...
