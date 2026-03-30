import streamlit as st
import math
import pandas as pd
import random
import io
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# --- CONFIGURAZIONE E COSTANTI ---
st.set_page_config(page_title="Polis - Firma Elettronica", page_icon="🖋️")

# Nasconde il menù di Streamlit per tutti gli utenti
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_content_allowed=True)

st.set_page_config(page_title="PolisEnergia 4.0", layout="wide")
st.image("logo_polis.png", width=250)
TIC_DOMESTICO_LE6 = 62.30  
TIC_ALTRI_USI_BT = 78.81
TIC_MT = 62.74
ONERI_ISTRUTTORIA = 27.42
SPOSTAMENTO_10MT = 226.36
FISSO_BASE_CALCOLO = 25.88
COSTO_PASSAGGIO_MT = 494.83
IBAN_POLIS = "IT80P0103015200000007044056 - Monte dei Paschi di Siena"

try:
    SMTP_SERVER = st.secrets["EMAIL_SERVER"]
    SMTP_PORT = st.secrets["EMAIL_PORT"]
    SENDER_EMAIL = st.secrets["EMAIL_SENDER"]
    SENDER_PASSWORD = st.secrets["EMAIL_PASSWORD"]
    MAIL_CC = st.secrets.get("EMAIL_CC", "")
except:
    st.error("Configura i Secrets EMAIL (EMAIL_SERVER, etc.) su Streamlit Cloud.")
    st.stop()

# --- FUNZIONI TECNICHE ---
def format_franchigia(p):
    val = round(p * 1.1, 2)
    if round(val, 1) != val:
        return float(math.ceil(val))
    return val

