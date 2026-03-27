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

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="PolisEnergia Preventivatore 4.0", page_icon="⚡", layout="wide")

# --- INIZIALIZZAZIONE SESSION STATE ---
if 'pdf_pronto' not in st.session_state: st.session_state.pdf_pronto = None
if 'ultimo_codice' not in st.session_state: st.session_state.ultimo_codice = "---"
if 'dati_anteprima' not in st.session_state: st.session_state.dati_anteprima = None

# --- COSTANTI TARIFFARIE 2026 ---
TIC_2026 = {
    "DOM_LE6": 62.30, 
    "BT_ALTRI": 78.81, 
    "MT": 62.74,
    "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 226.36, 
    "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88
}

# --- CONNESSIONE GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Errore connessione Cloud: {e}")

# --- FUNZIONE INVIO MAIL ARUBA ---
def invia_mail_aruba(destinatario, oggetto, corpo, pdf_bytes, nome_file):
    try:
        # Recupero credenziali dai Secrets (sezione gsheets o root)
        sender = st.secrets["connections"]["gsheets"]["EMAIL_SENDER"]
        password = st.secrets["connections"]["gsheets"]["EMAIL_PASSWORD"]
        server_smtp = st.secrets["connections"]["gsheets"]["EMAIL_SERVER"]
        porta_smtp = int(st.secrets["connections"]["gsheets"]["EMAIL_PORT"])

        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = destinatario
        msg['Subject'] = oggetto
        msg.attach(MIMEText(corpo, 'plain'))
        
        part = MIMEApplication(pdf_bytes, Name=nome_file)
        part['Content-Disposition'] = f'attachment; filename="{nome_file}"'
        msg.attach(part)
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(server_smtp, porta_smtp, context=context) as server:
            server.login(sender, password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Errore Aruba: {e}")
        return False

# --- FUNZIONE GENERAZIONE PDF ---
def genera_pdf(d, cod_pratica):
    pdf = FPDF()
    pdf.add_page()
    # Header Blu Polis
    pdf.set_fill_color(0, 29, 61); pdf.rect(0, 0, 210, 45, 'F')
    if os.path.exists("logo_polis.png"):
        pdf.image("logo_polis.png", 10, 10, 33)
    
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
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 8, f" Quota Potenza/Tecnica ({d['t_att']} -> {d['t_new']})", 1); pdf.cell(50, 8, f"{d['c_tec']:.2f} EUR", 1, 1, 'R')
    if d['c_dist'] > 0:
        pdf.cell(140, 8, " Quota Distanza / Oneri Rilievo", 1); pdf.cell(50, 8, f"{d['c_dist']:.2f} EUR", 1, 1, 'R')
    
    pdf.cell(140, 8, " Oneri Amministrativi", 1); pdf.cell(50, 8, f"{TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Gestione Pratica", 1); pdf.cell(50, 8, f"{d['c_gest']:.2f} EUR", 1, 1, 'R')
    
    pdf.ln(2); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 9, " IMPONIBILE", 1); pdf.cell(50, 9, f"{d['imponibile']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, f" IVA ({d['iva_perc']}%)", 1); pdf.cell(50, 9, f"{d['iva_euro']:.2f} EUR", 1, 1, 'R')
    if d['bollo'] > 0:
        pdf.cell(140, 9, " BOLLO", 1); pdf.cell(50, 9, "2.00 EUR", 1, 1, 'R')
    
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Helvetica", "B", 11)
    pdf.cell(140, 11, " TOTALE DA PAGARE", 1, 0, 'L', True); pdf.cell(50, 11, f"{d['totale']:.2f} EUR", 1, 1, 'R', True)
    
    pdf.ln(10); pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 5, f"Causale: {cod_pratica}\nIBAN: PolisEnergia srl - IT80P0103015200000007044056")
    return pdf.output()

# --- INTERFACCIA UTENTE ---
st.title("⚡ PolisEnergia Suite")
st.caption(f"Versione 4.0 | Ultimo Codice Generato: {st.session_state.ultimo_codice}")

with st.form("main_form"):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 Anagrafica")
        nome = st.text_input("Ragione Sociale").upper()
        indirizzo = st.text_input("Indirizzo")
        uso = st.selectbox("Regime Fiscale", ["IVA 10%", "IVA 22%", "P.A.", "Esente"])
        pod = st.text_input("POD").upper()
    
    with col2:
        st.subheader("⚙️ Dati Tecnici")
        tipo_ut = st.radio("Destinazione", ["Domestico", "Altri Usi"], horizontal=True)
        
        # Gestione Tensioni (Solo per Altri Usi)
        if tipo_ut == "Altri Usi":
            ct1, ct2 = st.columns(2)
            t_att = ct1.radio("Tensione Attuale", ["BT", "MT"], horizontal=True)
            t_new = ct2.radio("Tensione Richiesta", ["BT", "MT"], horizontal=True)
        else:
            t_att = t_new = "BT"

        pratica = st.selectbox("Tipo Pratica", ["Aumento Potenza", "Nuova Connessione", "Spostamento", "Subentro"])
        
        cp1, cp2 = st.columns(2)
        p_att = cp1.number_input("Potenza Attuale (kW)", value=3.0, step=0.5)
        p_new = cp2.number_input("Nuova Potenza (kW)", value=6.0, step=0.5)
        
        c_dist = st.number_input("Quota Distanza (€)", value=0.0)
        s_choice = ""
        if pratica == "Spostamento":
            s_choice = st.radio("Distanza Spostamento", ["Entro 10m", "Oltre 10m"], horizontal=True)

        app_gest = st.checkbox("Gestione Polis (10%)", value=True)

    submit = st.form_submit_button("📁 GENERA PREVENTIVO")

