import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# --- CONFIGURAZIONE SMTP ---
SMTP_SERVER = "out.postassl.it"
SMTP_PORT = 465
SENDER_EMAIL = "connessione@polisenergia.it"
SENDER_PASSWORD = "Pratiche2026@" 

# --- COSTANTI TECNICHE 2026 ---
TIC_DOMESTICO_LE6 = 62.30  
TIC_ALTRI_USI_BT = 78.81
TIC_MT = 62.74
ONERI_ISTRUTTORIA = 27.42
SPOSTAMENTO_10MT = 226.36
FISSO_BASE_CALCOLO = 25.88
COSTO_PASSAGGIO_MT = 494.83
IBAN_POLIS = "IT80P0103015200000007044056 - Monte dei Paschi di Siena"

st.set_page_config(page_title="PolisEnergia 4.0", layout="wide")

# --- LOGICA FRANCHIGIA (3.3 resta 3.3 | 4.95 diventa 5) ---
def format_franchigia(p):
    val = round(p * 1.1, 2)
    if round(val, 1) != val:
        return float(math.ceil(val))
    return val

# --- RESET ---
def reset_form():
    for key in list(st.session_state.keys()):
        if key != 'seq': del st.session_state[key]
    st.rerun()

if 'seq' not in st.session_state: st.session_state.seq = 1

# --- INTERFACCIA ---
st.title("⚡ PolisEnergia - Gestione Preventivi")
if st.button("🧹 PULISCI TUTTO"): reset_form()

# 1. DATI ANAGRAFICI
with st.container():
    c1, c2 = st.columns(2)
    nome = c1.text_input("Ragione Sociale", key="n").upper()
    email_dest = c1.text_input("Email Cliente", key="m")
    pod = c2.text_input("POD", key="p").upper()
    regime = c2.selectbox("Regime IVA", ["10%", "22%", "Esente", "P.A."], key="r")

st.divider()

# 2. SELEZIONE PRATICA
c3, c4 = st.columns([2, 1])
pratica = c3.selectbox("Tipo Pratica", ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento Contatore"], key="prat")
tipo_ut = c4.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True, key="ut")

p_att, p_new, c_dist, t_new, passaggio_mt = 0.0, 0.0, 0.0, "BT", False

if "Potenza" in pratica or "Subentro" in pratica:
    col1, col2 = st.columns(2)
    if tipo_ut == "Altri Usi":
        passaggio_mt = col1.checkbox("🔄 Passaggio a Media Tensione (MT)?", key="mt")
        t_new = "MT" if passaggio_mt else "BT"
    p_att = col1.number_input("Potenza Attuale (kW)", value=3.0, step=0.5, key="pa")
    p_new = col2.number_input("Potenza Richiesta (kW)", value=4.5, step=0.5, key="pn")
elif "Nuova" in pratica:
    p_new = st.number_input("Potenza Richiesta (kW)", value=3.0, key="pnc")
    c_dist = st.number_input("Quota Distanza €", 0.0, key="dist")
elif "Spostamento" in pratica:
    s_dist = st.radio("Distanza", ["Entro 10 metri", "Oltre 10 metri"], key="sd")
    c_dist = SPOSTAMENTO_10MT if "Entro" in s_dist else st.number_input("Costo Rilievo €", 0.0, key="sdc")

# --- CALCOLO (SEMPRE ATTIVO) ---
tar = TIC_MT if t_new == "MT" else (TIC_DOMESTICO_LE6 if (tipo_ut == "Domestico" and p_new <= 6) else TIC_ALTRI_USI_BT)

if "Spostamento" in pratica:
    c_tec = c_dist
    delta_kw = 0.0
else:
    v_new = format_franchigia(p_new)
    v_att = format_franchigia(p_att) if p_att > 0 else 0.0
    delta_kw = round(v_new - v_att, 1)
    c_tec = round(delta_kw * tar, 2)
    if passaggio_mt: c_tec += COSTO_PASSAGGIO_MT
    if "Nuova" in pratica: c_tec += c_dist

