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

# --- LOGICA FRANCHIGIA ---
def format_franchigia(p):
    val = p * 1.1
    # Se ha più di un decimale (es. 4.95) -> intero superiore (5)
    # Se ha un solo decimale (es. 3.3) -> resta 3.3
    if round(val, 1) != round(val, 5):
        return float(math.ceil(val))
    return round(val, 1)

def reset_form():
    for key in list(st.session_state.keys()):
        if key != 'seq': del st.session_state[key]
    st.rerun()

if 'seq' not in st.session_state: st.session_state.seq = 1

# --- UI ---
st.title("⚡ Preventivatore - PolisEnergia")
if st.button("🧹 SVUOTA TUTTO"): reset_form()

with st.container():
    c1, c2 = st.columns(2)
    nome = c1.text_input("Ragione Sociale", key="f_nome").upper()
    email_dest = c1.text_input("Email Cliente", key="f_mail")
    pod = c2.text_input("POD", key="f_pod").upper()
    regime = c2.selectbox("Regime IVA", ["10%", "22%", "Esente", "P.A."], key="f_reg")

st.divider()

pratica = st.selectbox("Tipo Pratica", 
    ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento Contatore"], key="f_prat")
tipo_ut = st.radio("Tipologia Utenza", ["Domestico", "Altri Usi"], horizontal=True, key="f_ut")

p_att, p_new, c_dist, t_new, passaggio_mt = 0.0, 0.0, 0.0, "BT", False

if "Potenza" in pratica or "Subentro" in pratica:
    col1, col2 = st.columns(2)
    if tipo_ut == "Altri Usi":
        passaggio_mt = col1.checkbox("🔄 Passaggio a Media Tensione (MT)?", key="f_mt")
        t_new = "MT" if passaggio_mt else "BT"
    p_att = col1.number_input("Potenza Attuale (kW)", value=3.0, step=0.5, key="f_pa")
    p_new = col2.number_input("Potenza Richiesta (kW)", value=4.5, step=0.5, key="f_pn")
elif "Nuova" in pratica:
    c1, c2 = st.columns(2)
    p_new = c1.number_input("Potenza Richiesta (kW)", value=3.0, step=0.5, key="f_pnc")
    c_dist = c2.number_input("Quota Distanza (da Rilievo) €", 0.0, key="f_dist")
elif "Spostamento" in pratica:
    s_dist = st.radio("Distanza", ["Entro 10 metri", "Oltre 10 metri"], key="f_sd")
    c_dist = SPOSTAMENTO_10MT if "Entro" in s_dist else st.number_input("Costo da Rilievo €", 0.0, key="f_sdc")

# --- MOTORE DI CALCOLO ---
tar = TIC_MT if t_new == "MT" else (TIC_DOMESTICO_LE6 if (tipo_ut == "Domestico" and p_new <= 6) else TIC_ALTRI_USI_BT)

if "Spostamento" in pratica:
    c_tec = c_dist
    delta_kw = 0.0
else:
    v_new = format_franchigia(p_new)
    v_att = format_franchigia(p_att) if p_att > 0 else 0.0
    delta_kw = max(0.0, v_new - v_att)
    c_tec = round(delta_kw * tar, 2)
    if passaggio_mt: c_tec += COSTO_PASSAGGIO_MT
    if "Nuova" in pratica: c_tec += c_dist

c_gest = round((c_tec + FISSO_BASE_CALCOLO) * 0.1, 2)
imp = round(c_tec + c_gest + ONERI_ISTRUTTORIA, 2)
iva_p = 10 if "10" in regime else (22 if "22" in regime or "P.A." in regime else 0)
iva_e = round(imp * (iva_p/100), 2)
bollo = 2.0 if (regime == "Esente" and imp > 77.47) else 0.0
totale = round((imp if "P.A." in regime else imp + iva_e) + bollo, 2)

# --- FASE 1: GENERAZIONE E ARCHIVIAZIONE ---
if nome and pod:
    st.info(f"Logica Franchigia: Nuova {format_franchigia(p_new)} - Attuale {format_franchigia(p_att)} = Delta {delta_kw} kW")
    
    st.table(pd.DataFrame({
        "Voce": ["Quota Tecnica", "Gestione Polis (10%)", "Oneri", "IVA", "TOTALE"],
        "Euro": [f"{c_tec:.2f}", f"{c_gest:.2f}", f"{ONERI_ISTRUTTORIA:.2f}", f"{iva_e:.2f}", f"**{totale:.2f}**"]
    }))

    if st.button("📄 1. GENERA PREVENTIVO E SALVA EXCEL", type="primary", use_container_width=True):
        cod = f"POLIS-2026-{st.session_state.seq:04d}"
        
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
        st.session_state.pronto_per_mail = True

        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read()
            row = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y"), "Codice": cod, "Cliente": nome, "POD": pod, "Delta": delta_kw, "Totale": totale}])
            conn.update(data=pd.concat([df, row], ignore_index=True))
            st.success("✅ Excel aggiornato e PDF Generato!")
        except: st.warning("⚠️ PDF generato, ma errore nel salvataggio Excel.")
        st.session_state.seq += 1

# --- FASE 2: INVIO MAIL (COMPARE SOLO DOPO FASE 1) ---
if st.session_state.get('pronto_per_mail'):
    st.divider()
    st.subheader("✉️ 2. Invio Email al Cliente")
    
    testo_mail_default = f"Gentile {nome},\nin allegato trasmettiamo il preventivo {st.session_state.current_cod} relativo al POD {pod}.\n\nRestiamo a disposizione per ogni chiarimento.\n\nCordiali saluti,\nPolisEnergia srl"
    corpo_mail = st.text_area("Testo della mail (modificabile):", value=testo_mail_default, height=200)
    
    c_mail1, c_mail2 = st.columns([3, 1])
    with c_mail1:
        if st.button("📧 INVIA ORA AL CLIENTE", use_container_width=True):
            if email_dest:
                try:
                    msg = MIMEMultipart()
                    msg['From'], msg['To'], msg['Subject'] = SENDER_EMAIL, email_dest, f"Preventivo PolisEnergia {st.session_state.current_cod}"
                    msg.attach(MIMEText(corpo_mail))
                    part = MIMEApplication(st.session_state.pdf_bytes, Name=f"{st.session_state.current_cod}.pdf")
                    part['Content-Disposition'] = f'attachment; filename="{st.session_state.current_cod}.pdf"'
                    msg.attach(part)
                    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
                        s.starttls(); s.login(SENDER_EMAIL, SENDER_PASSWORD); s.send_message(msg)
                    st.success(f"📩 Mail inviata con successo a {email_dest}!")
                except Exception as e: st.error(f"❌ Errore Mail: {e}")
            else: st.error("Inserisci l'indirizzo email del cliente in alto!")
            
    with c_mail2:
        st.download_button("📥 SCARICA PDF", st.session_state.pdf_bytes, f"{st.session_state.current_cod}.pdf", use_container_width=True)
