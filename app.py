import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import calendar
import holidays
import uuid
from supabase import create_client, Client

# --- 1. CONFIGURATION & CSS DE FORCE BRUTE ---
# CSS agressif pour mobile : force l'alignement horizontal, réduit les marges
# et compacifie l'historique pour ne plus avoir de "vide".
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

st.markdown("""
    <style>
    /* Force l'alignement horizontal (corbeille sur la même ligne) */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: space-between !important;
        margin-bottom: -15px !important;
    }
    
    /* Réduit l'espace autour des boutons pour gagner de la place */
    .stButton > button {
        padding: 4px 12px !important;
        margin-top: 0px !important;
        border-radius: 8px !important;
    }
    
    /* Compactifie le texte des historiques */
    .stMarkdown p {
        margin-bottom: 0px !important;
        font-size: 0.9em !important;
    }
    
    /* Cache l'ancre Streamlit pour gagner de la place en haut */
    div.st-emotion-cache-1vt4uyj {
        padding-top: 1rem;
    }
    
    /* Style pour le Dashboard Agenda (Calendrier simplifié) */
    .cal-dashboard {
        background: rgba(255,255,255,0.03);
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 20px;
    }
    .cal-title { font-weight: bold; margin-bottom: 8px; color:white;}
    .cal-item { font-size: 0.85em; opacity: 0.8; color:white;}
    .conge-tag { color: #007bff; font-weight:bold; }
    .ferie-tag { color: #f39c12; font-weight:bold; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_supabase():
    # Utilisation des secrets configurés dans Streamlit Cloud
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = get_supabase()

@st.cache_data(ttl=3600)
def get_fr_holidays(years):
    return holidays.France(years=years)

def to_hm(decimal_hours):
    """Convertit des heures décimales en format string XhXX"""
    abs_h = abs(decimal_hours)
    h = int(abs_h)
    m = int(round((abs_h - h) * 60))
    if m == 60:
        h += 1
        m = 0
    sign = "-" if decimal_hours < 0 else ("+" if decimal_hours > 0 else "")
    return f"{sign}{h}h{m:02d}"

# --- 2. LOGIQUE DE CALCUL ---
def calculate_due_fast(df_conges, solidarity_day):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    
    dr = pd.date_range(start=start, end=now, freq='D')
    df_dates = pd.DataFrame({'date': dr})
    df_dates['weekday'] = df_dates['date'].dt.weekday
    df_dates = df_dates[df_dates['weekday'] < 5].copy()
    
    df_dates['h_theo'] = np.where(df_dates['weekday'] <= 1, 7.5, 7.0)
    
    fr_h = get_fr_holidays([sy, sy+1])
    df_dates['is_holiday'] = df_dates['date'].dt.date.apply(lambda x: x in fr_h and x != solidarity_day)
    df_dates.loc[df_dates['is_holiday'], 'h_theo'] = 0
    
    if not df_conges.empty and 'date' in df_conges.columns:
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date']).dt.date
        conges_map = df_conges.dropna(subset=['dt_temp']).set_index('dt_temp')['type'].to_dict()
        df_dates['conge_val'] = df_dates['date'].dt.date.map(conges_map).fillna(0)
        df_dates['h_theo'] *= (1 - df_dates['conge_val'])
        
    return df_dates['h_theo'].sum()

# --- 3. AUTHENTIFICATION ---
# Mots de passe sérieux pour la mise en service
USERS = {"Julien": {"password": "%Gfpass115", "base_sup": 20.5}}

if 'authenticated' not in st.session_state: 
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center; margin-bottom: 20px;'>🔐 Connexion</h1>", unsafe_allow_html=True)
    with st.form("login"):
        u_i = st.text_input("Identifiant")
        p_i = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Entrer", use_container_width=True):
            if u_i in USERS and USERS[u_i]["password"] == p_i:
                st.session_state.authenticated, st.session_state.user_key = True, u_i
                st.rerun()
    st.stop()

# --- 4. CHARGEMENT DES DONNÉES ---
curr_user = st.session_state.user_key

def fetch_data():
    h_res = supabase.table("heures").select("*").eq("user", curr_user).execute()
    c_res = supabase.table("conges").select("*").eq("user", curr_user).execute()
    # Protection tables vides KeyError
    df_h = pd.DataFrame(h_res.data) if h_res.data else pd.DataFrame(columns=['id', 'user', 'date', 'val'])
    df_c = pd.DataFrame(c_res.data) if c_res.data else pd.DataFrame(columns=['id', 'user', 'date', 'type', 'group_id'])
    return df_h, df_c

u_a, u_c = fetch_data()

# --- 5. PARAMÈTRES & CALCULS DASHBOARD ---
# Date fixe de solidarité (à changer en sidebar si besoin)
sol_date = date(2026, 6, 1)

my_theo = calculate_due_fast(u_c.copy(), sol_date)
val_ajust = u_a['val'].astype(float).sum() if not u_a.empty else 0
my_delta = USERS[curr_user]["base_sup"] + val_ajust
fait = my_theo + my_delta
objectif = 1652.0

# --- 6. DASHBOARD CENTRALISÉ (AVANT LES ONGLETS) ---
st.markdown(f"<h1 style='text-align: center; margin-bottom: 20px;'>Hello {curr_user}</h1>", unsafe_allow_html=True)

# Barre de progression
fait_str = to_hm(fait).replace("+", "")
st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: -5px;">
        <p style="margin: 0; font-weight: bold; color: white;">Progression annuelle</p>
        <p style="margin: 0; opacity: 0.8; color: white;"><b>{fait_str}</b> / {int(objectif)}h</p>
    </div>
""", unsafe_allow_html=True)
st.progress(min(max(fait / objectif, 0.0), 1.0))

