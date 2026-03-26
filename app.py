import streamlit as st
import math, random, string
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="PolisEnergia Suite v66", layout="wide")

TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "PASS_BT_MT": 494.83, "DIST_FISSA": 209.62, 
    "DIST_EXTRA": 105.08, "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 452.72, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88 
}

DICITURA_LEGALE = (
    "L'esecuzione della prestazione è pertanto subordinata al verificarsi delle seguenti condizioni: "
    "1) conferma della proposta pervenuta entro 30 gg dalla presente richiesta; "
    "2) in caso di consegna della specifica tecnica, comunicazione dell'avvenuto completamento "
    "delle eventuali opere e/o concessioni, autorizzazioni, servitù a cura del cliente finale."
)

st.title("⚡ POLIS ENERGIA")
st.markdown("---")

# --- COLONNE INPUT ---
col1, col2 = st.columns(2)

with col1:
    uso = st.selectbox("Regime Fiscale", ["Domestico (IVA 10%)", "Altri Usi (IVA 22%)", "P.A. (Split Payment)", "Esente (IVA 0%)"])
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    nome = st.text_input("Intestatario / Ragione Sociale").upper()
    fornitura = st.text_input("Indirizzo Fornitura").upper()

with col2:
    t_att = st.selectbox("Tensione Attuale", ["BT (Bassa Tensione)", "MT (Media Tensione)"])
    # Vincolo Domestico -> Solo BT
    opzioni_t_new = ["BT (Bassa Tensione)"] if "Domestico" in uso else ["BT (Bassa Tensione)", "MT (Media Tensione)"]
    t_new = st.selectbox("Tensione Richiesta", opzioni_t_new)
    pod = st.text_input("Codice POD").upper()

# --- LOGICA PARAMETRI DINAMICI ---
st.markdown("### Dettagli Tecnici")
p_att, p_new, dist_m, tipo_spost = 0.0, 0.0, 0, ""

if pratica == "Spostamento Misuratore":
    tipo_spost = st.radio("Distanza dello spostamento", ["Entro 10 metri", "Oltre 10 metri (Sopralluogo)"])
else:
    c_p1, c_p2, c_p3 = st.columns(3)
    if "Nuova" not in pratica:
        p_att = c_p1.number_input("Potenza Attuale (kW)", min_value=0.0, step=0.5, value=3.0)
    p_new = c_p2.number_input("Nuova Potenza Richiesta (kW)", min_value=0.0, step=0.5, value=6.0)
    if pratica == "Nuova Connessione":
        dist_m = c_p3.number_input("Metri oltre i 200m", min_value=0, step=10)

# --- MOTORE DI CALCOLO ---
c_tec = 0.0
if pratica == "Spostamento Misuratore":
    c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in tipo_spost else TIC_2026["SPOST_OLTRE_10"]
else:
    # Scelta prezzo unitario TIC
    px = TIC_2026["MT"] if "MT" in t_new else (TIC_2026["DOM_LE6"] if ("Domestico" in uso and p_new <= 6) else TIC_2026["BT_ALTRI"])
    # Coefficiente 1.1 per BT fino a 34kW
    f = 1.0 if ("MT" in t_new or p_new > 34) else 1.1
    
    if pratica == "Nuova Connessione":
        c_tec = (p_new * f * px) + TIC_2026["DIST_FISSA"] + (math.ceil(dist_m/100) * TIC_2026["DIST_EXTRA"])
    else:
        # Aumento potenza = Differenza tra nuova e attuale
        c_tec = (max(0, p_new - p_att)) * f * px

c_pass = TIC_2026["PASS_BT_MT"] if ("BT" in t_att and "MT" in t_new) else 0

# CALCOLO GESTIONE: (Tecnica + Passaggio + 25.88) * 10%
c_gest = (c_tec + c_pass + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10

# IMPONIBILE: Tecnica + Passaggio + Gestione + Istruttoria (I 25.88 RESTANO FUORI)
tot_imp = c_tec + c_pass + c_gest + TIC_2026["ISTRUTTORIA"]

# IVA e SPLIT PAYMENT
is_split = "P.A." in uso
aliq = 0.22 if is_split else (0.10 if "10%" in uso else (0.22 if "22%" in uso else 0.0))
tot_iva = tot_imp * aliq
tot_finale = tot_imp if is_split else tot_imp + tot_iva

# --- AREA RISULTATI ---
st.markdown("---")
res_col1, res_col2 = st.columns([2, 1])

with res_col1:
    st.info(f"**RIEPILOGO COSTI:**\n\n"
            f"- Quota Tecnica TIC: {c_tec:.2f} €\n"
            f"- Passaggio Tensione: {c_pass:.2f} €\n"
            f"- Gestione PolisEnergia (10%): {c_gest:.2f} €\n"
            f"- Oneri Istruttoria: {TIC_2026['ISTRUTTORIA']:.2f} €")
    st.warning(f"**CONDIZIONI:** {DICITURA_LEGALE}")

with res_col2:
    st.metric("TOTALE DA PAGARE", f"{tot_finale:.2f} €")
    if is_split:
        st.caption(f"IVA ({int(aliq*100)}%) in Scissione dei Pagamenti (Split Payment)")
    else:
        st.caption(f"Include IVA al {int(aliq*100)}%")

# --- DOWNLOAD PDF (Base) ---
if st.button("Genera Documento PDF"):
    if not nome or not pod:
        st.error("Inserire Nome e POD per generare il PDF")
    else:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "PREVENTIVO POLIS ENERGIA", ln=True, align='C')
        pdf.set_font("Arial", "", 12)
        pdf.ln(10)
        pdf.cell(0, 10, f"Cliente: {nome}", ln=True)
        pdf.cell(0, 10, f"POD: {pod}", ln=True)
        pdf.cell(0, 10, f"Totale dovuto: {tot_finale:.2f} EUR", ln=True)
        pdf.ln(10)
        pdf.multi_cell(0, 10, f"Note legali: {DICITURA_LEGALE}")
        
        pdf_name = f"Preventivo_{pod}.pdf"
        pdf.output(pdf_name)
        with open(pdf_name, "rb") as f:
            st.download_button("Clicca qui per scaricare", f, file_name=pdf_name)
