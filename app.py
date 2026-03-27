import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import os
import ssl
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="PolisEnergia 4.0", layout="wide")

TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "SPOST_ENTRO_10": 226.36, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88, "COSTO_PASSAGGIO_MT": 494.83
}

IBAN_POLIS = "IT80P0103015200000007044056 - Monte dei Paschi di Siena" # Inserisci IBAN reale

if 'seq' not in st.session_state: st.session_state.seq = 1
if 'pdf_pronto' not in st.session_state: st.session_state.pdf_pronto = None

# --- FUNZIONI ---
def genera_pdf(d):
    pdf = FPDF()
    pdf.add_page()
    
    # Header Blu Polis
    pdf.set_fill_color(0, 29, 61); pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_xy(120, 12); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 5, "PolisEnergia srl - Via Terre delle Risaie, 4 - 84131 Salerno (SA)", align='R', ln=1)
    
    # Titolo e Codice Pratica
    pdf.set_xy(10, 50); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"PREVENTIVO N. {d['cod_pratica']}", ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=1)
    
    # Dati Cliente
    pdf.ln(5); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"Spett.le: {d['nome']}", ln=1)
    pdf.cell(0, 6, f"Indirizzo: {d['indirizzo']}", ln=1)
    pdf.cell(0, 6, f"POD: {d['pod']}", ln=1)
    
    # Tabella Costi
    pdf.ln(10); pdf.set_fill_color(0, 180, 216); pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, " DESCRIZIONE PRESTAZIONE", 1, 0, 'L', True); pdf.cell(50, 10, " IMPORTO", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 8, f" Quota Potenza/Tecnica ({d['t_att']} -> {d['t_new']})", 1); pdf.cell(50, 8, f"{d['c_tec']:.2f} EUR", 1, 1, 'R')
    if d['c_dist'] > 0: pdf.cell(140, 8, " Quota Distanza / Oneri Rilievo", 1); pdf.cell(50, 8, f"{d['c_dist']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Amministrativi e Istruttoria", 1); pdf.cell(50, 8, f"{TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Gestione Pratica Polis", 1); pdf.cell(50, 8, f"{d['c_gest']:.2f} EUR", 1, 1, 'R')
    
    pdf.ln(2); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 9, f" IMPONIBILE", 1); pdf.cell(50, 9, f"{d['imponibile']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, f" IVA {d['iva_perc']}%", 1); pdf.cell(50, 9, f"{d['iva_euro']:.2f} EUR", 1, 1, 'R')
    if d['bollo'] > 0: pdf.cell(140, 9, " MARCA DA BOLLO", 1); pdf.cell(50, 9, "2.00 EUR", 1, 1, 'R')
    
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(140, 11, " TOTALE DA PAGARE", 1, 0, 'L', True); pdf.cell(50, 11, f"{d['totale']:.2f} EUR", 1, 1, 'R', True)
    
    # Coordinate e Firma
    pdf.ln(15); pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, "COORDINATE BANCARIE:", ln=1)
    pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, f"IBAN: {IBAN_POLIS}", ln=1)
    pdf.cell(0, 6, f"Causale: Saldo Preventivo {d['cod_pratica']}", ln=1)
    
    pdf.ln(30)
    pdf.cell(100, 10, "Firma PolisEnergia srl", ln=0)
    pdf.cell(90, 10, "Firma per Accettazione Cliente", ln=1, align='R')
    pdf.line(10, 185, 60, 185); pdf.line(140, 185, 200, 185)
    
    return bytes(pdf.output())

# --- INTERFACCIA ---
st.title("⚡ PolisEnergia 4.0")

# 1. ANAGRAFICA
c1, c2 = st.columns(2)
with c1:
    nome = st.text_input("Ragione Sociale", key="reg_soc").upper()
    indirizzo = st.text_input("Indirizzo", key="ind_cli")
with c2:
    uso = st.selectbox("Regime Fiscale", ["IVA 10%", "IVA 22%", "P.A.", "Esente"], key="iva_sel")
    pod = st.text_input("POD", key="pod_cli").upper()

st.divider()