# --- LOGICA DI CALCOLO ---
if submit:
    if nome and indirizzo:
        # 1. Determinazione Tariffe TIC
        def get_tariffa(tens, pot, ut):
            if tens == "MT": return TIC_2026["MT"]
            if ut == "Domestico" and pot <= 6: return TIC_2026["DOM_LE6"]
            return TIC_2026["BT_ALTRI"]

        tar_att = get_tariffa(t_att, p_att, tipo_ut)
        tar_new = get_tariffa(t_new, p_new, tipo_ut)

        # 2. Calcolo Quota Tecnica
        if pratica == "Spostamento":
            c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in s_choice else TIC_2026["SPOST_OLTRE_10"]
        else:
            # Franchigia 1.1 (Solo BT <= 30kW)
            f_att = 1.1 if (t_att == "BT" and p_att <= 30) else 1.0
            p_partenza_effettiva = p_att * f_att
            p_arrivo_arrotondata = math.ceil(p_new)
            
            # Differenziale: (Nuova Potenza * Nuova Tariffa) - (Vecchia Potenza * Vecchia Tariffa)
            c_tec = max(0.0, (p_arrivo_arrotondata * tar_new) - (p_partenza_effettiva * tar_att))

        # 3. Calcolo Totali
        c_gest = (c_tec + c_dist + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if app_gest else 0.0
        imp = c_tec + c_dist + c_gest + TIC_2026["ISTRUTTORIA"]
        iva_p = 10 if "10" in uso else (22 if ("22" in uso or "P.A." in uso) else 0)
        iva_e = imp * (iva_p/100)
        bollo = 2.0 if (uso == "Esente" and imp > 77.47) else 0.0
        tot = (imp if "P.A." in uso else imp + iva_e) + bollo

        # 4. Preparazione Dati
        dati = {
            'nome': nome, 'indirizzo': indirizzo, 'pod': pod if pod else "N.D.",
            'pratica': pratica, 't_att': t_att, 't_new': t_new, 'c_tec': c_tec, 
            'c_dist': c_dist, 'c_gest': c_gest, 'p_att': p_att, 'p_new': p_new, 
            'imponibile': imp, 'iva_perc': iva_p, 'iva_euro': iva_e, 'bollo': bollo, 'totale': tot
        }

        # 5. Generazione PDF e Salvataggio Stato
        cod_pratica = f"BA{int(tot)}{datetime.now().second % 10}"
        st.session_state.pdf_pronto = genera_pdf(dati, cod_pratica)
        st.session_state.ultimo_codice = cod_pratica
        st.session_state.dati_anteprima = dati

        # 6. Archiviazione Google Sheets
        try:
            df = conn.read(ttl=0)
            nuova_riga = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y"), "Codice": cod_pratica, "Cliente": nome, "Totale": tot}])
            conn.update(data=pd.concat([df, nuovo], ignore_index=True))
        except: pass

        st.rerun()

# --- SEZIONE INVIO MAIL (Visibile solo dopo il calcolo) ---
if st.session_state.pdf_pronto:
    st.divider()
    st.subheader("✉️ Invia il preventivo")
    
    col_mail1, col_mail2 = st.columns([1, 2])
    with col_mail1:
        mail_cliente = st.text_input("Email destinatario", key="email_client")
        st.download_button("📥 SCARICA PDF", data=bytes(st.session_state.pdf_pronto), file_name=f"{st.session_state.ultimo_codice}.pdf")
    
    with col_mail2:
        testo_def = f"Gentile Cliente, in allegato il preventivo {st.session_state.ultimo_codice} relativo alla pratica di {st.session_state.dati_anteprima['pratica']}."
        corpo_mail = st.text_area("Messaggio", value=testo_def, key="mail_body")
        
        if st.button("🚀 INVIA ORA"):
            if mail_cliente:
                with st.spinner("Invio tramite Aruba..."):
                    successo = invia_mail_aruba(
                        mail_cliente, 
                        f"Preventivo PolisEnergia - {st.session_state.ultimo_codice}", 
                        corpo_mail, 
                        st.session_state.pdf_pronto, 
                        f"{st.session_state.ultimo_codice}.pdf"
                    )
                    if successo:
                        st.success("✅ Email inviata con successo!")
                        st.balloons()
            else:
                st.error("Inserisci un indirizzo email!")
