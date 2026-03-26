import streamlit as st
import math
from fpdf import FPDF

# 1. Configurazione - SOLO COMANDI NATIVI
st.set_page_config(page_title="PolisEnergia Suite", layout="wide")

# 2. COSTANTI TECNICHE
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "PASS_BT_MT": 494.83, "DIST_FISSA": 209.62, 
    "DIST_EXTRA": 105.08, "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 452.72, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88 
}

# --- INTERFACCIA ---
st.title("POLIS ENERGIA")
st.caption("Configuratore Tecnico Fornitura 2026 - Versione Certificata")

# Input principali in colonne
c1, c2 = st.columns(2)

with c1:
    tipo_utenza = st.radio("Tipologia Utenza", ["Domestico", "Altri Usi"], horizontal=True)
    uso = st.selectbox("Regime Fiscale", ["IVA 10% (Domestico)", "IVA 22% (Business)", "P.A. (Split Payment)", "Esente"])
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    nome = st.text_input("Ragione Sociale / Intestatario").upper()

with c2:
    t_att = st.selectbox("Tensione Attuale", ["BT", "MT"])
    # Vincolo Domestico automatico
    op_t_new = ["BT"] if tipo_utenza == "Domestico" else ["BT", "MT"]
    t_new = st.selectbox("Tensione Richiesta", op_t_new)
    pod = st.text_input("Codice POD").upper()
    applica_gestione = st.checkbox("Applica Oneri Gestione (10%)", value=True)

st.write("---")

# --- LOGICA DI CALCOLO ---
p_att, p_new, dist_m, c_tec = 0.0, 0.0, 0, 0.0

if pratica == "Spostamento Misuratore":
    tipo_spost = st.radio("Distanza Spostamento", ["Entro 10m", "Oltre 10m"])
    c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in tipo_spost else TIC_2026["SPOST_OLTRE_10"]
    f_new = 1.0
else:
    col_p1, col_p2, col_p3 = st.columns(3)
    if "Nuova" not in pratica:
        p_att = col_p1.number_input("Potenza Attuale (kW)", min_value=0.0, value=3.0)
    p_new = col_p2.number_input("Potenza Richiesta (kW)", min_value=0.1, value=6.0)
    if pratica == "Nuova Connessione":
        dist_m = col_p3.number_input("Metri oltre i 200m", min_value=0)

    # Logica Limitatore (1.1 in BT fino a 30kW)
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

# IVA
is_split = "P.A." in uso
aliq = 0.10 if "10%" in uso else (0.22 if ("22%" in uso or is_split) else 0.0)
tot_finale = tot_imp if is_split else tot_imp * (1 + aliq)

# --- VISUALIZZAZIONE RISULTATI ---
res1, res2 = st.columns(2)

with res1:
    st.header("Riepilogo Costi")
    st.write(f"Potenza Disponibile: **{(p_new * f_new):.2f} kW**")
    st.write(f"Quota Tecnica TIC: {c_tec:.2f} €")
    st.write(f"Oneri Gestione: {c_gest:.2f} €")
    st.write(f"Istruttoria: {TIC_2026['ISTRUTTORIA']:.2f} €")

with res2:
    st.metric("TOTALE DA PAGARE", f"{tot_finale:.2f} €")
    if is_split:
        st.warning("REGIME SPLIT PAYMENT ATTIVO")
    
    if st.button("Genera Documento PDF"):
        if nome and pod:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "POLIS ENERGIA - PREVENTIVO 2026", ln=True, align='C')
            pdf.set_font("Helvetica", "", 12)
            pdf.ln(10)
            pdf.cell(0, 10, f"Cliente: {nome}", ln=True)
            pdf.cell(0, 10, f"POD: {pod}", ln=True)
            pdf.cell(0, 10, f"Pratica: {pratica}", ln=True)
            pdf.cell(0, 10, f"Potenza Disp: {p_new*f_new:.2f} kW", ln=True)
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, f"TOTALE DOVUTO: {tot_finale:.2f} EUR", ln=True)
            
            p_name = f"Preventivo_{pod}.pdf"
            pdf.output(p_name)
            with open(p_name, "rb") as f:
                st.download_button("Scarica PDF", f, file_name=p_name)
        else:
            st.error("Inserisci Nome e POD prima di generare!")
