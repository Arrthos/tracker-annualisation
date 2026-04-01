import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import holidays
import uuid
from supabase import create_client
import base64
import os

# --- 1. CONFIGURATION & SESSION STATE ---
# Doit être la toute première commande Streamlit
st.set_page_config(page_title="Annualisation Gamba Rota", layout="centered")

# Initialisation critique des variables de session (si l'app redémarre)
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_key' not in st.session_state:
    st.session_state.user_key = None
if 'solidarity_date' not in st.session_state:
    # Par défaut pour la journée travaillée
    st.session_state.solidarity_date = date(2026, 5, 25)

# --- 2. CSS DESIGN (Amélioré pour mobile) ---
design_css = """
    <style>
    .stApp { background-color: #000000 !important; color: #EAEAEA; }
    header {visibility: hidden;}
    
    /* Carte Balance des Heures */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px;
        border-radius: 24px;
        text-align: center;
        backdrop-filter: blur(15px);
        margin: 15px 0;
    }

    /* Texte de la Balance (Heures:Minutes) */
    .balance-val { font-size: 5rem; font-weight: 800; letter-spacing: -3px; margin: 5px 0; line-height: 1; }
    .pos { color: #2ECC71; } /* Vert si positif */
    .neg { color: #FF4B4B; } /* Rouge si négatif */

    /* Texte de conversion en jours de récup */
    .recup-text {
        font-size: 1.1rem;
        color: #9BA1B0;
        margin-top: 10px;
        font-weight: 500;
    }

    /* NOUVELLE ALERTE FÉRIÉ INTUITIVE */
    .holiday-alert {
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(255, 75, 75, 0.1); /* Fond rouge très léger */
        color: #FF4B4B; /* Texte rouge vif */
        padding: 10px;
        border-radius: 12px;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 20px;
        border: 1px solid rgba(255, 75, 75, 0.3);
    }
    .holiday-icon { font-size: 1.2rem; margin-right: 8px; }

    /* Barre de progression */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #3498DB, #2ECC71);
        height: 10px;
        border-radius: 5px;
    }

    /* Lignes d'historique (Heures et Congés) */
    .history-row {
        background: rgba(255,255,255,0.03); 
        padding: 10px; 
        border-radius: 10px; 
        display: flex; 
        align-items: center;
        height: 48px;
        margin-bottom: 4px;
        font-size: 0.9rem;
    }
    
    /* Ajustement des boutons pour mobile */
    div[data-testid="column"] button {
        height: 48px !important;
        margin-top: 0px !important;
    }
    </style>
"""
st.markdown(design_css, unsafe_allow_html=True)

# --- 3. FONCTIONS LOGIQUES ---
@st.cache_resource
def get_supabase(): 
    # Récupère l'URL et la clé anonyme depuis les secrets de Streamlit Cloud
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

@st.cache_data(ttl=3600)
def get_fr_holidays(years): 
    # Utilise la bibliothèque holidays pour la France
    return holidays.France(years=years)

def to_hm(decimal_hours):
    # Convertit les heures décimales (ex: 2.5) en format heures:minutes (ex: +2h30)
    abs_h = abs(decimal_hours)
    h, m = int(abs_h), int(round((abs_h - int(abs_h)) * 60))
    if m == 60: h += 1; m = 0
    return f"{'-' if decimal_hours < 0 else '+'}{h}h{m:02d}"

def calculate_metrics(df_conges, solidarity_day):
    # Calcule les heures théoriques de la période (01/09 au 'maintenant')
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start = datetime(sy, 9, 1)
    
    # Plage de jours ouvrés
    dr = pd.date_range(start=start, end=now, freq='D')
    df = pd.DataFrame({'date': dr})
    df['wd'] = df['date'].dt.weekday
    df = df[df['wd'] < 5].copy() # On garde Lundi à Vendredi
    
    # Heures théoriques par défaut (L-M: 7.5h, M-J-V: 7.0h)
    df['h_theo'] = np.where(df['wd'] <= 1, 7.5, 7.0)
    
    # Gestion des fériés de la période
    fr_h = get_fr_holidays([sy, sy+1])
    # Le férié est théorique à 0h sauf si c'est la journée travaillée
    df['is_h'] = df['date'].dt.date.apply(lambda x: x in fr_h and x != solidarity_day)
    df.loc[df['is_h'], 'h_theo'] = 0
    
    # Gestion des congés posés (on soustrait les heures théoriques)
    if not df_conges.empty:
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date']).dt.date
        c_map = df_conges.groupby('dt_temp')['type'].sum().to_dict()
        df['c_val'] = df['date'].dt.date.map(c_map).fillna(0)
        # On s'assure de ne pas avoir d'heures négatives
        df['h_theo'] = np.maximum(0, df['h_theo'] * (1 - df['c_val']))
    
    return df['h_theo'].sum()

