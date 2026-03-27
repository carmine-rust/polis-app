import streamlit as st
import math
import re
import pandas as pd
from fpdf import FPDF
import os
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import ssl

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="PolisEnergia Preventivatore 4.0", page_icon="⚡", layout="wide")

# --- INIZIALIZZAZIONE STATO ---
if 'seq' not in st.session_state: st.session_state.seq = 0
if 'pdf_pronto' not in st.session_state: st.session_state.pdf_pronto = None
if 'ultimo_codice' not in st.session_state: st.session_state.ultimo_codice = "In attesa..."

# --- CONNESSIONE A GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Errore connessione Cloud: {e}")

# --- FUNZIONI DI SERVIZIO ---
def invia_mail_aruba(destinatario, oggetto, corpo, pdf_bytes, nome_file):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["EMAIL_SENDER"]
        msg['To'] = destinatario
        msg['Subject'] = oggetto
        msg.attach(MIMEText(corpo, 'plain'))
        
        part = MIMEApplication(pdf_bytes, Name=nome_file)
        part['Content-Disposition'] = f'attachment; filename="{nome_file}"'
        msg.attach(part)
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(st.secrets["EMAIL_SERVER"], st.secrets["EMAIL_PORT"], context=context) as server:
            server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Errore Aruba: {e}")
        return False

TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "SPOST_ENTRO_10": 226.36, "SPOST_OLTRE_10": 226.36, 
    "ISTRUTTORIA": 27.42, "FISSO_BASE_CALCOLO": 25.88
}

def genera_pdf(d, cod_pratica):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(0, 29, 61); pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_xy(120, 12); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 5, "PolisEnergia srl - Via Terre delle Risaie, 4 - 84131 Salerno (SA)", align='R', ln=1)
    pdf.set_font("Helvetica", "", 8); pdf.cell(0, 6, "www.polisenergia.it", align='R', ln=1)
    
    pdf.set_xy(10, 55); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"SPETT.LE: {d['nome']}", ln=1)
    pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, f"INDIRIZZO: {d['indirizzo']}", ln=1)
    pdf.ln(10); pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"PREVENTIVO {d['pratica'].upper()} - POD: {d['pod']}", border="B", ln=1)
    
    pdf.ln(5); pdf.set_fill_color(0, 180, 216); pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, " DESCRIZIONE PRESTAZIONE", 1, 0, 'L', True); pdf.cell(50, 10, " IMPORTO", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 8, " ONERI DISTRIBUTORE", 1, 1, 'L', True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 8, f" Quota Tecnica", 1); pdf.cell(50, 8, f"{d['c_tec']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Amministrativi", 1); pdf.cell(50, 8, f"{TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Gestione Pratica", 1); pdf.cell(50, 8, f"{d['c_gest']:.2f} EUR", 1, 1, 'R')
    
    pdf.ln(2); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 9, " IMPONIBILE", 1); pdf.cell(50, 9, f"{d['imponibile']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, f" IVA ({d['iva_perc']}%)", 1); pdf.cell(50, 9, f"{d['iva_euro']:.2f} EUR", 1, 1, 'R')
    
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Helvetica", "B", 11)
    pdf.cell(140, 11, " TOTALE DA PAGARE", 1, 0, 'L', True); pdf.cell(50, 11, f"{d['totale']:.2f} EUR", 1, 1, 'R', True)
    
    pdf.ln(10); pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 5, f"Causale: {cod_pratica}\nIBAN: IT80P0103015200000007044056")
    return pdf.output()

# --- INTERFACCIA ---
st.title("⚡ PolisEnergia")
st.caption(f"Preventivatore 4.0 | Ultimo Codice: {st.session_state.ultimo_codice}")

# Form principale
with st.form("main_form"):
    c1, c2 = st.columns(2)
    with c1:
        nome = st.text_input("Ragione Sociale").upper()
        indirizzo = st.text_input("Indirizzo")
        uso = st.selectbox("Regime Fiscale", ["IVA 10%", "IVA 22%", "P.A.", "Esente"])
        pod = st.text_input("POD").upper()
    with c2:
        pratica = st.selectbox("Tipo di Pratica", ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento"])
        p_new = st.number_input("Nuova Potenza RICHIESTA (kW)", value=6.0, step=0.5)
        p_att = st.number_input("Potenza Partenza (kW)", value=3.0)
        app_gest = st.checkbox("Gestione Polis (10%)", value=True)
    
    submit = st.form_submit_button("📁 GENERA E ARCHIVIA")

# --- LOGICA DI CALCOLO (Si attiva solo al Submit) ---
if submit:
    if nome and indirizzo:
        # Calcoli semplificati per velocità
        c_tec = (p_new - p_att) * 78.81 if p_new > p_att else 0.0
        c_gest = (c_tec + TIC_2026['FISSO_BASE_CALCOLO']) * 0.10 if app_gest else 0.0
        imp = c_tec + c_gest + TIC_2026['ISTRUTTORIA']
        iva_p = 10 if "10" in uso else 22
        iva_e = imp * (iva_p/100)
        tot = imp + iva_e
        
        cod_pratica = f"BA{int(tot)}{st.session_state.seq}"
        
        dati = {
            'nome': nome, 'indirizzo': indirizzo, 'pod': pod if pod else "N.D.",
            'pratica': pratica, 'c_tec': c_tec, 'c_gest': c_gest, 'p_att': p_att, 
            'p_new': p_new, 'imponibile': imp, 'iva_perc': iva_p, 'iva_euro': iva_e, 'totale': tot
        }
        
        # 1. Genera PDF e salva in Session State
        pdf_file = genera_pdf(dati, cod_pratica)
        st.session_state.pdf_pronto = pdf_file
        st.session_state.ultimo_codice = cod_pratica
        st.session_state.seq = (st.session_state.seq + 1) % 10
        
        # 2. Archivia su Google Sheets
        try:
            df_esistente = conn.read(ttl=0)
            nuova_riga = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y"), "Codice": cod_pratica, "Cliente": nome, "Totale": tot}])
            conn.update(data=pd.concat([df_esistente, nuova_riga], ignore_index=True))
            st.success("✅ Salvato su Google Sheets!")
        except Exception as e:
            st.error(f"Errore Cloud: {e}")
        
        st.rerun() # Ricarica per mostrare il box mail correttamente

# --- SEZIONE INVIO MAIL (Fuori dal form, visibile solo se PDF esiste) ---
if st.session_state.pdf_pronto is not None:
    st.divider()
    st.subheader("✉️ Invia Preventivo via Email")
    
    with st.container():
        col_m1, col_m2 = st.columns([1, 2])
        with col_m1:
            mail_cliente = st.text_input("Email destinatario", key="mail_input")
            st.download_button("📥 SCARICA PDF", data=bytes(st.session_state.pdf_pronto), file_name=f"{st.session_state.ultimo_codice}.pdf")
        with col_m2:
            testo_default = f"Gentile Cliente, in allegato il preventivo {st.session_state.ultimo_codice}."
            corpo_mail = st.text_area("Messaggio", value=testo_default, key="text_area_mail")

        if st.button("🚀 INVIA ORA", key="send_btn"):
            if mail_cliente:
                with st.spinner("Invio tramite Aruba..."):
                    esito = invia_mail_aruba(mail_cliente, f"Preventivo Polis - {st.session_state.ultimo_codice}", corpo_mail, st.session_state.pdf_pronto, f"{st.session_state.ultimo_codice}.pdf")
                    if esito:
                        st.success(f"📩 Inviata con successo a {mail_cliente}!")
                        st.balloons()
            else:
                st.warning("Inserisci l'email!")