c_gest = round((c_tec + FISSO_BASE_CALCOLO) * 0.1, 2)
imp = round(c_tec + c_gest + ONERI_ISTRUTTORIA, 2)
iva_p = 10 if "10" in regime else (22 if "22" in regime or "P.A." in regime else 0)
iva_e = round(imp * (iva_p/100), 2)
bollo = 2.0 if (regime == "Esente" and imp > 77.47) else 0.0
totale = round((imp if "P.A." in regime else imp + iva_e) + bollo, 2)

# --- 3. ANTEPRIMA ---
st.subheader("📊 Anteprima Calcolo")
st.info(f"Logica: {format_franchigia(p_new)} (Nuova) - {format_franchigia(p_att)} (Attuale) = {delta_kw} kW fatturabili")

col_tab1, col_tab2 = st.columns([2, 1])
with col_tab1:
    st.table(pd.DataFrame({
        "Descrizione": ["Quota Tecnica TIC", "Gestione Polis (10%)", "Oneri Istruttoria", "IVA", "Bollo"],
        "Importo (€)": [f"{c_tec:.2f}", f"{c_gest:.2f}", f"{ONERI_ISTRUTTORIA:.2f}", f"{iva_e:.2f}", f"{bollo:.2f}"]
    }))
with col_tab2:
    st.metric("TOTALE", f"{totale:.2f} €")

# --- 4. AZIONI (GENERA, ARCHIVIA) ---
if st.button("📁 GENERA PDF E SALVA SU EXCEL", type="primary", use_container_width=True):
    cod = f"POLIS-2026-{st.session_state.seq:04d}"
    
    # PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, f"PREVENTIVO {cod}", ln=1, align='C')
    pdf.set_font("Arial", "", 10); pdf.cell(0, 8, f"Cliente: {nome} - POD: {pod}", ln=1)
    pdf.cell(150, 8, f"Quota Tecnica (Delta {delta_kw} kW)", 1); pdf.cell(40, 8, f"{c_tec:.2f}", 1, ln=1)
    pdf.cell(150, 8, "Totale", 1); pdf.cell(40, 8, f"{totale:.2f}", 1, ln=1)
    pdf.ln(10); pdf.cell(0, 5, f"IBAN: {IBAN_POLIS}", ln=1)
    pdf.cell(0, 5, f"CAUSALE: {cod}", ln=1)
    
    st.session_state.pdf_bytes = pdf.output(dest='S').encode('latin-1')
    st.session_state.current_cod = cod
    
    # EXCEL
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read()
        row = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y"), "Codice": cod, "Cliente": nome, "POD": pod, "Delta": delta_kw, "Totale": totale}])
        conn.update(data=pd.concat([df, row], ignore_index=True))
        st.success(f"✅ Preventivo {cod} archiviato!")
    except: st.warning("PDF generato, ma errore Excel.")
    
    st.session_state.seq += 1

# --- 5. MAIL (COMPARE SOLO SE IL PDF È STATO GENERATO) ---
if 'pdf_bytes' in st.session_state:
    st.divider()
    st.subheader("✉️ Invia Email e Scarica")
    
    msg_def = f"Gentile {nome},\nin allegato il preventivo {st.session_state.current_cod} per il POD {pod}.\nCordiali saluti."
    corpo = st.text_area("Messaggio:", value=msg_def, height=150)
    
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("📧 INVIA MAIL AL CLIENTE", use_container_width=True):
            try:
                msg = MIMEMultipart()
                msg['From'], msg['To'], msg['Subject'] = SENDER_EMAIL, email_dest, f"Preventivo {st.session_state.current_cod}"
                msg.attach(MIMEText(corpo))
                part = MIMEApplication(st.session_state.pdf_bytes, Name=f"{st.session_state.current_cod}.pdf")
                part['Content-Disposition'] = f'attachment; filename="{st.session_state.current_cod}.pdf"'
                msg.attach(part)
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
                    s.starttls(); s.login(SENDER_EMAIL, SENDER_PASSWORD); s.send_message(msg)
                st.success("📩 Mail inviata!")
            except: st.error("Errore invio mail.")
            
    with c_btn2:
        st.download_button("📥 SCARICA PDF", st.session_state.pdf_bytes, f"{st.session_state.current_cod}.pdf", use_container_width=True)
