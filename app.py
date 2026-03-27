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

# --- CONFIGURAZIONE SMTP (Da completare con i tuoi dati) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "tua_mail@gmail.com"
SENDER_PASSWORD = "tua_password_applicazione" 

# --- COSTANTI TECNICHE 2026 ---
TIC_DOMESTICO_LE6 = 62.30  
TIC_ALTRI_USI_BT = 78.81
TIC_MT = 62.74
ONERI_ISTRUTTORIA = 27.42
SPOSTAMENTO_10MT = 226.36
FISSO_BASE_CALCOLO = 25.88
COSTO_PASSAGGIO_MT = 494.83
IBAN_POLIS = "IT 00 X 00000 00000 000000000000"

st.set_page_config(page_title="PolisEnergia 4.0", layout="wide")

# --- LOGICA ARROTONDAMENTO FRANCHIGIA ---
def calcola_valore_franchigia(v):
    # Se ha più di un decimale (es. 4.95) -> va all'intero superiore (5)
    # Se ha un solo decimale (es. 3.3) -> resta invariato (3.3)
    val = v * 1.1
    if round(val, 1) != round(val, 10): # Verifica se ci sono decimali oltre il primo
        return float(math.ceil(val))
    return round(val, 1)

def reset_totale():
    for key in list(st.session_state.keys()):
        if key != 'seq': del st.session_state[key]
    st.rerun()

if 'seq' not in st.session_state: st.session_state.seq = 1

# --- INTERFACCIA ---
st.title("⚡ Sistema Integrato PolisEnergia")
if st.button("🧹 PULISCI E RESETTA"): reset_totale()

with st.expander("Anagrafica e POD", expanded=True):
    c1, c2 = st.columns(2)
    nome = c1.text_input("Ragione Sociale", key="k_n").upper()
    email_cliente = c1.text_input("Email per invio preventivo", key="k_m")
    pod = c2.text_input("POD", key="k_p").upper()
    regime = c2.selectbox("IVA / Regime", ["10%", "22%", "Esente", "P.A."], key="k_r")

st.divider()

pratica = st.selectbox("Tipo Operazione", ["Aumento Potenza", "Nuova Connessione", "Spostamento Contatore"], key="k_op")
tipo_ut = st.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True, key="k_tu")

# --- LOGICA INPUT DINAMICI ---
p_att, p_new, c_dist, t_new, passaggio_mt = 0.0, 0.0, 0.0, "BT", False

if "Potenza" in pratica:
    col1, col2 = st.columns(2)
    if tipo_ut == "Altri Usi":
        passaggio_mt = col1.checkbox("🔄 Passaggio a Media Tensione (MT)?", key="k_mt")
        t_new = "MT" if passaggio_mt else "BT"
    p_att = col1.number_input("Potenza Attuale (kW)", value=3.0, step=0.5, key="k_pa")
    p_new = col2.number_input("Nuova Potenza Richiesta (kW)", value=4.5, step=0.5, key="k_pn")

elif "Nuova" in pratica:
    c1, c2 = st.columns(2)
    p_new = c1.number_input("Potenza Richiesta (kW)", value=3.0, step=0.5, key="k_pnc")
    c_dist = c2.number_input("Quota Distanza / Oneri Rilievo (€)", 0.0, key="k_dist")

elif "Spostamento" in pratica:
    s_tipo = st.radio("Distanza Spostamento", ["Entro 10 metri", "Oltre 10 metri"], key="k_sd")
    if "Entro" in s_tipo: c_dist = SPOSTAMENTO_10MT
    else: c_dist = st.number_input("Costo da Preventivo Rilievo (€)", 0.0, key="k_sdc")

# --- MOTORE DI CALCOLO ---
tar = TIC_MT if t_new == "MT" else (TIC_DOMESTICO_LE6 if (tipo_ut == "Domestico" and p_new <= 6) else TIC_ALTRI_USI_BT)

if "Spostamento" in pratica:
    c_tec = c_dist
    delta_fatturabile = 0.0
