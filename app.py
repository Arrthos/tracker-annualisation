import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import holidays

# --- 1. CONFIGURATION ---
# IMPORTANT : L'identifiant ici doit être le même que celui dans la colonne 'user' du Sheets
USERS = {
    "Julien": {"password": "123", "base_sup": 20.5, "full_name": "Ton Prénom", "role": "admin"},
    "collegue1": {"password": "abc", "base_sup": 10.0, "full_name": "Jean Dupont", "role": "user"}
}

st.set_page_config(page_title="Work Tracker Team", layout="centered")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# --- 2. LOGIN ---
if not st.session_state.authenticated:
    st.title("🔐 Connexion")
    u_i = st.text_input("Identifiant")
    p_i = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if u_i in USERS and USERS[u_i]["password"] == p_i:
            st.session_state.authenticated = True
            st.session_state.user_key = u_i
            st.rerun()
    st.stop()

curr_user = st.session_state.user_key
u_info = USERS[curr_user]

# --- 3. CONNEXION ET LECTURE ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Lecture sans cache pour voir les modifs immédiates
    df_ajust_raw = conn.read(worksheet="Feuille 1", ttl=0).dropna(how='all')
    df_conges_raw = conn.read(worksheet="Conges", ttl=0).dropna(how='all')
except Exception as e:
    st.error(f"Erreur de lecture du Sheets : {e}")
    st.stop()

# --- 4. CALCULS ---
def calculate_for_user(uid, df_a, df_c):
    now = datetime.now()
    sy = now.year if now.month >= 9 else now.year - 1
    start_date = datetime(sy, 9, 1)
    ajd = now.replace(hour=23, minute=59)
    fr_h = holidays.France(years=[sy, sy + 1])
    
    # Vérification des colonnes
    if 'user' not in df_c.columns or 'user' not in df_a.columns:
        st.warning("⚠️ Attention : La colonne 'user' est introuvable dans le Google Sheets.")
        return 0.0, 0.0

    # Filtrage strict par utilisateur
    u_c = df_c[df_c['user'].astype(str) == str(uid)]
    u_a = df_a[df_a['user'].astype(str) == str(uid)]
    
    d_conges = {pd.to_datetime(row['date'], dayfirst=True).date(): float(row['type']) for _, row in u_c.iterrows()}

    theo = 0
    curr = start_date
    while curr <= ajd:
        d = curr.date()
        if curr.weekday() < 5:
            h_j = 7.5 if curr.weekday() <= 1 else 7.0
            if not (d in fr_h and d != date(sy+1, 6, 1)):
                theo += h_j * (1 - d_conges.get(d, 0))
        curr += timedelta(days=1)
    
    delta_s = u_a['val'].sum() if not u_a.empty else 0
    return USERS[uid]["base_sup"] + delta_s, theo

my_delta, my_theo = calculate_for_user(curr_user, df_ajust_raw, df_conges_raw)

# --- 5. INTERFACE ---
st.title(f"Salut {u_info['full_name']} !")
h_d, m_d = int(abs(my_delta)), int((abs(my_delta) - int(abs(my_delta))) * 60)
color = "#238636" if my_delta >= 0 else "#da3633"

st.markdown(f"<h1 style='text-align:center; color:{color}; font-size:4em;'>{'+' if my_delta >= 0 else '-'}{h_d}h{m_d:02d}</h1>", unsafe_allow_html=True)

t1, t2 = st.tabs(["⚡ Heures", "🌴 Congés"])

with t1:
    with st.form("form_heures"):
        col1, col2 = st.columns(2)
        a_t = col1.selectbox("Type", ["Plus (+)", "Moins (-)"])
        d_a = col2.date_input("Date", value=datetime.now())
        h_a = st.number_input("Heures", 0, 12, 0)
        m_a = st.number_input("Minutes", 0, 59, 0)
        submit_h = st.form_submit_button("Enregistrer l'heure")

    if submit_h:
        try:
            val = (h_a + m_a/60) * (-1 if "Moins" in a_t else 1)
            new_row = pd.DataFrame([{"user": curr_user, "date": d_a.strftime("%d/%m/%Y"), "val": val}])
            updated = pd.concat([df_ajust_raw, new_row], ignore_index=True)
            # On s'assure que les colonnes sont dans le bon ordre avant l'update
            conn.update(worksheet="Feuille 1", data=updated[['user', 'date', 'val']])
            st.success("✅ Enregistré !")
            st.rerun()
        except Exception as e:
            st.error(f"Erreur lors de l'enregistrement : {e}")

    # Historique
    u_h = df_ajust_raw[df_ajust_raw['user'] == curr_user] if 'user' in df_ajust_raw.columns else pd.DataFrame()
    if not u_h.empty:
        st.write("---")
        for i, row in u_h.iloc[::-1].head(5).iterrows():
            c_t, c_d = st.columns([4, 1])
            c_t.write(f"{row['date']} : {row['val']:+.2f}h")
            if c_d.button("🗑️", key=f"h_{i}"):
                conn.update(worksheet="Feuille 1", data=df_ajust_raw.drop(i)[['user', 'date', 'val']])
                st.rerun()

with t2:
    with st.form("form_conges"):
        c_d = st.date_input("Date", value=datetime.now())
        c_t = st.radio("Durée", ["Journée", "Demi"], horizontal=True)
        submit_c = st.form_submit_button("Enregistrer le congé")

    if submit_c:
        try:
            new_c = pd.DataFrame([{"user": curr_user, "date": c_d.strftime("%d/%m/%Y"), "type": 1.0 if c_t == "Journée" else 0.5}])
            updated_c = pd.concat([df_conges_raw, new_c], ignore_index=True)
            conn.update(worksheet="Conges", data=updated_c[['user', 'date', 'type']])
            st.success("✅ Congé enregistré !")
            st.rerun()
        except Exception as e:
            st.error(f"Erreur lors de l'enregistrement : {e}")

    u_c = df_conges_raw[df_conges_raw['user'] == curr_user] if 'user' in df_conges_raw.columns else pd.DataFrame()
    if not u_c.empty:
        st.write("---")
        for i, row in u_c.iloc[::-1].head(5).iterrows():
            c_t, c_d = st.columns([4, 1])
            label = "Jour" if row['type'] == 1.0 else "Demi"
            c_t.write(f"📅 {row['date']} ({label})")
            if c_d.button("🗑️", key=f"c_{i}"):
                conn.update(worksheet="Conges", data=df_conges_raw.drop(i)[['user', 'date', 'type']])
                st.rerun()
