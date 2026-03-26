import streamlit as st
import math
from fpdf import FPDF

# 1. SETUP - SOLO COMANDI NATIVI (ZERO ERRORE)
st.set_page_config(page_title="PolisEnergia Suite", page_icon="⚡", layout="wide")

# 2. COSTANTI TIC 2026 (Aggiornate)
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "PASS_BT_MT": 494.83, "DIST_FISSA": 209.62, 
    "DIST_EXTRA": 105.08, "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 452.72, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88 
}

# --- INTERFACCIA ---
st.title("⚡ POLIS ENERGIA")
st.subheader("Configuratore Tecnico Fornitura 2026")
st.info("Logica Limitatore ARERA (Pd 1.1) Attiva")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📋 Dati Pratica")
    tipo_utenza = st.radio("Tipologia Utenza", ["Domestico", "Altri Usi"], horizontal=True)
    uso = st.selectbox("Regime Fiscale / IVA", ["IVA 10% (Domestico)", "IVA 22% (Business)", "P.A. (Split Payment)", "Esente"])
    nome = st.text_input("Intestatario / Ragione Sociale").upper()
    pod = st.text_input("Codice POD (14 cifre)").upper()

with col2:
    st.markdown("### ⚙️ Parametri Tecnici")
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    t_att = st.selectbox("Tensione Attuale", ["BT (Bassa)", "MT (Media)"])
    
    # Vincolo Domestico/BT
    op_t_new = ["BT (Bassa)"] if tipo_utenza == "Domestico" else ["BT (Bassa)", "MT (Media)"]
    t_new = st.selectbox("Tensione Richiesta", op_t_new)
    applica_gestione = st.checkbox("Applica Oneri Gestione Polis (10%)", value=True)

# --- MOTORE DI CALCOLO ---
st.divider()
p_att, p_new, dist_m, c_tec = 0.0, 0.0, 0, 0.0

if pratica == "Spostamento Misuratore":
    tipo_sp = st.radio("Distanza dello spostamento", ["Entro 10 metri", "Oltre 10 metri"])
    c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in tipo_sp else TIC_2026["SPOST_OLTRE_10"]
    f_new = 1.0
else:
    c_p1, c_p2, c_p3 = st.columns(3)
    if "Nuova" not in pratica:
        p_att = c_p1.number_input("Potenza Attuale (kW)", min_value=0.0, value=3.0, step=0.5)
    p_new = c_p2.number_input("Nuova Potenza Richiesta (kW)", min_value=0.1, value=6.0, step=0.5)
    if pratica == "Nuova Connessione":
        dist_m = c_p3.number_input("Metri oltre i 200m di distanza", min_value=0, step=50)

    # Logica Pd (Limitatore 1.1 in BT fino a 30kW)
    f_new = 1.1 if ("BT" in t_new and p_new <= 30) else 1.0
    f_att = 1.1 if ("BT" in t_att and p_att <= 30) else 1.0
    
    # Scelta Prezzo TIC
    px = TIC_2026["MT"] if "MT" in t_new else (TIC_2026["DOM_LE6"] if (tipo_utenza == "Domestico" and p_new <= 6) else TIC_2026["BT_ALTRI"])
    
    if pratica == "Nuova Connessione":
        pd_new = p_new * f_new
        c_tec = (pd_new * px) + TIC_2026["DIST_FISSA"] + (math.ceil(dist_m/100) * TIC_2026["DIST_EXTRA"])
    else:
        # Differenziale su Potenze Disponibili
        pd_new = p_new * f_new
        pd_att = p_att * f_att
        c_tec = max(0.0, pd_new - pd_att) * px

c_pass = TIC_2026["PASS_BT_MT"] if ("BT" in t_att and "MT" in t_new) else 0
c_gest = (c_tec + c_pass + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if applica_gestione else 0.0
tot_imp = c_tec + c_pass + c_gest + TIC_2026["ISTRUTTORIA"]

# Gestione IVA
is_split = "P.A." in uso
aliq = 0.10 if "10%" in uso else (0.22 if ("22%" in uso or is_split) else 0.0)
tot_iva = tot_imp * aliq
tot_finale = tot_imp if is_split else tot_imp + tot_iva

# --- OUTPUT RISULTATI ---
res_col1, res_col2 = st.columns([2, 1])

with res_col1:
    st.markdown("### 💰 Riepilogo Economico")
    st.write(f"🔹 Potenza Disponibile Calcolata: **{(p_new * f_new):.2f} kW**")
    st.write(f"🔹 Quota Tecnica TIC: **{c_tec:.2f} €**")
    if applica_gestione:
        st.write(f"🔹 Oneri Gestione PolisEnergia: **{c_gest:.2f} €**")
    st.write(f"🔹 Istruttoria Amministrativa: **{TIC_2026['ISTRUTTORIA']:.2f} €**")

with res_col2:
    st.metric("TOTALE DA PAGARE", f"{tot_finale:.2f} €")
    if is_split:
        st.warning("REGIME SPLIT PAYMENT (IVA Esclusa dal totale)")
    
    if st.button("📄 GENERA PREVENTIVO PDF"):
        if nome and pod:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "POLIS ENERGIA - PREVENTIVO UFFICIALE", ln=True, align='C')
            pdf.set_font("Helvetica", "", 12)
            pdf.ln(10)
            pdf.cell(0, 10, f"Intestatario: {nome}", ln=True)
            pdf.cell(0, 10, f"Codice POD: {pod}", ln=True)
            pdf.cell(0, 10, f"Tipo Pratica: {pratica}", ln=True)
            pdf.cell(0, 10, f"Potenza Contrattuale: {p_new} kW (Disp: {p_new*f_new:.2f} kW)", ln=True)
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, f"TOTALE DOVUTO: {tot_finale:.2f} EUR", ln=True)
            pdf.ln(10)
            pdf.set_font("Helvetica", "I", 8)
            pdf.multi_cell(0, 5, "Nota: Il presente preventivo ha validita 30 giorni. La potenza calcolata include la franchigia del 10% (limitatore) come da normativa ARERA TIC 2026.")
            
            p_name = f"Preventivo_{pod}.pdf"
            pdf.output(p_name)
            with open(p_name, "rb") as f:
                st.download_button("SCARICA DOCUMENTO", f, file_name=p_name)
        else:
            st.error("Inserisci Nome e POD per generare il PDF!")