else:
    v_new = calcola_valore_franchigia(p_new)
    v_att = calcola_valore_franchigia(p_att) if p_att > 0 else 0.0
    delta_fatturabile = max(0.0, v_new - v_att)
    c_tec = round(delta_fatturabile * tar, 2)
    if passaggio_mt: c_tec += COSTO_PASSAGGIO_MT
    if "Nuova" in pratica: c_tec += c_dist # Somma distanza se nuova connessione

# Calcoli Finali
c_gest = round((c_tec + FISSO_BASE_CALCOLO) * 0.1, 2)
imp = round(c_tec + c_gest + ONERI_ISTRUTTORIA, 2)
iva_p = 10 if "10" in regime else (22 if "22" in regime or "P.A." in regime else 0)
iva_e = round(imp * (iva_p/100), 2)
bollo = 2.0 if (regime == "Esente" and imp > 77.47) else 0.0
totale = round((imp if "P.A." in regime else imp + iva_e) + bollo, 2)

# --- ANTEPRIMA ---
if nome and pod:
    st.subheader(f"📊 Riepilogo Tecnico (Delta: {delta_fatturabile} kW)")
    df_res = pd.DataFrame({
        "Voce": ["Quota TIC / Tecnica", "Gestione Polis (10%)", "Oneri Istruttoria", "IVA", "Bollo", "TOTALE"],
        "Importo (€)": [f"{c_tec:.2f}", f"{c_gest:.2f}", f"{ONERI_ISTRUTTORIA:.2f}", f"{iva_e:.2f}", f"{bollo:.2f}", f"**{totale:.2f}**"]
    })
    st.table(df_res)

    if st.button("🚀 GENERA, SALVA E INVIA", type="primary", use_container_width=True):
        cod = f"POLIS-2026-{st.session_state.seq:04d}"
        
        # 1. GENERAZIONE PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, f"PREVENTIVO {cod}", ln=1, align='C')
        pdf.set_font("Arial", "", 10); pdf.cell(0, 8, f"Spett.le {nome} - POD: {pod}", ln=1)
        pdf.cell(150, 8, f"Quota Tecnica (Delta {delta_fatturabile} kW)", 1); pdf.cell(40, 8, f"{c_tec:.2f}", 1, ln=1)
        pdf.cell(150, 8, "Totale da Corrispondere", 1); pdf.cell(40, 8, f"{totale:.2f}", 1, ln=1)
        pdf.ln(10); pdf.cell(0, 5, f"IBAN: {IBAN_POLIS}", ln=1)
        pdf.cell(0, 5, f"CAUSALE: {cod}", ln=1)
        pdf_content = pdf.output(dest='S').encode('latin-1')

        # 2. SALVATAGGIO EXCEL (GSheets)
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df_curr = conn.read()
            row = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y"), "Codice": cod, "Cliente": nome, "POD": pod, "Delta": delta_fatturabile, "Totale": totale}])
            conn.update(data=pd.concat([df_curr, row], ignore_index=True))
            st.success("✅ Dati archiviati con successo!")
        except: st.warning("⚠️ Salvataggio Excel non riuscito (controlla Secrets)")

        # 3. INVIO EMAIL
        if email_cliente:
            try:
                msg = MIMEMultipart()
                msg['From'], msg['To'], msg['Subject'] = SENDER_EMAIL, email_cliente, f"Preventivo {cod} - PolisEnergia"
                msg.attach(MIMEText(f"Buongiorno {nome}, in allegato il preventivo richiesto per il POD {pod}."))
                part = MIMEApplication(pdf_content, Name=f"{cod}.pdf")
                part['Content-Disposition'] = f'attachment; filename="{cod}.pdf"'
                msg.attach(part)
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
                    s.starttls(); s.login(SENDER_EMAIL, SENDER_PASSWORD); s.send_message(msg)
                st.success(f"📧 Mail inviata a {email_cliente}")
            except: st.error("❌ Errore invio mail")

        st.session_state.pdf_pronto = pdf_content
        st.session_state.ultimo_cod = cod
        st.session_state.seq += 1
        st.rerun()

if 'pdf_pronto' in st.session_state:
    st.download_button(f"📥 SCARICA {st.session_state.ultimo_cod}", st.session_state.pdf_pronto, f"{st.session_state.ultimo_cod}.pdf")
