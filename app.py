import streamlit as st
import math
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# --- 1. CONFIGURAZIONE E SECRETS ---
st.set_page_config(page_title="PolisEnergia 4.0", layout="wide")

try:
    SMTP_SERVER = st.secrets["EMAIL_SERVER"]
    SMTP_PORT = st.secrets["EMAIL_PORT"]
    SENDER_EMAIL = st.secrets["EMAIL_SENDER"]
    SENDER_PASSWORD = st.secrets["EMAIL_PASSWORD"]
    MAIL_CC = st.secrets.get("EMAIL_CC", "")
except:
    st.error("Configura i Secrets EMAIL su Streamlit!")
    st.stop()

# --- 2. LE TUE COSTANTI ORIGINALI ---
TIC_DOMESTICO_LE6 = 62.30  
TIC_ALTRI_USI_BT = 78.81
TIC_MT = 62.74
ONERI_ISTRUTTORIA = 27.42
SPOSTAMENTO_10MT = 226.36
FISSO_BASE_CALCOLO = 25.88
COSTO_PASSAGGIO_MT = 494.83
IBAN_POLIS = "IT80P0103015200000007044056 - Monte dei Paschi di Siena"

# --- 3. VISTA CLIENTE (GESTIONE FIRMA) ---
query_params = st.query_params
if "otp" in query_params:
    st.title("🖋️ Accettazione Preventivo Online")
    codice_prev = str(query_params.get("codice", "")).strip()
    otp_corretto = str(query_params.get("otp", "")).strip()

    st.info(f"Stai confermando il preventivo: **{codice_prev}**")
    otp_input = st.text_input("Inserisci il codice OTP ricevuto via mail", max_chars=6)

    if st.button("✅ ACCETTA E FIRMA ORA"):
        if str(otp_input).strip() == otp_corretto:
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                df = conn.read(ttl=0)
                # Pulizia codici per match sicuro
                df_codici = df["Codice"].astype(str).str.strip().str.replace('.0', '', regex=False)

                if codice_prev in df_codici.values:
                    idx = df_codici[df_codici == codice_prev].index[0]
                    df.at[idx, "Stato"] = "ACCETTATO"
                    df.at[idx, "Data Firma"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    conn.update(data=df)
                    
                    st.success("🎉 Preventivo firmato con successo!")
                    st.balloons()
                    
                    # Notifica a te (Carmine)
                    msg = MIMEMultipart()
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = SENDER_EMAIL
                    msg['Subject'] = f"🔔 FIRMATO: {codice_prev}"
                    msg.attach(MIMEText(f"Il cliente ha firmato il preventivo {codice_prev}", 'plain'))
                    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ssl.create_default_context()) as server:
                        server.login(SENDER_EMAIL, SENDER_PASSWORD)
                        server.send_message(msg)
                else:
                    st.error("Errore: Preventivo non trovato nel database")
            except Exception as e:
                st.error(f"Errore tecnico: {e}")
        else:
            st.error("❌ Codice OTP errato.")
    st.stop()

# --- 4. TUA LOGICA DI CALCOLO ORIGINALE ---
def genera_pdf_polis(d):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(0, 51, 102)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_xy(10, 12)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 10, "PolisEnergia srl")
    pdf.set_xy(120, 10)
    pdf.set_font("helvetica", "", 8)
    pdf.multi_cell(80, 4, "Via Terre delle Risaie, 4 - 84131 Salerno (SA)\nP.IVA 05050950657\nassistenza@polisenergia.it", align='R')
    pdf.set_xy(10, 50); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, f"PREVENTIVO N. {d['Codice']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    # ... (Il resto del layout PDF che avevi scritto tu)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(140, 12, " TOTALE DA CORRISPONDERE", border=1, fill=True)
    pdf.cell(50, 12, f"{d['Totale']:.2f} EUR ", border=1, align='R', fill=True)
    return pdf.output()

st.title("⚡ PolisEnergia - Gestione Preventivi")

# 1. DATI ANAGRAFICI
with st.container():
    c1, c2 = st.columns(2)
    nome = c1.text_input("Ragione Sociale").upper()
    email_dest = c1.text_input("Email Cliente")
    pod = c2.text_input("POD").upper()
    indirizzo = c1.text_input("Indirizzo Impianto")
    regime = c2.selectbox("Regime IVA", ["10%", "22%", "Esente", "P.A."])

# 2. SELEZIONE PRATICA E CALCOLI (TUA LOGICA ESATTA)
pratica = st.selectbox("Tipo Pratica", ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento Contatore"])
tipo_ut = st.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True)

