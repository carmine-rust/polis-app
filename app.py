import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- COSTANTI ---
TIC_DOMESTICO_LE6 = 62.30  
TIC_ALTRI_USI_BT = 78.81
TIC_MT = 62.74
ONERI_ISTRUTTORIA = 27.42
SPOSTAMENTO_10MT = 226.36
FISSO_BASE_CALCOLO = 25.88
COSTO_PASSAGGIO_MT = 494.83
IBAN_POLIS = "IT 00 X 00000 00000 000000000000"
LOGO_PATH = "logo_polis.png"

st.set_page_config(page_title="PolisEnergia - Preventivatore", layout="wide")

if 'seq' not in st.session_state: st.session_state.seq = 1
if 'pdf_pronto' not in st.session_state: st.session_state.pdf_pronto = None

def reset_form():
    for key in list(st.session_state.keys()):
        if key not in ['seq']: del st.session_state[key]
    st.rerun()

def genera_pdf_polis(d):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(0, 29, 61); pdf.rect(0, 0, 210, 45, 'F')
    try: pdf.image(LOGO_PATH, 10, 8, 33)
    except:
        pdf.set_xy(10, 15); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "POLIS ENERGIA SRL")
    pdf.set_xy(120, 12); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 5, "PolisEnergia srl - Via Terre delle Risaie, 4 - 84131 Salerno (SA)", align='R', ln=1)
    pdf.set_font("Helvetica", "", 8); pdf.cell(0, 5, "P.IVA 05862440651 - info@polisenergia.it", align='R', ln=1)
    pdf.set_xy(10, 55); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"PREVENTIVO N. {d['Codice']}", ln=1)
    pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, f"Data: {d['Data']}", ln=1)
    pdf.ln(5); pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, f"SPETT.LE CLIENTE: {d['Cliente']}", ln=1)
    pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, f"Indirizzo: {d['Indirizzo']}", ln=1); pdf.cell(0, 6, f"POD: {d['POD']}", ln=1)
    pdf.ln(10); pdf.set_fill_color(0, 119, 182); pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, " DESCRIZIONE PRESTAZIONE", 1, 0, 'L', True); pdf.cell(50, 10, " IMPORTO", 1, 1, 'C', True)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 8, f" Quota Tecnica TIC (Potenza Disponibile {d['Delta_kW']} kW)", 1); pdf.cell(50, 8, f"{d['Quota_Tecnica']:.2f} EUR", 1, 1, 'R')
    if d['c_dist'] > 0: pdf.cell(140, 8, " Quota Distanza / Rilievo", 1); pdf.cell(50, 8, f"{d['c_dist']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Amministrativi e Istruttoria", 1); pdf.cell(50, 8, f"{ONERI_ISTRUTTORIA:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Competenze Professionali Gestione", 1); pdf.cell(50, 8, f"{d['Gestione_Polis']:.2f} EUR", 1, 1, 'R')
    pdf.ln(2); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 9, " TOTALE IMPONIBILE", 1); pdf.cell(50, 9, f"{d['Imponibile']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, f" IVA APPLICATA ({d['iva_perc']}%)", 1); pdf.cell(50, 9, f"{d['IVA_Euro']:.2f} EUR", 1, 1, 'R')
    if d.get('bollo', 0) > 0: pdf.cell(140, 9, " IMPOSTA DI BOLLO", 1); pdf.cell(50, 9, "2.00 EUR", 1, 1, 'R')
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(140, 11, " TOTALE DA CORRISPONDERE", 1, 0, 'L', True); pdf.cell(50, 11, f"{d['Totale']:.2f} EUR", 1, 1, 'R', True)
    pdf.ln(15); pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, "MODALITA' DI PAGAMENTO:", ln=1)
    pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, f"IBAN: {IBAN_POLIS}", ln=1)
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, f"CAUSALE: Accettazione Preventivo {d['Codice']}", ln=1)
    pdf.ln(25); pdf.cell(100, 10, "Firma PolisEnergia srl", ln=0); pdf.cell(90, 10, "Firma Accettazione Cliente", ln=1, align='R')
    pdf.line(10, 205, 70, 205); pdf.line(140, 205, 200, 205)
    return bytes(pdf.output())