def load_img(path):
    # Charge et convertit une image locale en base64 pour l'affichage HTML
    if os.path.exists(path):
        with open(path, "rb") as f: 
            return base64.b64encode(f.read()).decode()
    return None

# --- 4. AUTHENTIFICATION ---
# Chargement critique depuis les Secrets
try:
    USERS = st.secrets["users"]
    supabase = get_supabase()
except Exception as e:
    st.error(f"Erreur critique de configuration (Secrets manquants ou mal formés ?) : {e}")
    st.stop()

# Écran de connexion si pas authentifié
if not st.session_state.authenticated:
    img_base64 = load_img("image_11.png") # Ton logo/image de fond
    if img_base64:
        st.markdown(f'<div style="display:flex;justify-content:center;margin-top:40px;"><img src="data:image/png;base64,{img_base64}" width="160"></div>', unsafe_allow_html=True)
    
    with st.form("login"):
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Connexion", use_container_width=True):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.authenticated = True
                st.session_state.user_key = u
                st.rerun() # Rafraîchit l'app pour afficher le dashboard
            else:
                st.error("Identifiant ou mot de passe incorrect")
    st.stop() # Arrête le script ici si pas connecté

# --- 5. CHARGEMENT & CALCULS ---
curr_user = st.session_state.user_key
user_config = USERS[curr_user] # La configuration (contrat, base_sup) depuis les secrets

# Récupération en direct depuis Supabase
try:
    h_data = supabase.table("heures").select("*").eq("user", curr_user).execute().data
    c_data = supabase.table("conges").select("*").eq("user", curr_user).execute().data
except Exception as e:
    st.error(f"Erreur lors de la récupération des données Supabase : {e}")
    st.stop()

# Création des DataFrames (avec colonnes de sécurité si vide)
u_a = pd.DataFrame(h_data) if h_data else pd.DataFrame(columns=['id', 'date', 'val'])
u_c = pd.DataFrame(c_data) if c_data else pd.DataFrame(columns=['id', 'date', 'type', 'group_id'])

# Calculs de la balance
du = calculate_metrics(u_c.copy(), st.session_state.solidarity_date)
h_sup_total = u_a['val'].astype(float).sum() if not u_a.empty else 0
delta = user_config["base_sup"] + h_sup_total
fait = du + delta
h_contrat = user_config["contrat"]

# Calcul d'estimation des jours de récup (sur une base moyenne de 7.2h)
jours_recup = delta / 7.2

# --- 6. DASHBOARD PRINCIPAL ---
st.markdown(f"<p style='text-align:center; color:#9BA1B0; margin-bottom:0;'>Bonjour,</p><h2 style='text-align:center; margin-top:0;'>{curr_user}</h2>", unsafe_allow_html=True)

# Barre de progression et texte associé
st.markdown(f"<p style='text-align:center; margin-bottom:5px;'><small>Progression : <b>{int(fait)}</b> / {h_contrat}h</small></p>", unsafe_allow_html=True)
st.progress(min(max(fait / float(h_contrat), 0.0), 1.0))

# Carte de Balance Heures Supp (GLASS-CARD)
status_color = "pos" if delta >= 0 else "neg"
recup_subtext = f'✨ Soit environ <b>{jours_recup:.1f}</b> jours de récup' if delta > 0 else '☕ Pas encore de récup possible'

st.markdown(f"""
    <div class="glass-card">
        <small style="color:#9BA1B0">BALANCE HEURES SUP.</small>
        <div class="balance-val {status_color}">{to_hm(delta)}</div>
        <div class="recup-text">{recup_subtext}</div>
    </div>
""", unsafe_allow_html=True)

# --- 7. NOUVEAU : ALERTE FÉRIÉ INTUITIVE (15 jours) ---
# Récupération des fériés FR pour l'année en cours + suivante
fr_h = get_fr_holidays([datetime.now().year, datetime.now().year + 1])
badges = []
today = date.today()

# On parcourt les fériés triés par date
for d_h, name in sorted(fr_h.items()):
    # Si le férié est aujourd'hui ou dans les 15 jours à venir
    if today <= d_h <= (today + timedelta(days=15)):
        date_formatted = d_h.strftime("%d/%m/%Y")
        badges.append(f'<span class="holiday-badge">{date_formatted} : {name}</span>')

