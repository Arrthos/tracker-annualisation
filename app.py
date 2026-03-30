import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import holidays
import uuid
from supabase import create_client

# --- 1. CONFIG & CSS ---
st.set_page_config(page_title="Work Tracker Pro", layout="centered")

st.markdown("""
    <style>
    .stButton > button { width: 100% !important; border-radius: 10px !important; }
    div[data-testid="stHorizontalBlock"] { align-items: center !important; }
    .status-box { background: rgba(255,255,255,0.05); padding: 15px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 20px; }
    .ferie-tag { color: #f39c12; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = get_supabase()

@st.cache_data(ttl=3600)
def get_fr_holidays(years):
    return holidays.France(years=years)

def to_hm(decimal_hours):
    abs_h = abs(decimal_hours)
    h, m = int(abs_h), int(round((abs_h - int(abs_h)) * 60))
    if m == 60: h += 1; m = 0
    sign = "-" if decimal_hours < 0 else "+" if decimal_hours > 0 else ""
    return f"{sign}{h}h{m:02d}"

# --- 2. LOGIQUE DE CALCUL THÉORIQUE ---
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
    if not df_conges.empty:
        df_conges['dt_temp'] = pd.to_datetime(df_conges['date']).dt.date
        conges_map = df_conges.dropna(subset=['dt_temp']).set_index('dt_temp')['type'].to_dict()
        df_dates['conge_val'] = df_dates['date'].dt.date.map(conges_map).fillna(0)
        df_dates['h_theo'] *= (1 - df_dates['conge_val'])
    return df_dates['h_theo'].sum()

# --- 3. AUTHENTIFICATION ---
USERS = {"Julien": {"password": "%Gfpass115", "base_sup": 20.5}}
if 'authenticated' not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.form("login"):
        u = st.text_input("Utilisateur")
        p = st.text_input("Mots de passe", type="password")
        if st.form_submit_button("Connexion"):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.authenticated, st.session_state.user_key = True, u
                st.rerun()
    st.stop()

# --- 4. CHARGEMENT DONNÉES ---
curr_user = st.session_state.user_key
h_res = supabase.table("heures").select("*").eq("user", curr_user).execute()
c_res = supabase.table("conges").select("*").eq("user", curr_user).execute()
u_a = pd.DataFrame(h_res.data) if h_res.data else pd.DataFrame(columns=['id', 'date', 'val'])
u_c = pd.DataFrame(c_res.data) if c_res.data else pd.DataFrame(columns=['id', 'date', 'type', 'group_id'])

# --- 5. DASHBOARD & PROGRESSION ---
sol_date = date(2026, 6, 1)
my_theo = calculate_due_fast(u_c.copy(), sol_date)
val_ajust = u_a['val'].astype(float).sum() if not u_a.empty else 0
my_delta = USERS[curr_user]["base_sup"] + val_ajust
fait = my_theo + my_delta

st.title(f"Hello {curr_user}")

# Barre de progression rétablie
st.write(f"**Progression :** {to_hm(fait).replace('+','')} / 1652h")
st.progress(min(max(fait / 1652.0, 0.0), 1.0))

# Balance
color = "#238636" if my_delta >= 0 else "#da3633"
st.markdown(f'<h1 style="text-align:center; color:{color}; font-size:4em; margin-top:-10px;">{to_hm(my_delta)}</h1>', unsafe_allow_html=True)

# Agenda rétabli
today = datetime.now().date()
fr_h = get_fr_holidays([today.year])
posees = pd.to_datetime(u_c['date']).dt.date.tolist() if not u_c.empty else []

st.markdown("<div class='status-box'><b>📅 Agenda Prochaines Semaines</b>", unsafe_allow_html=True)
agenda_items = []
for i in range(21):
    d = today + timedelta(days=i)
    if d in fr_h: agenda_items.append(f"• {d.strftime('%d/%m')} : <span class='ferie-tag'>{fr_h.get(d)}</span>")
    if d in posees: agenda_items.append(f"• {d.strftime('%d/%m')} : 🌴 Congé")
if not agenda_items: st.write("Rien de prévu")
else: st.markdown("<br>".join(agenda_items[:5]), unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# --- 6. ONGLETS & SAISIE ---
tab1, tab2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with tab1:
    with st.expander("➕ Enregistrer des heures"):
        with st.form("h_f", clear_on_submit=True):
            typ = st.radio("Sens", ["Plus (+)", "Moins (-)"], horizontal=True)
            d = st.date_input("Date", date.today())
            c1, c2 = st.columns(2)
            hv, mv = c1.number_input("H", 0, 12, 0), c2.number_input("M", 0, 59, 0)
            if st.form_submit_button("Valider"):
                val = (hv + mv/60) * (-1 if "Moins" in typ else 1)
                supabase.table("heures").insert({"user": curr_user, "date": str(d), "val": val}).execute()
                st.rerun()
    
    for _, row in u_a.iloc[::-1].iterrows():
        c1, c2 = st.columns([0.8, 0.2])
        c1.write(f"**{pd.to_datetime(row['date']).strftime('%d/%m/%Y')}** : `{to_hm(row['val'])}`")
        if c2.button("🗑️", key=f"h_{row['id']}"):
            supabase.table("heures").delete().eq("id", row['id']).execute(); st.rerun()

with tab2:
    mode = st.toggle("Passer en mode Période (plusieurs jours)", value=False)
    with st.container(border=True):
        if not mode:
            st.subheader("📍 Jour unique")
            d_u = st.date_input("Jour", date.today())
            is_h = st.checkbox("Demi-journée")
            if st.button("Enregistrer le jour", type="primary"):
                if d_u.weekday() < 5:
                    supabase.table("conges").insert({"user": curr_user, "date": str(d_u), "type": 0.5 if is_h else 1.0, "group_id": str(uuid.uuid4())}).execute()
                    st.rerun()
                else: st.error("Week-end !")
        else:
            st.subheader("📅 Période")
            range_d = st.date_input("Début et fin", [date.today(), date.today()])
            if st.button("Enregistrer la période", type="primary"):
                if isinstance(range_d, list) and len(range_d) == 2:
                    g_id = str(uuid.uuid4())
                    dr = pd.date_range(range_d[0], range_d[1], freq='D').date
                    rows = [{"user": curr_user, "date": str(d), "type": 1.0, "group_id": g_id} for d in dr if d.weekday() < 5]
                    if rows: supabase.table("conges").insert(rows).execute(); st.rerun()

    st.subheader("Liste des congés")
    if not u_c.empty:
        u_c['dt'] = pd.to_datetime(u_c['date'])
        for gid, data in u_c.sort_values('dt', ascending=False).groupby('group_id', sort=False):
            c1, c2 = st.columns([0.8, 0.2])
            start, end = data['dt'].min(), data['dt'].max()
            lbl = f"Du {start.strftime('%d/%m/%Y')} au {end.strftime('%d/%m/%Y')}" if len(data) > 1 else f"Le {start.strftime('%d/%m/%Y')}"
            if len(data) == 1 and data.iloc[0]['type'] == 0.5: lbl += " (Demi)"
            c1.write(f"🌴 {lbl}")
            if c2.button("🗑️", key=f"g_{gid}"):
                supabase.table("conges").delete().eq("group_id", gid).execute(); st.rerun()
