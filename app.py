import streamlit as st
import math, random, string
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="PolisEnergia Suite v69", page_icon="⚡", layout="wide")

# --- STILE CSS PERSONALIZZATO (Senza variabili f-string per evitare errori) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&display=swap');
    
    /* Font Globale */
    html, body, [class*="css"] { font-family: 'Lato', sans-serif !important; }
    
    /* Sfondo App */
    .stApp { background-color: #001d3d; color: #ffffff; }
    
    /* Sidebar e Input */
    [data-testid="stSidebar"] { background-color: #000814; }
    div[data-baseweb="select"] > div, input { 
        background-color: #0a1a2f !important; 
        color: white !important; 
        border: 1px solid #00b4d8 !important;
    }
    
    /* Card Risultati */
    .result-card {
        background: linear-gradient(135deg, #003566 0%, #001d3d 100%);
        padding: 25px;
        border-radius: 15px;
        border: 1px solid #00b4d8;
        box-shadow: 0 4px 15px rgba(0, 180, 216, 0.2);
        margin-bottom: 20px;
    }
    
    /* Bottoni */
    .stButton>button {
        background-color: #00b4d8;
        color: #001d3d;
        font-weight: bold;
        border-radius: 10px;
        border: none;
        transition: 0.3s;
        width: 100%;
        height: 3em;
    }
    .stButton>button:hover {
        background-color: #ffffff;
        color: #003566;
        transform: translateY(-2px);
    }
    
    /* Header */
    h1, h2, h3 { color: #00b4d8 !important; }
    .stMetric label { color: #ffffff !important; }
    .stMetric [data-testid="stMetricValue"] { color: #00b4d8 !important; font-weight: 700; }
</style>
""", unsafe_content_allowed=True)

# --- DATI E LOGICA (Invariati per precisione tecnica) ---
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "PASS_BT_MT": 494.83, "DIST_FISSA": 209.62, 
    "DIST_EXTRA": 105.08, "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 452.72, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88 
}

DICITURA_LEGALE = (
    "L'esecuzione della prestazione è subordinata a: 1) conferma entro 30 gg; "
    "2) completamento eventuali opere civili a cura del cliente. La potenza calcolata ai fini TIC "
    "include la franchigia del 10% (limitatore) ove previsto da normativa ARERA."
)

# --- HEADER APP ---
st.title("⚡ POLIS ENERGIA")
st.subheader("Configuratore Tecnico Fornitura 2026")
st.markdown("---")

# --- LAYOUT INPUT ---
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### Anagrafica e Fisco")
    tipo_utenza = st.radio("Tipologia Utenza", ["Domestico", "Altri Usi"], horizontal=True)
    uso = st.selectbox("Regime Fiscale / IVA", ["IVA 10% (Domestico)", "IVA 22% (Business)", "P.A. (Split Payment)", "Esente (IVA 0%)"])
    nome = st.text_input("Intestatario / Ragione Sociale").upper()
    pod = st.text_input("Codice POD").upper()

with col_right:
    st.markdown("### Configurazione Tecnica")
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    t_att = st.selectbox("Tensione Attuale", ["BT (Bassa Tensione)", "MT (Media Tensione)"])
    
    if tipo_utenza == "Domestico":
        t_new = "BT (Bassa Tensione)"
        st.caption("Nota: Utenze domestiche limitate a BT.")
    else:
        t_new = st.selectbox("Tensione Richiesta", ["BT (Bassa Tensione)", "MT (Media Tensione)"])
    
    applica_gestione = st.checkbox("Applica Oneri Gestione Pratica (10%)", value=True)

# --- CALCOLI (Logica Pd vs Pc) ---
st.markdown("---")
p_att, p_new, dist_m, tipo_spost = 0.0, 0.0, 0, ""

if pratica == "Spostamento Misuratore":
    tipo_spost = st.radio("Distanza dello spostamento", ["Entro 10 metri", "Oltre 10 metri"])
    c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in tipo_spost else TIC_2026["SPOST_OLTRE_10"]
    f_new = 1.0
else:
    c_p1, c_p2, c_p3 = st.columns(3)
    if "Nuova" not in pratica:
        p_att = c_p1.number_input("Potenza Attuale (kW)", min_value=0.0, value=3.0)
    p_new = c_p2.number_input("Potenza Richiesta (kW)", min_value=0.0, value=6.0)
    if pratica == "Nuova Connessione":
        dist_m = c_p3.number_input("Metri oltre 200m", min_value=0)

    # Logica Pd
    f_new = 1.1 if ("BT" in t_new and p_new <= 30) else 1.0
    f_att = 1.1 if ("BT" in t_att and p_att <= 30) else 1.0
    px = TIC_2026["MT"] if "MT" in t_new else (TIC_2026["DOM_LE6"] if (tipo_utenza == "Domestico" and p_new <= 6) else TIC_2026["BT_ALTRI"])
    
    if pratica == "Nuova Connessione":
        c_tec = (p_new * f_new * px) + TIC_2026["DIST_FISSA"] + (math.ceil(dist_m/100) * TIC_2026["DIST_EXTRA"])
    else:
        c_tec = max(0.0, (p_new * f_new) - (p_att * f_att)) * px

c_pass = TIC_2026["PASS_BT_MT"] if ("BT" in t_att and "MT" in t_new) else 0
c_gest = (c_tec + c_pass + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if applica_gestione else 0.0
tot_imp = c_tec + c_pass + c_gest + TIC_2026["ISTRUTTORIA"]

is_split = "P.A." in uso
aliq = 0.10 if "10%" in uso else (0.22 if ("22%" in uso or is_split) else 0.0)
tot_finale = tot_imp if is_split else tot_imp * (1 + aliq)

# --- RISULTATI ESTETICI ---
res_left, res_right = st.columns([2, 1])

with res_left:
    st.markdown(f"""
    <div class="result-card">
        <h3>Riepilogo Preventivo</h3>
        <p>Potenza Disponibile Calcolata: <b>{(p_new * f_new):.2f} kW</b></p>
        <p>Quota Tecnica TIC: {c_tec:.2f} €</p>
        <p>Gestione PolisEnergia (10%): {c_gest:.2f} €</p>
        <p>Oneri Istruttoria: {TIC_2026['ISTRUTTORIA']:.2f} €</p>
        <hr style="border: 0.5px solid #00b4d8;">
        <p style="font-size: 0.9em; opacity: 0.8;">{DICITURA_LEGALE}</p>
    </div>
    """, unsafe_content_allowed=True)

with res_right:
    st.metric("TOTALE DA PAGARE", f"{tot_finale:.2f} €")
    if is_split: st.error("REGIME SPLIT PAYMENT")
    else: st.success(f"IVA {int(aliq*100)}% INCLUSA")
    
    if st.button("🚀 GENERA PDF"):
        if not nome or not pod:
            st.warning("Inserire Nome e POD!")
        else:
            # Semplice generazione PDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "PREVENTIVO POLIS ENERGIA", ln=True, align='C')
            pdf.set_font("Helvetica", "", 12)
            pdf.ln(10)
            pdf.cell(0, 10, f"Cliente: {nome} | POD: {pod}", ln=True)
            pdf.cell(0, 10, f"Totale: {tot_finale:.2f} EUR", ln=True)
            pdf_name = f"Prev_{pod}.pdf"
            pdf.output(pdf_name)
            with open(pdf_name, "rb") as f:
                st.download_button("SCARICA IL FILE", f, file_name=pdf_name)