# Affichage de l'alerte si au moins un férié est trouvé
if badges:
    badges_html = " ".join(badges)
    st.markdown(f'<div class="holiday-alert"><span class="holiday-icon">📅</span> Prochainement : {badges_html}</div>', unsafe_allow_html=True)

st.write("---") # Ligne de séparation

# --- 8. PARAMÈTRES ---
with st.expander("⚙️ Paramètres & Solidarité"):
    st.caption("Initialisé au : 01 septembre")
    new_sol = st.date_input("Journée de solidarité :", st.session_state.solidarity_date)
    if new_sol != st.session_state.solidarity_date:
        # Rafraîchit si la date de solidarité change pour recalculer les théoriques
        st.session_state.solidarity_date = new_sol
        st.rerun()

# --- 9. ONGLETS DE SAISIE ---
t1, t2 = st.tabs(["⚡ Heures supp", "🌴 Congés / Arret"])

# Onglet Heures Supp
with t1:
    with st.expander("➕ Enregistrer des heures"):
        with st.form("h_form", clear_on_submit=True):
            typ = st.radio("Sens", ["Plus (+)", "Moins (-)"], horizontal=True)
            d = st.date_input("Date", date.today())
            h_col, m_col = st.columns(2)
            hv = h_col.number_input("H", 0, 12, 0)
            mv = m_col.number_input("M", 0, 59, 0)
            if st.form_submit_button("Valider", use_container_width=True):
                val = (hv + mv/60) * (-1 if "Moins" in typ else 1)
                supabase.table("heures").insert({"user": curr_user, "date": str(d), "val": val}).execute()
                st.rerun() # Rafraîchit pour voir l'entrée dans l'historique
    
    # Historique des Heures Supp
    if not u_a.empty:
        for _, row in u_a.sort_values('date', ascending=False).iterrows():
            c1, c2 = st.columns([0.8, 0.2])
            with c1:
                # Texte aligné
                date_formatted = pd.to_datetime(row['date']).strftime('%d/%m/%Y')
                st.markdown(f"<div class='history-row'>📅 {date_formatted} : &nbsp;<b>{to_hm(row['val'])}</b></div>", unsafe_allow_html=True)
            with c2:
                # Bouton de suppression aligné
                if st.button("🗑️", key=f"h_{row['id']}", use_container_width=True):
                    supabase.table("heures").delete().eq("id", row['id']).execute()
                    st.rerun()

# Onglet Congés
with t2:
    mode_p = st.toggle("Mode Période", value=False)
    if not mode_p:
        # Mode Jounée Unique
        d_u = st.date_input("Jour", date.today())
        half = st.checkbox("Demi-journée")
        if st.button("Enregistrer le jour", use_container_width=True):
            if d_u.weekday() < 5: # Uniquement Lundi-Vendredi
                supabase.table("conges").insert({"user": curr_user, "date": str(d_u), "type": 0.5 if half else 1.0, "group_id": str(uuid.uuid4())}).execute()
                st.rerun()
    else:
        # Mode Période
        cs, ce = st.columns(2)
        ds = cs.date_input("Début", date.today())
        de = ce.date_input("Fin", date.today() + timedelta(days=1))
        if st.button("Enregistrer la période", use_container_width=True):
            gid = str(uuid.uuid4())
            days = pd.date_range(ds, de, freq='D').date
            # On ne garde que les jours ouvrés
            rows = [{"user": curr_user, "date": str(day), "type": 1.0, "group_id": gid} for day in days if day.weekday() < 5]
            if rows:
                supabase.table("conges").insert(rows).execute()
                st.rerun()

    # Historique des Congés
    if not u_c.empty:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        # Groupe par l'identifiant unique de période
        for gid, data in u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False):
            c1, c2 = st.columns([0.8, 0.2])
            s, e = data['dt'].min(), data['dt'].max()
            
            # Libellé adaptable (jour unique ou période)
            if len(data) > 1:
                lbl = f"{s.strftime('%d/%m/%Y')} → {e.strftime('%d/%m/%Y')}"
            else:
                lbl = f"{s.strftime('%d/%m/%Y')}"
            
            # Mention de demi-journée
            if len(data) == 1 and data.iloc[0]['type'] == 0.5:
                lbl += " (1/2)"
            
            with c1:
                st.markdown(f"<div class='history-row'>🌴 {lbl}</div>", unsafe_allow_html=True)
            with c2:
                if st.button("🗑️", key=f"g_{gid}", use_container_width=True):
                    supabase.table("conges").delete().eq("group_id", gid).execute()
                    st.rerun()