# Bloc Balance (toujours visible)
balance_str = to_hm(my_delta)
color_delta = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f"""
    <div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:15px; text-align:center; border:2px solid {color_delta}; margin: 15px 0 20px 0;">
        <p style="margin:0; opacity:0.6; font-size:0.8em; color:white;">BALANCE</p>
        <h1 style="color:{color_delta}; font-size:3.5em; margin:5px 0;">{balance_str}</h1>
    </div>
""", unsafe_allow_html=True)

# --- NOUVEAU : DASBOARD AGENDA (CALENDRIER ROBUSTE MOBILE) ---
# Ce bloc remplace la grille de calendrier visuelle par un agenda écrit incassable
today = datetime.now()
end_agenda = today + timedelta(days=21) # Affiche les 3 prochaines semaines
posees_dates = pd.to_datetime(u_c['date']).dt.date.tolist() if not u_c.empty else []
fr_h = get_fr_holidays([today.year])

agenda_html = f"<div class='cal-dashboard'><div class='cal-title'>📅 Agenda Prochaines Semaines</div>"
events_found = False
for i in range((end_agenda - today).days + 1):
    day = today.date() + timedelta(days=i)
    txt_day = day.strftime("%d/%m")
    
    # Événement Congés
    if day in posees_dates:
        agenda_html += f"<div class='cal-item'>• {txt_day} : <span class='conge-tag'>Congé</span></div>"
        events_found = True
    # Événement Férié
    elif day in fr_h:
        ferie_name = fr_h.get(day)
        agenda_html += f"<div class='cal-item'>• {txt_day} : <span class='ferie-tag'>{ferie_name}</span></div>"
        events_found = True

if not events_found:
    agenda_html += "<div class='cal-item' style='opacity:0.5;'>Aucun événement prévu.</div>"

st.markdown(agenda_html + "</div>", unsafe_allow_html=True)


# --- 7. ONGLETS DE SAISIE ---
tab1, tab2 = st.tabs(["⚡ Heures supp", "🌴 Congés"])