# 2. LOGICA DINAMICA
pratica = st.selectbox("Tipo di Pratica", ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento"])
tipo_ut = st.radio("Destinazione", ["Domestico", "Altri Usi"], horizontal=True)

p_att, p_new, c_dist = 0.0, 0.0, 0.0
t_att, t_new = "BT", "BT"
flag_mt = False
s_dist = ""

if pratica in ["Aumento Potenza", "Subentro con Modifica"]:
    col1, col2 = st.columns(2)
    with col1:
        if tipo_ut == "Altri Usi":
            flag_mt = st.checkbox("Passaggio a MT (+494.83€)")
            t_new = "MT" if flag_mt else st.radio("Tensione", ["BT", "MT"])
        p_att = st.number_input("Potenza Attuale (kW)", 0.0, step=0.5)
    with col2:
        p_new = st.number_input("Nuova Potenza (kW)", 0.0, step=0.5)
elif pratica == "Nuova Connessione":
    col1, col2 = st.columns(2)
    with col1:
        p_new = st.number_input("Potenza Richiesta (kW)", 0.0, step=0.5)
    with col2:
        c_dist = st.number_input("Quota Distanza (€) - Manuale", 0.0)
elif pratica == "Spostamento":
    s_dist = st.radio("Distanza", ["Entro i 10 mt", "Oltre i 10 mt"])
    if "Oltre" in s_dist:
        c_dist = st.number_input("Costo Spostamento (€) - Manuale", 0.0)

app_gest = st.checkbox("Gestione Polis (10%)", value=True)

# --- CALCOLO ISTANTANEO ---
def get_t(tens, pot, ut):
    if tens == "MT": return TIC_2026["MT"]
    return TIC_2026["DOM_LE6"] if ut == "Domestico" and pot <= 6 else TIC_2026["BT_ALTRI"]

c_tec = 0.0
if pratica == "Spostamento":
    c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in s_dist else 0.0
elif pratica == "Nuova Connessione":
    c_tec = math.ceil(p_new) * get_t(t_new, p_new, tipo_ut)
else:
    f = 1.1 if (t_att == "BT" and p_att <= 30) else 1.0
    c_tec = max(0.0, (math.ceil(p_new) * get_t(t_new, p_new, tipo_ut)) - (p_att * f * get_t(t_att, p_att, tipo_ut)))
    if flag_mt: c_tec += TIC_2026["COSTO_PASSAGGIO_MT"]

c_gest = (c_tec + c_dist + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.1 if app_gest else 0.0
imp = c_tec + c_dist + c_gest + TIC_2026["ISTRUTTORIA"]
iva_p = 10 if "10" in uso else (22 if "22" in uso or "P.A." in uso else 0)
iva_e = imp * (iva_p/100)
bollo = 2.0 if (uso == "Esente" and imp > 77.47) else 0.0
tot = (imp if "P.A." in uso else imp + iva_e) + bollo

# --- ANTEPRIMA ---
st.subheader("📊 Riepilogo Costi")
st.dataframe(pd.DataFrame({
    "Voce": ["Costo Tecnico", "Distanza", "Gestione Polis", "IVA", "Totale"],
    "Importo": [f"{c_tec:.2f}€", f"{c_dist:.2f}€", f"{c_gest:.2f}€", f"{iva_e:.2f}€", f"{tot:.2f}€"]
}), use_container_width=True)

# --- AZIONI ---
if st.button("📁 CONFERMA E REGISTRA PRATICA", type="primary", use_container_width=True):
    if nome and indirizzo:
        # Generazione Codice PREV2026XXXX
        cod_pratica = f"PREV{datetime.now().year}{st.session_state.seq:04d}"
        
        dati = {
            'Data': datetime.now().strftime("%d/%m/%Y"),
            'cod_pratica': cod_pratica, 'nome': nome, 'indirizzo': indirizzo, 'pod': pod,
            'pratica': pratica, 't_att': t_att, 't_new': t_new, 'c_tec': c_tec, 'c_dist': c_dist,
            'c_gest': c_gest, 'imponibile': imp, 'iva_perc': iva_p, 'iva_euro': iva_e, 
            'bollo': bollo, 'totale': tot, 'uso': uso
        }
        
        # 1. Genera PDF
        st.session_state.pdf_pronto = genera_pdf(dati)
        st.session_state.ultimo_codice = cod_pratica
        
        # 2. Aggiorna Google Sheets
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df_old = conn.read()
            df_new = pd.concat([df_old, pd.DataFrame([dati])], ignore_index=True)
            conn.update(data=df_new)
            st.success("Dati registrati su Google Sheets!")
        except:
            st.warning("Database non configurato nei Secrets, PDF generato comunque.")
            
        st.session_state.seq += 1
        st.rerun()
    else:
        st.error("Compila i campi obbligatori!")

# --- DOWNLOAD E INVIO ---
if st.session_state.pdf_pronto:
    st.divider()
    cdl, cml = st.columns(2)
    with cdl:
        st.download_button(f"📥 SCARICA {st.session_state.ultimo_codice}", st.session_state.pdf_pronto, f"{st.session_state.ultimo_codice}.pdf")
    with cml:
        mail_cli = st.text_input("Invia a (Email Cliente):")
        if st.button("🚀 INVIA"):
            # Qui inserire la tua funzione invia_mail_aruba
            st.success("Invio simulato con successo!")