# --- INTERFACCIA ---
st.title("⚡ PolisEnergia 4.0")
if st.button("🧹 PULISCI"): reset_form()

c1, c2 = st.columns(2)
nome = c1.text_input("Ragione Sociale").upper()
indirizzo = c1.text_input("Indirizzo")
regime = c2.selectbox("Regime Fiscale", ["IVA 10%", "IVA 22%", "P.A.", "Esente"])
pod = c2.text_input("POD").upper()

st.divider()
pratica = st.selectbox("Operazione", ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento"])
tipo_ut = st.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True)

p_att, p_new, c_dist, t_new, flag_mt = 0.0, 0.0, 0.0, "BT", False

if "Potenza" in pratica or "Subentro" in pratica:
    col1, col2 = st.columns(2)
    if tipo_ut == "Altri Usi":
        flag_mt = col1.checkbox("Passaggio a MT?")
        t_new = "MT" if flag_mt else "BT"
    p_att = col1.number_input("Potenza Attuale (kW)", value=3.0, step=0.5)
    p_new = col2.number_input("Nuova Potenza (kW)", value=4.5, step=0.5)
elif "Nuova" in pratica:
    p_new = st.number_input("Potenza (kW)", value=3.0, step=0.5)
    c_dist = st.number_input("Quota Distanza (€)", 0.0)
elif "Spostamento" in pratica:
    s_dist = st.radio("Distanza", ["Entro 10 mt", "Oltre 10 mt"], horizontal=True)
    if "Oltre" in s_dist: c_dist = st.number_input("Costo (€)", 0.0)
    else: c_dist = 0.0

# --- CALCOLO ESATTO ---
if t_new == "MT": tar = TIC_MT
elif tipo_ut == "Domestico" and p_new <= 6: tar = TIC_DOMESTICO_LE6
else: tar = TIC_ALTRI_USI_BT

if "Spostamento" in pratica:
    c_tec = SPOSTAMENTO_10MT if "Entro" in s_dist else 0.0
    delta_kw = 0.0
else:
    # LA LOGICA RICHIESTA: CEIL(P_NEW * 1.1) - (P_ATT * 1.1)
    val_new = math.ceil(p_new * 1.1) if t_new == "BT" else p_new
    val_att = (p_att * 1.1) if t_new == "BT" else p_att
    delta_kw = max(0.0, val_new - val_att)
    c_tec = delta_kw * tar
    if flag_mt: c_tec += COSTO_PASSAGGIO_MT

c_gest = (c_tec + c_dist + FISSO_BASE_CALCOLO) * 0.1
imp = c_tec + c_dist + c_gest + ONERI_ISTRUTTORIA
iva_p = 10 if "10" in regime else (22 if "22" in regime or "P.A." in regime else 0)
iva_e = imp * (iva_p/100)
bollo = 2.0 if (regime == "Esente" and imp > 77.47) else 0.0
tot = (imp if "P.A." in regime else imp + iva_e) + bollo

# --- ANTEPRIMA ---
st.table(pd.DataFrame({"Voce": ["Quota TIC", "Gestione", "IVA", "TOTALE"], "Euro": [f"{c_tec:.2f}", f"{c_gest:.2f}", f"{iva_e:.2f}", f"{tot:.2f}"]}))

if st.button("📁 GENERA PREVENTIVO", type="primary"):
    if nome and pod:
        cod = f"PREV2026{st.session_state.seq:04d}"
        dati = {'Data': datetime.now().strftime("%d/%m/%Y"), 'Codice': cod, 'Cliente': nome, 'Indirizzo': indirizzo, 'POD': pod, 'Quota_Tecnica': c_tec, 'Delta_kW': round(delta_kw, 2), 'c_dist': c_dist, 'Gestione_Polis': c_gest, 'Imponibile': imp, 'iva_perc': iva_p, 'IVA_Euro': iva_e, 'bollo': bollo, 'Totale': tot}
        st.session_state.pdf_pronto = genera_pdf_polis(dati)
        st.session_state.ultimo_codice = cod
        st.session_state.seq += 1
        st.rerun()

if st.session_state.pdf_pronto:
    st.download_button(f"📥 SCARICA {st.session_state.ultimo_codice}", st.session_state.pdf_pronto, f"{st.session_state.ultimo_codice}.pdf")