with tab1:
    @st.fragment
    def section_heures():
        with st.expander("➕ Enregistrer des heures"):
            with st.form("h_form", clear_on_submit=True):
                typ = st.radio("Type", ["Plus (+)", "Moins (-)"], horizontal=True)
                dat = st.date_input("Date", value=date.today())
                c1, c2 = st.columns(2)
                h_v, m_v = c1.number_input("H", 0, 12, 0), c2.number_input("M", 0, 59, 0)
                if st.form_submit_button("Valider", use_container_width=True):
                    val = (h_v + m_v/60) * (-1 if "Moins" in typ else 1)
                    supabase.table("heures").insert({"user": curr_user, "date": str(dat), "val": val}).execute()
                    st.rerun()
        
        st.subheader("🗑️ Historique Heures")
        if u_a.empty: st.info("Aucune heure enregistrée.")
        else:
            # Tri par date inverse
            for _, row in u_a.iloc[::-1].iterrows():
                col_text, col_btn = st.columns([0.85, 0.15])
                date_fmt = pd.to_datetime(row['date']).strftime("%d/%m/%Y")
                col_text.write(f"**{date_fmt}** : `{to_hm(row['val'])}`")
                if col_btn.button("🗑️", key=f"h_{row['id']}"):
                    supabase.table("heures").delete().eq("id", row['id']).execute()
                    st.rerun()
    section_heures()

with tab2:
    @st.fragment
    def section_conges():
        with st.expander("➕ Poser un congé / une période"):
            with st.form("c_form", clear_on_submit=True):
                # Réintégration multi-dates pour les périodes
                sel_dates = st.date_input("Date ou Période", value=[date.today()])
                t_v = st.radio("Durée par jour", ["Journée", "Demi"], horizontal=True)
                val_c = 1.0 if t_v == "Journée" else 0.5
                
                if st.form_submit_button("Confirmer", use_container_width=True):
                    # Génération group_id unique pour la période
                    g_id = str(uuid.uuid4())
                    
                    if isinstance(sel_dates, (list, tuple)) and len(sel_dates) > 1:
                        # Cas période
                        dates_to_add = pd.date_range(start=sel_dates[0], end=sel_dates[1], freq='D').date
                    else:
                        # Cas jour unique
                        dates_to_add = [sel_dates[0] if isinstance(sel_dates, (list, tuple)) else sel_dates]
                    
                    # Insertion masse sans week-ends
                    new_rows = [{"user": curr_user, "date": str(d), "type": val_c, "group_id": g_id} for d in dates_to_add if d.weekday() < 5]
                    
                    if new_rows:
                        supabase.table("conges").insert(new_rows).execute()
                        st.rerun()

        st.subheader("🗑️ Liste des congés")
        if u_c.empty: st.info("Aucun congé.")
        else:
            # GROUPEMENT PAR GROUP_ID POUR AFFICHAGE PROPRE
            u_c['dt_obj'] = pd.to_datetime(u_c['date'])
            # Tri pour avoir les plus récents en haut
            groups = u_c.sort_values('dt_obj', ascending=False).groupby('group_id', sort=False)
            
            for g_id, data in groups:
                col_text_c, col_btn_c = st.columns([0.85, 0.15])
                start_f = data['dt_obj'].min().strftime("%d/%m/%Y")
                end_f = data['dt_obj'].max().strftime("%d/%m/%Y")
                
                if len(data) > 1:
                    lbl = f"Du **{start_f}** au **{end_f}**"
                else:
                    lbl = f"Le **{start_f}**"
                
                col_text_c.write(f"🌴 {lbl}")
                
                # SUPPRESSION DE TOUT LE GROUPE D'UN COUP
                if col_btn_c.button("🗑️", key=f"g_{g_id}"):
                    supabase.table("conges").delete().eq("group_id", g_id).execute()
                    st.rerun()
    section_conges()

# --- 8. DÉCONNEXION ---
if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()