# Inizializzazioni
p_att, p_new, c_dist, t_partenza, passaggio_mt = 0.0, 0.0, 0.0, "BT", False
delta, tar = 0.0, 0.0

if "Potenza" in pratica or "Subentro" in pratica:
    col1, col2 = st.columns(2)
    if tipo_ut == "Altri Usi":
        t_partenza = col1.selectbox("Tensione di Partenza", ["BT", "MT"])
        if t_partenza == "BT": passaggio_mt = col1.checkbox("Passaggio a Media Tensione (MT)?")
    p_att = col1.number_input("Potenza Attuale (kW)", value=3.0)
    p_new = col2.number_input("Potenza Richiesta (kW)", value=4.5)
elif "Nuova" in pratica:
    p_new = st.number_input("Potenza Richiesta (kW)", value=3.0)
    c_dist = st.number_input("Quota Distanza €", 0.0)
elif "Spostamento" in pratica:
    s_dist = st.radio("Distanza", ["Entro 10 metri", "Oltre 10 metri"])
    c_dist = SPOSTAMENTO_10MT if "Entro" in s_dist else st.number_input("Costo Rilievo €", 0.0)

# LOGICA POTENZA (Copiata dal tuo script)
if p_new > 0:
    if p_new <= 30:
        v_new = round(p_new * 1.1, 1)
        v_att = round(p_att * 1.1, 1) if p_att > 0 else 0.0
        delta = round(v_new - v_att, 1)
        if tipo_ut == "Domestico" and p_new <= 6: tar = TIC_DOMESTICO_LE6
        else: tar = TIC_MT if (t_partenza == "MT" or passaggio_mt) else TIC_ALTRI_USI_BT
    else:
        delta = round(p_new - p_att, 1)
        tar = TIC_MT if (t_partenza == "MT" or passaggio_mt) else TIC_ALTRI_USI_BT

# CALCOLO FINALE (Copiato dal tuo script)
c_tec = c_dist if "Spostamento" in pratica else round(delta * tar, 2)
if passaggio_mt: c_tec += COSTO_PASSAGGIO_MT
if "Nuova" in pratica: c_tec += c_dist

c_gest = round((c_tec + FISSO_BASE_CALCOLO) * 0.1, 2)
imp = round(c_tec + c_gest + ONERI_ISTRUTTORIA, 2)
iva_p = 10 if "10" in regime else (22 if "22" in regime or "P.A." in regime else 0)
iva_e = round(imp * (iva_p/100), 2)
bollo = 2.0 if (regime == "Esente" and imp > 77.47) else 0.0
totale = round(imp + bollo, 2) if "P.A." in regime else round(imp + iva_e + bollo, 2)

st.metric("TOTALE PREVENTIVO", f"{totale:.2f} €")

# INVIO E SALVATAGGIO
if st.button("📁 GENERA E INVIA EMAIL"):
    cod = datetime.now().strftime("%y%m%d%H%M%S")
    otp = str(random.randint(100000, 999999))
    
    # Salvataggio GSheets
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)
    nuova_riga = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y"), "Codice": cod, "Cliente": nome, "POD": pod, "Totale": totale, "OTP": otp, "Stato": "Inviato"}])
    conn.update(data=pd.concat([df, nuova_riga], ignore_index=True))

    # Link firma (Cambia l'URL con quello della tua app)
    url_app = "https://preventivatore-pratiche-connessione.streamlit.app/"
    link = f"{url_app}?codice={cod}&otp={otp}"

    # Generazione PDF e Mail
    d_pdf = {"Codice": cod, "Cliente": nome, "POD": pod, "Indirizzo": indirizzo, "Totale": totale}
    pdf_bytes = genera_pdf_polis(d_pdf)
    
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL; msg['To'] = email_dest; msg['Cc'] = MAIL_CC
    msg['Subject'] = f"Preventivo PolisEnergia {cod}"
    corpo = f"Gentile cliente,\nin allegato il preventivo.\nPer firmare clicca qui: {link}\nOTP: {otp}"
    msg.attach(MIMEText(corpo, 'plain'))
    
    part = MIMEApplication(pdf_bytes, Name=f"{cod}.pdf")
    part['Content-Disposition'] = f'attachment; filename="{cod}.pdf"'
    msg.attach(part)

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ssl.create_default_context()) as s:
        s.login(SENDER_EMAIL, SENDER_PASSWORD)
        s.send_message(msg)
    st.success("Inviato!")