def genera_pdf_polis(d):
    pdf = FPDF()
    pdf.add_page()
    
    # --- HEADER BLU ---
    pdf.set_fill_color(0, 51, 102) # Blu scuro Polis
    pdf.rect(0, 0, 210, 40, 'F')
    
    # Logo (se presente) o Testo
    try:
        pdf.image("logo_polis.png", 10, 8, 33)
    except:
        pdf.set_xy(10, 12)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("helvetica", "B", 18)
        pdf.cell(0, 10, "PolisEnergia srl")
    
    # Dati Aziendali in Bianco
    pdf.set_xy(120, 10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "", 8)
    pdf.multi_cell(80, 4, "Via Terre delle Risaie, 4 - 84131 Salerno (SA)\nP.IVA 05050950657\nassistenza@polisenergia.it - www.polisenergia.it", align='R')
    
    # --- TITOLO E DATA ---
    pdf.set_xy(10, 50)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 14)
    # Sostituito ln=1 con new_x/new_y
    pdf.cell(0, 10, f"PREVENTIVO N. {d['Codice']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"Data emissione: {datetime.now().strftime('%d/%m/%Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # --- DATI CLIENTE ---
    pdf.ln(5)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, f" SPETT.LE CLIENTE: {d['Cliente']}", border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L', fill=True)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 7, f" POD: {d['POD']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 7, f" Indirizzo: {d['Indirizzo']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # --- TABELLA PRESTAZIONI ---
    pdf.ln(10)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, " DESCRIZIONE PRESTAZIONE", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L', fill=True)
    pdf.cell(50, 10, " IMPORTO", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C', fill=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 10)
    
    # Righe Tabella
    voci = [
        ("Quota Tecnica", f"{d['C_Tec']:.2f}"),
        ("Oneri Amministrativi", f"{d['Oneri']:.2f}"),
        ("Oneri Gestione Pratica", f"{d['Gestione']:.2f}")
    ]
    
    for voce, importo in voci:
        pdf.cell(140, 8, f" {voce}", border=1)
        pdf.cell(50, 8, f"{importo} EUR ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        
    # Totali
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(140, 10, " TOTALE IMPONIBILE", border=1)
    pdf.cell(50, 10, f"{d['Imponibile']:.2f} EUR ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
    pdf.cell(140, 10, f" IVA APPLICATA ({d['IVA_Perc']}%)", border=1)
    pdf.cell(50, 10, f"{d['IVA_Euro']:.2f} EUR ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
    
    pdf.set_fill_color(220, 230, 240)
    pdf.cell(140, 12, " TOTALE DA CORRISPONDERE", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, align='L', fill=True)
    pdf.cell(50, 12, f"{d['Totale']:.2f} EUR ", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R', fill=True)
    
    # --- PAGAMENTO ---
    pdf.ln(15)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, "MODALITA' DI PAGAMENTO:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"Bonifico Bancario IBAN: {d['IBAN']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, f"CAUSALE: Accettazione Preventivo {d['Codice']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- NOTE ---
    pdf.ln(15)
    pdf.set_font("helvetica", "", 6)
    pdf.cell(0,4, " L'esecuzione della prestazione è pertanto subordinata al verificarsi delle seguenti condizioni:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0,4, "- conferma della proposta perventua entro 30 gg dalla presente richiesta;", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0,4, "- in caso di consegna della specifica tecnica, comunicazione dell'avvenuto completamento delle eventuali opere e/o concessioni,autorizzazioni, servitù a cura del cliente finale." , new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0,4, "Tale preventivo, opportunamente sottoscritto, dovrà essere inviato tramite mail all'indirizzo assistenza@polisenergia.it", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # --- FIRME ---
    pdf.set_y(-50)
    pdf.set_font("helvetica", "", 8)
    pdf.cell(0, 5, "Firma per Accettazione Cliente", border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
    pdf.ln(10)
    pdf.line(140, pdf.get_y()+5, 200, pdf.get_y()+5) # Linea Cliente
    
    # rimosso dest='S', fpdf2 gestisce l'output come byte stream
    return pdf.output()

# --- VISTA CLIENTE (FIRMA) ---
query_params = st.query_params
if "otp" in query_params:
    st.title("🖋️ Accettazione Online")
    cod_u = str(query_params.get("codice", "")).strip()
    otp_u = str(query_params.get("otp", "")).strip()
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)
    df_c = df["Codice"].astype(str).str.strip().str.replace('.0', '', regex=False)

    if cod_u in df_c.values:
        idx = df_c[df_c == cod_u].index[0]
        try:
            valore_totale = df.at[idx, "Totale"]
            importo_totale = float(valore_totale)
        except:
            importo_totale = 0.0
    
    otp_in = st.text_input("Inserisci OTP ricevuto via mail", max_chars=6)
    importo_totale = float(df.at[idx, "Totale"])
    st.warning(f"""
    ### 💳 Istruzioni per il pagamento
    Per rendere effettiva l'accettazione, è necessario effettuare il bonifico:
    - **Importo da versare:** {importo_totale:.2f} EUR
    - **IBAN:** `{IBAN_POLIS}`
    - **Causale:** `Accettazione Preventivo {cod_u}`
    """)
    if st.button("✅ FIRMA ORA"):
            if otp_in.strip() == otp_u:
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    df = conn.read(ttl=0)
                    df_c = df["Codice"].astype(str).str.strip().str.replace('.0', '', regex=False)
                    if cod_u in df_c.values:
                        idx = df_c[df_c == cod_u].index[0]
                        nome_cliente = df.at[idx, "Cliente"]
                    
                        # Aggiornamento Database
                        df.at[idx, "Stato"] = "ACCETTATO"
                        df.at[idx, "Data Firma"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                        conn.update(data=df)
                    
                    # Notifica a Carmine
                        msg = MIMEMultipart()
                        msg['From'] = SENDER_EMAIL
                        msg['To'] = SENDER_EMAIL
                        msg['cc'] = MAIL_CC
                        msg['Subject'] = f"✅ ACCETTAZIONE: {nome_cliente}"
                    
                        # Costruiamo il testo e lo attacchiamo una volta sola
                        corpo_mail = f"Il cliente {nome_cliente} ha accettato il preventivo {cod_u}."
                        msg.attach(MIMEText(corpo_mail, 'plain'))
                        
                        # Invio Mail
                        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ssl.create_default_context()) as s:
                            s.login(SENDER_EMAIL, SENDER_PASSWORD)
                            s.send_message(msg)
                    
                        st.success("Firmato!")
                        st.balloons()
                    else: 
                        st.error("Non trovato.")
                except Exception as e: 
                    st.error(f"Errore: {e}")
            else: 
                st.error("OTP errato.")
    st.stop()

# --- VISTA CARMINE ---
st.title("⚡ PolisEnergia - Gestione Preventivi")

if st.button("🧹 PULISCI TUTTO", use_container_width=True):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# 1. DATI
with st.container():
    c1, c2 = st.columns(2)
    nome = c1.text_input("Ragione Sociale", key="n").upper()
    email_dest = c1.text_input("Email Cliente", key="m")
    pod = c2.text_input("POD", key="p").upper()
    indirizzo = c1.text_input("Indirizzo Impianto", key="ind")
    regime = c2.selectbox("Regime IVA", ["10%", "22%", "Esente", "P.A."], key="r")

st.divider()

# 2. CALCOLO (TUA LOGICA ORIGINALE)
c3, c4 = st.columns([2, 1])
pratica = c3.selectbox("Tipo Pratica", ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento Contatore"], key="prat")
tipo_ut = c4.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True, key="ut")

p_att, p_new, c_dist, passaggio_mt, t_partenza = 0.0, 0.0, 0.0, False, "BT"

if "Potenza" in pratica or "Subentro" in pratica:
    col1, col2 = st.columns(2)
    if tipo_ut == "Altri Usi":
        t_partenza = col1.selectbox("Tensione", ["BT", "MT"], key="t")
        if t_partenza == "BT": passaggio_mt = col1.checkbox("Passaggio a MT?", key="mt")
    p_att = col1.number_input("kW Attuali", value=3.0, key="pa")
    p_new = col2.number_input("kW Richiesti", value=4.5, key="pn")
elif "Nuova" in pratica:
    p_new = st.number_input("kW Richiesti", value=3.0, key="pnc")
    c_dist = st.number_input("Quota Distanza €", 0.0, key="dist")
elif "Spostamento" in pratica:
    s_dist = st.radio("Distanza", ["Entro 10 metri", "Oltre 10 metri"], key="sd")
    c_dist = SPOSTAMENTO_10MT if "Entro" in s_dist else st.number_input("Costo Rilievo €", 0.0, key="sdc")

# --- NUOVA LOGICA LIMITATORE / FRANCHIGIA ---
limitatore = False
if tipo_ut == "Altri Usi" and 15 < p_new <= 30:
    # Il flag appare solo in questa condizione ed è attivo di default
    limitatore = st.checkbox("Abilita Limitatore (Franchigia +10%)", value=True, key="lim_flag")

# Logica Potenza
if p_new > 0:
    # Caso 1: Potenza <= 30 kW
    if p_new <= 30:
        # Applichiamo la franchigia del 10% (es. 20 -> 22) SOLO SE:
        # - È Domestico 
        # - OPPURE è Altri Usi e il flag limitatore è attivo
        if tipo_ut == "Domestico" or (tipo_ut == "Altri Usi" and limitatore):
            v_new = round(p_new * 1.1, 1)
            v_att = round(p_att * 1.1, 1) if p_att > 0 else 0.0
        else:
            # Altri Usi SENZA limitatore: calcolo netto
            v_new = p_new
            v_att = p_att
            
        delta = round(v_new - v_att, 1)
        
        # Selezione Tariffa TIC
        if (tipo_ut == "Domestico" and p_new <= 6):
            tar = TIC_DOMESTICO_LE6
        elif (t_partenza == "MT" or passaggio_mt):
            tar = TIC_MT
        else:
            tar = TIC_ALTRI_USI_BT
            
    # Caso 2: Potenza > 30 kW (Sempre calcolo netto)
    else:
        delta = round(p_new - p_att, 1)
        tar = TIC_MT if (t_partenza == "MT" or passaggio_mt) else TIC_ALTRI_USI_BT

# Calcoli Economici Finali
c_tec = c_dist if "Spostamento" in pratica else round(delta * tar, 2)
if passaggio_mt: c_tec += COSTO_PASSAGGIO_MT
if "Nuova" in pratica: c_tec += c_dist

c_gest = round((c_tec + FISSO_BASE_CALCOLO) * 0.1, 2)
imp = round(c_tec + c_gest + ONERI_ISTRUTTORIA, 2)
iva_p = 10 if "10" in regime else (22 if "22" in regime or "P.A." in regime else 0)
iva_e = round(imp * (iva_p/100), 2)
bollo = 2.0 if (regime == "Esente" and imp > 77.47) else 0.0
totale = round(imp + bollo, 2) if "P.A." in regime else round(imp + iva_e + bollo, 2)

# --- 3. ANTEPRIMA ---
st.subheader("📊 Anteprima Calcolo")
col_t1, col_t2 = st.columns([2, 1])
with col_t1:
    st.table(pd.DataFrame({
        "Voce": ["Quota TIC", "Gestione Polis", "Istruttoria", "IVA", "Bollo"],
        "Valore (€)": [f"{c_tec:.2f}", f"{c_gest:.2f}", f"{ONERI_ISTRUTTORIA:.2f}", f"{iva_e:.2f}", f"{bollo:.2f}"]
    }))
with col_t2:
    st.metric("TOTALE", f"{totale:.2f} €")
    if "Spostamento" not in pratica:
        st.info(f"Delta: {delta} kW | Tariffa: {tar} €/kW")

# --- 4. AZIONI ---
if st.button("📄 1. GENERA PDF E ARCHIVIA", type="primary", use_container_width=True):
    cod = datetime.now().strftime("%y%m%d%H%M%S")
    st.session_state.current_cod = cod
    st.session_state.pdf_bytes = genera_pdf_polis({"Codice": cod, "Cliente": nome, "POD": pod, "Indirizzo": indirizzo, "C_Tec": c_tec, "Oneri": ONERI_ISTRUTTORIA, "Gestione": c_gest, "Imponibile": imp, "IVA_Perc": iva_p, "IVA_Euro": iva_e, "Totale": totale, "IBAN": IBAN_POLIS})
    
    # Salva GSheets
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)
    row = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y"), "Codice": cod, "Cliente": nome, "POD": pod, "Totale": totale, "Stato": "Inviato"}])
    conn.update(data=pd.concat([df, row], ignore_index=True))
    st.success(f"Archiviato con codice {cod}")

if 'pdf_bytes' in st.session_state:
    pdf_buffer = io.BytesIO(st.session_state.pdf_bytes)
    st.download_button(label="📥 SCARICA PDF",
        data=pdf_buffer, # Ora passiamo il buffer, non la variabile diretta
        file_name=f"{st.session_state.current_cod}.pdf",
        mime="application/pdf",
        use_container_width=True,
        key="btn_download_finale"
    )
    
    st.divider()
    otp = str(random.randint(100000, 999999))
    link = f"https://preventivatore-pratiche-connessione.streamlit.app/?codice={st.session_state.current_cod}&otp={otp}"
    
    testo_pre = f"Spett.le {nome},\nin allegato il preventivo {st.session_state.current_cod}.\nPuoi firmare qui: {link}\nOTP: {otp}"
    corpo_mail = st.text_area("Modifica Testo Mail:", value=testo_pre, height=150)
    
    if st.button("📧 2. INVIA EMAIL AL CLIENTE", use_container_width=True):
        msg = MIMEMultipart(); msg['From'] = SENDER_EMAIL; msg['To'] = email_dest; msg['Cc'] = MAIL_CC; msg['Subject'] = f"Preventivo {st.session_state.current_cod}"
        msg.attach(MIMEText(corpo_mail, 'plain'))
        part = MIMEApplication(st.session_state.pdf_bytes, Name=f"{st.session_state.current_cod}.pdf")
        part['Content-Disposition'] = f'attachment; filename="{st.session_state.current_cod}.pdf"'
        msg.attach(part)
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ssl.create_default_context()) as s:
            s.login(SENDER_EMAIL, SENDER_PASSWORD); s.send_message(msg)
        st.success("Email inviata!")
