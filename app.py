import streamlit as st
import math
from fpdf import FPDF
from datetime import datetime

# 1. Configurazione
st.set_page_config(page_title="PolisEnergia", page_icon="⚡", layout="wide")

# 2. Costanti TIC 2026
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "PASS_BT_MT": 494.83, "DIST_FISSA": 209.62, 
    "DIST_EXTRA": 105.08, "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 452.72, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88
}

# --- INTERFACCIA ---
st.title("⚡ PolisEnergia")
st.caption("Configuratore Tecnico Fornitura")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Dati Pratica")
    tipo_utenza = st.radio("Tipologia Utenza", ["Domestico", "Altri Usi"], horizontal=True)
    uso = st.selectbox("Regime Fiscale / IVA", ["IVA 10% (Domestico)", "IVA 22% (Business)", "P.A. (Split Payment)", "Esente"])
    nome = st.text_input("Intestatario / Ragione Sociale").upper()
    pod = st.text_input("Codice POD").upper()

with col2:
    st.subheader("Parametri Tecnici")
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    t_att = st.selectbox("Tensione Attuale", ["BT", "MT"])
    op_t_new = ["BT"] if tipo_utenza == "Domestico" else ["BT", "MT"]
    t_new = st.selectbox("Tensione Richiesta", op_t_new)
    applica_gestione = st.checkbox("Applica Oneri Gestione Polis (10%)", value=True)

# --- LOGICA DI CALCOLO ---
st.divider()
p_att, p_new, dist_m, c_tec = 0.0, 0.0, 0, 0.0

if "Spostamento" in pratica:
    tipo_sp = st.radio("Distanza", ["Entro 10m", "Oltre 10m"])
    c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in tipo_sp else TIC_2026["SPOST_OLTRE_10"]
    f_new = 1.0
else:
    c_p1, c_p2, c_p3 = st.columns(3)
    if "Nuova" not in pratica:
        p_att = c_p1.number_input("Potenza Attuale (kW)", min_value=0.0, value=3.0)
    p_new = c_p2.number_input("Nuova Potenza (kW)", min_value=0.1, value=6.0)
    if "Nuova" in pratica:
        dist_m = c_p3.number_input("Metri oltre i 200m", min_value=0)

    f_new = 1.1 if (t_new == "BT" and p_new <= 30) else 1.0
    f_att = 1.1 if (t_att == "BT" and p_att <= 30) else 1.0
    px = TIC_2026["MT"] if t_new == "MT" else (TIC_2026["DOM_LE6"] if (tipo_utenza == "Domestico" and p_new <= 6) else TIC_2026["BT_ALTRI"])
    
    if "Nuova" in pratica:
        c_tec = (p_new * f_new * px) + TIC_2026["DIST_FISSA"] + (math.ceil(dist_m/100) * TIC_2026["DIST_EXTRA"])
    else:
        c_tec = max(0.0, (p_new * f_new) - (p_att * f_att)) * px

c_pass = TIC_2026["PASS_BT_MT"] if (t_att == "BT" and t_new == "MT") else 0
c_gest = (c_tec + c_pass + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if applica_gestione else 0.0
tot_sogg_iva = c_tec + c_pass + c_gest + TIC_2026["ISTRUTTORIA"]

# --- LOGICA BOLLO 2 EURO (SOLO ESENTE) ---
bollo_2_euro = 0.0
if uso == "Esente" and tot_sogg_iva > 77.47:
    bollo_2_euro = 2.00

# Fiscale
is_split = "P.A." in uso
aliq = 0.10 if "10%" in uso else (0.22 if ("22%" in uso or is_split) else 0.0)
tot_iva = tot_sogg_iva * aliq

# Totale Finale: Bollo aggiunto solo se calcolato (Esente > 77.47)
tot_finale = (tot_sogg_iva if is_split else tot_sogg_iva + tot_iva) + bollo_2_euro

# --- AREA ANTEPRIMA ---
st.subheader("📊 Riepilogo Preventivo")
r1, r2, r3 = st.columns(3)
r1.metric("Potenza Disponibile", f"{p_new * f_new:.2f} kW")
r2.metric("Imponibile", f"{tot_sogg_iva:.2f} €")
r3.metric("TOTALE FINALE", f"{tot_finale:.2f} €")

with st.expander("🔍 Vedi dettaglio fiscale"):
    st.write(f"**Quota Potenza TIC:** {c_tec:.2f} €")
    st.write(f"**Istruttoria:** {TIC_2026['ISTRUTTORIA']:.2f} €")
    if bollo_2_euro > 0:
        st.write(f"**Imposta di Bollo:** {bollo_2_euro:.2f} € (Regime Esente > 77,47€)")
    if not uso == "Esente":
        st.write(f"**IVA ({int(aliq*100)}%):** {tot_iva:.2f} €")
    if is_split:
        st.info("Nota: IVA in Split Payment")

# --- FUNZIONE PDF ---
def genera_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(0, 29, 61); pdf.rect(0, 0, 210, 45, 'F')
    try:
        pdf.image("logo_polis.png", x=10, y=8, w=45)
    except:
        pdf.set_xy(10, 15); pdf.set_font("Helvetica", "B", 20); pdf.set_text_color(255, 255, 255); pdf.cell(0, 10, "POLIS ENERGIA")
    
    pdf.set_xy(120, 12); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 10)
    pdf.set_font("Helvetica", "", 8); pdf.cell(5, 5, "Ufficio Tecnico | www.polisenergia.it", ln=True, align='R')
    
    pdf.ln(25); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 14)
    pdf.cell(2, 10, f"PREVENTIVO PER: {nome}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(95, 7, f"POD: {pod}", 0); pdf.cell(95, 7, f"Data: {datetime.now().strftime('%d/%m/%Y')}", 0, 1, 'R')
    
    pdf.ln(10)
    pdf.set_fill_color(0, 180, 216); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(135, 10, " DESCRIZIONE", 1, 0, 'L', True); pdf.cell(55, 10, " IMPORTO", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 10)
    pdf.cell(135, 10, f" Quota Potenza TIC ({p_new*f_new:.2f} kW)", 1); pdf.cell(55, 10, f" {c_tec:.2f} EUR", 1, 1, 'R')
    pdf.cell(135, 10, " Istruttoria Amministrativa", 1); pdf.cell(55, 10, f" {TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    if bollo_2_euro > 0:
        pdf.cell(135, 10, " Imposta di Bollo ", 1); pdf.cell(55, 10, " 2.00 EUR", 1, 1, 'R')
    
    pdf.ln(10); pdf.set_font("Helvetica", "B", 12)
    pdf.cell(135, 10, "TOTALE DA PAGARE", 0, 0, 'R'); pdf.cell(55, 10, f"{tot_finale:.2f} EUR", 0, 1, 'R')
    return pdf.output()

# --- BOTTONE ---
st.divider()
if st.button("🚀 GENERA PREVENTIVO PDF"):
    if nome and pod:
        try:
            pdf_data = genera_pdf()
            st.download_button(label="📥 Scarica documento", data=bytes(pdf_data), file_name=f"Polis_{pod}.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"Errore: {e}")
    else:
        st.error("Inserisci Nome e POD!")
