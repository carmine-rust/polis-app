import streamlit as st
import math
from fpdf import FPDF

# 1. Configurazione Iniziale
st.set_page_config(page_title="PolisEnergia Suite", page_icon="⚡", layout="wide")

# 2. Iniezione Font LATO e Stile Polis
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&display=swap');
    
    /* Applica Lato a tutto l'applicativo */
    html, body, [class*="css"], .stText, .stMarkdown, p, h1, h2, h3, label {
        font-family: 'Lato', sans-serif !important;
    }
    
    .stApp { background-color: #001d3d; color: white; }
    
    /* Personalizzazione Input */
    div[data-baseweb="select"] > div, input { 
        background-color: #0a1a2f !important; 
        color: white !important; 
        border: 1px solid #00b4d8 !important;
    }
    
    /* Titoli in Azzurro Polis */
    h1, h2, h3 { color: #00b4d8 !important; font-weight: 700; }
    
    /* Bottoni Professionali */
    .stButton>button {
        background-color: #00b4d8;
        color: #001d3d;
        border-radius: 5px;
        font-weight: 700;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: white;
        color: #003566;
    }
    </style>
    """, unsafe_content_allowed=True)

# 3. Costanti TIC 2026
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "PASS_BT_MT": 494.83, "DIST_FISSA": 209.62, 
    "DIST_EXTRA": 105.08, "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 452.72, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88 
}

# --- INTERFACCIA ---
st.title("⚡ POLIS ENERGIA")
st.caption("Configuratore Tecnico Fornitura 2026 | Font: Lato")
st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Configurazione Cliente")
    tipo_utenza = st.radio("Tipologia Utenza", ["Domestico", "Altri Usi"], horizontal=True)
    uso = st.selectbox("Regime Fiscale / IVA", ["IVA 10% (Domestico)", "IVA 22% (Business)", "P.A. (Split Payment)", "Esente"])
    nome = st.text_input("Ragione Sociale / Intestatario").upper()
    pod = st.text_input("Codice POD").upper()

with col2:
    st.subheader("Parametri Tecnici")
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    t_att = st.selectbox("Tensione Attuale", ["BT", "MT"])
    op_t_new = ["BT"] if tipo_utenza == "Domestico" else ["BT", "MT"]
    t_new = st.selectbox("Tensione Richiesta", op_t_new)
    applica_gestione = st.checkbox("Applica Oneri Gestione (10%)", value=True)

# --- MOTORE DI CALCOLO ---
p_att, p_new, dist_m, c_tec = 0.0, 0.0, 0, 0.0

if pratica == "Spostamento Misuratore":
    tipo_spost = st.radio("Distanza dello spostamento", ["Entro 10 metri", "Oltre 10 metri"])
    c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in tipo_spost else TIC_2026["SPOST_OLTRE_10"]
    f_new = 1.0
else:
    cp1, cp2, cp3 = st.columns(3)
    if "Nuova" not in pratica:
        p_att = cp1.number_input("Potenza Attuale (kW)", min_value=0.0, value=3.0)
    p_new = cp2.number_input("Potenza Richiesta (kW)", min_value=0.1, value=6.0)
    if pratica == "Nuova Connessione":
        dist_m = cp3.number_input("Metri oltre i 200m", min_value=0)

    # Logica Pd (Limitatore 1.1 in BT <= 30kW)
    f_new = 1.1 if (t_new == "BT" and p_new <= 30) else 1.0
    f_att = 1.1 if (t_att == "BT" and p_att <= 30) else 1.0
    
    # Prezzo unitario TIC
    px = TIC_2026["MT"] if t_new == "MT" else (TIC_2026["DOM_LE6"] if (tipo_utenza == "Domestico" and p_new <= 6) else TIC_2026["BT_ALTRI"])
    
    if pratica == "Nuova Connessione":
        c_tec = (p_new * f_new * px) + TIC_2026["DIST_FISSA"] + (math.ceil(dist_m/100) * TIC_2026["DIST_EXTRA"])
    else:
        c_tec = max(0.0, (p_new * f_new) - (p_att * f_att)) * px

c_pass = TIC_2026["PASS_BT_MT"] if (t_att == "BT" and t_new == "MT") else 0
c_gest = (c_tec + c_pass + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if applica_gestione else 0.0
tot_imp = c_tec + c_pass + c_gest + TIC_2026["ISTRUTTORIA"]

is_split = "P.A." in uso
aliq = 0.10 if "10%" in uso else (0.22 if ("22%" in uso or is_split) else 0.0)
tot_finale = tot_imp if is_split else tot_imp * (1 + aliq)

# --- VISUALIZZAZIONE RISULTATI ---
st.divider()
r1, r2 = st.columns([2, 1])

with r1:
    st.markdown("### Riepilogo Costi")
    st.write(f"📊 Potenza Disponibile: **{(p_new * f_new):.2f} kW**")
    st.write(f"💶 Quota Tecnica TIC: **{c_tec:.2f} €**")
    st.write(f"🏢 Gestione PolisEnergia: **{c_gest:.2f} €**")
    st.write(f"📄 Istruttoria: **{TIC_2026['ISTRUTTORIA']:.2f} €**")

with r2:
    st.metric("TOTALE FINALE", f"{tot_finale:.2f} €")
    if is_split: st.info("REGIME SPLIT PAYMENT")
    
    if st.button("GENERA PDF UFFICIALE"):
        if nome and pod:
            pdf = FPDF()
            pdf.add_page()
            # Nota: FPDF standard usa font core (Helvetica), 
            # Per Lato nel PDF servirebbe caricare il file .ttf, ma Helvetica è un ottimo sostituto "pulito"
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "POLIS ENERGIA - PREVENTIVO", ln=True, align='C')
            pdf.set_font("Helvetica", "", 12)
            pdf.ln(10)
            pdf.cell(0, 10, f"Intestatario: {nome} | POD: {pod}", ln=True)
            pdf.cell(0, 10, f"Potenza Contrattuale: {p_new} kW", ln=True)
            pdf.cell(0, 10, f"Totale da Pagare: {tot_finale:.2f} EUR", ln=True)
            
            p_name = f"Prev_{pod}.pdf"
            pdf.output(p_name)
            with open(p_name, "rb") as f:
                st.download_button("SCARICA IL PDF", f, file_name=p_name)
