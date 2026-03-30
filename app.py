import streamlit as st
import math
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

try:
    query_params = st.query_params
except:
    query_params = {}

if "otp" in query_params:
    # --- VISTA CLIENTE ---
    st.title("🖋️ Accettazione Preventivo Online")
    
    codice_prev = query_params.get("codice", "N/D")
    otp_corretto = str(query_params.get("otp", ""))

    st.info(f"Stai confermando il preventivo: **{codice_prev}**")
    
    # Corretto: otp_input (variabile) e st.text_input (funzione)
    otp_input = st.text_input("Inserisci il codice OTP ricevuto via mail", max_chars=6)

    if st.button("✅ ACCETTA E FIRMA ORA"):
        if str(otp_input) == otp_corretto:
            try:
                # 1. Connessione e aggiornamento (Corretto 'gsheets')
                conn = st.connection("gsheets", type=GSheetsConnection)
                df = conn.read()

                if codice_prev in df["Codice"].values:
                    df.loc[df["Codice"] == codice_prev, "Stato"] = "ACCETTATO"
                    df.loc[df["Codice"] == codice_prev, "Data Firma"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    conn.update(data=df)
                    
                    st.success("🎉 Preventivo firmato con successo!")
                    st.balloons()
                    

                    # 2. Generazione PDF Ricevuta
                    pdf_firmato = FPDF()
                    pdf_firmato.add_page()
                    pdf_firmato.set_font("Arial", "B", 16)
                    pdf_firmato.cell(0, 10, f"CONFERMA ACCETTAZIONE {codice_prev}", ln=1, align='C')
                    pdf_firmato.ln(10)
                    pdf_firmato.set_font("Arial", "", 12)
                    
                    testo_pdf = (f"Il presente documento attesta che il cliente ha accettato i termini "
                                 f"in data {datetime.now().strftime('%d/%m/%Y')} alle ore {datetime.now().strftime('%H:%M')}.\n"
                                 f"Validazione tramite OTP: {otp_input}\n"
                                 f"Stato: FIRMATO ELETTRONICAMENTE")
                    
                    pdf_firmato.multi_cell(0, 10, testo_pdf)
                    pdf_output = pdf_firmato.output(dest="S").encode('latin-1')

                    # 3. Invio Notifica Mail a te
                    try:
                        msg_notifica = MIMEMultipart()
                        msg_notifica['From'] = SENDER_EMAIL
                        msg_notifica['To'] = SENDER_EMAIL
                        msg_notifica['Subject'] = f"🔔 ACCETTATO: {codice_prev}"
                        msg_notifica.attach(MIMEText(f"Il cliente ha firmato il preventivo {codice_prev}", 'plain'))
                        
                        import ssl
                        context_not = ssl.create_default_context()
                        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context_not) as server:
                            server.login(SENDER_EMAIL, SENDER_PASSWORD)
                            server.send_message(msg_notifica)
                    except:
                        pass # Se la notifica a te fallisce, non blocchiamo il cliente

                    # 4. Tasto Download per il cliente
                    st.download_button(
                        label="📥 Scarica la tua ricevuta di firma (PDF)",
                        data=pdf_output,
                        file_name=f"Ricevuta_Firma_{codice_prev}.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.error("Errore: Preventivo non trovato nel database")
                    
            except Exception as e:
                st.error(f"Errore tecnico: {e}")
        else:
            st.error("❌ Codice OTP errato. Riprova.")
            
    st.stop() # Interrompe l'app qui per il cliente

st.title("Gestione Preventivi Polis")
st.write("Benvenuto Carmine. Qui puoi generare nuovi OTP.")
    
# --- CONFIGURAZIONE SMTP ---
SMTP_SERVER = st.secrets["EMAIL_SERVER"]
SMTP_PORT = st.secrets["EMAIL_PORT"]
SENDER_EMAIL = st.secrets["EMAIL_SENDER"]
SENDER_PASSWORD = st.secrets["EMAIL_PASSWORD"]
MAIL_CC = st.secrets["EMAIL_CC"]

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

from fpdf.enums import XPos, YPos

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
if st.button("🧹 PULISCI TUTTO", use_container_width=True):
    st.session.state.clear()
    st.rerun()

# 1. DATI ANAGRAFICI
with st.container():
    c1, c2 = st.columns(2)
    nome = c1.text_input("Ragione Sociale", key="n").upper()
    indirizzo = c1.text_input("Indirizzo", key="in_ind")
    email_dest = c1.text_input("Email Cliente", key="m")
    pod = c2.text_input("POD", key="p").upper()
    regime = c2.selectbox("Regime IVA", ["10%", "22%", "Esente", "P.A."], key="r")

st.divider()

# 2. SELEZIONE PRATICA
c3, c4 = st.columns([2, 1])
pratica = c3.selectbox("Tipo Pratica", ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento Contatore"], key="prat")
tipo_ut = c4.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True, key="ut")

p_att, p_new, c_dist, t_new, passaggio_mt = 0.0, 0.0, 0.0, "BT", False
t_partenza="BT"
delta, tar = 0.0, 0.0

# --- 1. INIZIALIZZAZIONE VARIABILI (Sempre all'inizio) ---
p_att, p_new, c_dist, passaggio_mt = 0.0, 0.0, 0.0, False
t_partenza = "BT"
delta, tar = 0.0, 0.0

# --- 2. INPUT UTENTE (BLOCCHI IF/ELIF) ---
if "Potenza" in pratica or "Subentro" in pratica:
    col1, col2 = st.columns(2)
    if tipo_ut == "Altri Usi":
        t_partenza = col1.selectbox("Tensione di Partenza", ["BT", "MT"], key="t_part")
        if t_partenza == "BT":
            passaggio_mt = col1.checkbox("🔄 Passaggio a Media Tensione (MT)?", key="mt")
    p_att = col1.number_input("Potenza Attuale (kW)", value=3.0, step=0.5, key="pa")
    p_new = col2.number_input("Potenza Richiesta (kW)", value=4.5, step=0.5, key="pn")

elif "Nuova" in pratica:
    p_new = st.number_input("Potenza Richiesta (kW)", value=3.0, key="pnc")
    c_dist = st.number_input("Quota Distanza €", 0.0, key="dist")

elif "Spostamento" in pratica:
    s_dist = st.radio("Distanza", ["Entro 10 metri", "Oltre 10 metri"], key="sd")
    c_dist = SPOSTAMENTO_10MT if "Entro" in s_dist else st.number_input("Costo Rilievo €", 0.0, key="sdc")

# --- 3. LOGICA LIMITATORE E TARIFFE (FUORI DAGLI IF PRECEDENTI) ---
if p_new > 0:
    if p_new <= 30:
        # Caso Sotto 30 kW: Franchigia 10%
        v_new = round(p_new * 1.1, 1)
        v_att = round(p_att * 1.1, 1) if p_att > 0 else 0.0
        delta = round(v_new - v_att, 1)
        
        # Scelta Tariffa
        if tipo_ut == "Domestico" and p_new <= 6:
            tar = TIC_DOMESTICO_LE6
        else:
            tar = TIC_MT if (t_partenza == "MT" or passaggio_mt) else TIC_ALTRI_USI_BT
    else:
        # Caso Oltre 30 kW: Potenza secca
        delta = round(p_new - p_att, 1)
        tar = TIC_MT if (t_partenza == "MT" or passaggio_mt) else TIC_ALTRI_USI_BT

# --- 4. CALCOLO QUOTA TECNICA FINALE ---
if "Spostamento" in pratica:
    c_tec = c_dist
else:
    c_tec = round(delta * tar, 2)
    if passaggio_mt: 
        c_tec += COSTO_PASSAGGIO_MT
    if "Nuova" in pratica: 
        c_tec += c_dist

# --- 5. RIEPILOGO ONERI E TOTALI ---
c_gest = round((c_tec + FISSO_BASE_CALCOLO) * 0.1, 2)
imp = round(c_tec + c_gest + ONERI_ISTRUTTORIA, 2)

# Calcolo IVA e Bollo
iva_p = 10 if "10" in regime else (22 if "22" in regime or "P.A." in regime else 0)
iva_e = round(imp * (iva_p/100), 2)
bollo = 2.0 if (regime == "Esente" and imp > 77.47) else 0.0

# Totale Finale
if "P.A." in regime:
    totale = round(imp + bollo, 2) # IVA Scissa per P.A.
else:
    totale = round(imp + iva_e + bollo, 2)

# --- 3. ANTEPRIMA ---
st.subheader("📊 Anteprima Calcolo")
if "Potenza" in pratica or "Subentro" in pratica or "Nuova" in pratica:
    # Usiamo 'delta' (che è il nome definito nel calcolo) invece di 'delta_kw'
    st.info(f"📊 **Logica Potenza:** {p_new} kW richiesti. Delta fatturabile: **{delta} kW**")

col_tab1, col_tab2 = st.columns([2, 1])
with col_tab1:
    st.table(pd.DataFrame({
        "Descrizione": ["Quota Tecnica TIC", "Gestione Polis (10%)", "Oneri Istruttoria", "IVA", "Bollo"],
        "Importo (€)": [f"{c_tec:.2f}", f"{c_gest:.2f}", f"{ONERI_ISTRUTTORIA:.2f}", f"{iva_e:.2f}", f"{bollo:.2f}"]
    }))
with col_tab2:
    st.metric("TOTALE", f"{totale:.2f} €")

# --- 4. AZIONI (GENERA, ARCHIVIA) ---
st.subheader("Riepilogo Parametri di Calcolo")
col_r1, col_r2 = st.columns(2)

with col_r1:
    st.write(f"**Tipo Utenza:** {tipo_ut}")
    st.write(f"**Tensione:** {'Media (MT)' if (t_partenza == 'MT' or passaggio_mt) else 'Bassa (BT)'}")

with col_r2:
    if "Spostamento" not in pratica:
        st.write(f"**Delta Potenza:** {delta} kW")
        st.write(f"**Tariffa applicata (€/kW):** {tar}")
    else:
        st.write(f"**Costo Fisso Spostamento:** {c_dist} €")

st.divider()
if st.button("📁 GENERA PDF E SALVA SU EXCEL", type="primary", use_container_width=True):
    cod = datetime.now().strftime("%y%m%d%H%M%S")
    
    # PDF
    dati_pdf = {
        "Codice": cod,
        "Cliente": nome,
        "Indirizzo": indirizzo if ('indirizzo' in locals() and indirizzo) else "N.D.",
        "POD": pod,
        "C_Tec": c_tec,
        "Oneri": ONERI_ISTRUTTORIA,
        "Gestione": c_gest,
        "Imponibile": imp,
        "IVA_Perc": iva_p,
        "IVA_Euro": iva_e,
        "Totale": totale,
        "IBAN": IBAN_POLIS
    }
    
    output = genera_pdf_polis(dati_pdf)
    
    # Gestione Errore Bytes
    if isinstance(output, str):
        st.session_state.pdf_bytes = output.encode('latin-1')
    else:
        st.session_state.pdf_bytes = bytes(output)
        
    st.session_state.current_cod = cod
    
    # EXCEL
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read()
        row = pd.DataFrame([{"Data": datetime.now().strftime("%d/%m/%Y"), "Codice": cod, "Cliente": nome, "POD": pod, "Delta": delta, "Totale": totale}])
        conn.update(data=pd.concat([df, row], ignore_index=True))
        st.success(f"✅ Preventivo {cod} archiviato!")
    except: st.warning("PDF generato, ma errore Excel.")
    
    st.session_state.seq += 1
    
# --- 5. MAIL CON LOGICA DI FIRMA AUTOMATICA ---
if 'pdf_bytes' in st.session_state:
    st.divider()
    st.subheader("✉️ 2. Invio Email per Accettazione Automatica")
    
    # 1. Generiamo l'OTP e il link (se non già presenti in sessione)
    if 'current_otp' not in st.session_state:
        st.session_state.current_otp = str(random.randint(100000, 999999))
    
    # Indirizzo della tua app pubblicata (cambialo con quello reale)
    url_app = "https://preventivatore-pratiche-connessione.streamlit.app/" 
    # Creiamo il link magico
    link_firma = f"{url_app}?codice={st.session_state.current_cod}&otp={st.session_state.current_otp}"
    
    # 2. Prepariamo il messaggio con il link
    testo_predefinito = (
        f"Gentile cliente,\n"
        f"in allegato trasmettiamo il preventivo {st.session_state.current_cod}.\n\n"
        f"Puoi accettare e firmare il preventivo in un click cliccando qui:\n"
        f"{link_firma}\n\n"
        f"Codice di sicurezza OTP: {st.session_state.current_otp}\n\n"
        f"Restiamo a disposizione per ogni chiarimento.\n"
        f"PolisEnergia srl"
    )
    
    corpo_mail = st.text_area("Modifica il testo della mail:", value=testo_predefinito, height=200)
    
    c_btn1, c_btn2 = st.columns(2)
    
    with c_btn1:
        if st.button("📧 INVIA ORA E ATTIVA FIRMA", use_container_width=True):
            if not email_dest or "@" not in email_dest:
                st.error("❌ Inserisci un indirizzo email valido.")
            else:
                try:
                    with st.spinner("Invio in corso..."):
                        # --- A. SALVATAGGIO SU GSHEETS (Ponte per l'automazione) ---
                        # Salviamo l'OTP nel foglio così l'app lo "riconoscerà" quando il cliente clicca
                        conn = st.connection("gsheets", type=GSheetsConnection)
                        df = conn.read()
                        nuova_riga = pd.DataFrame([{
                            "Data": datetime.now().strftime("%d/%m/%Y"),
                            "Codice": st.session_state.current_cod,
                            "Cliente": nome,
                            "Email": email_dest,
                            "OTP": st.session_state.current_otp,
                            "Stato": "Inviato"
                        }])
                        conn.update(data=pd.concat([df, nuova_riga], ignore_index=True))

                        # --- B. INVIO EMAIL (Aruba) ---
                        msg = MIMEMultipart()
                        msg['From'] = SENDER_EMAIL
                        msg['To'] = email_dest
                        msg['Cc'] = MAIL_CC
                        msg['Subject'] = f"PolisEnergia srl: Preventivo {st.session_state.current_cod}"
                        msg.attach(MIMEText(corpo_mail, 'plain'))

                        filename = f"{st.session_state.current_cod}.pdf"
                        part = MIMEApplication(st.session_state.pdf_bytes, Name=filename)
                        part['Content-Disposition'] = f'attachment; filename="{filename}"'
                        msg.attach(part)

                        import ssl
                        context = ssl.create_default_context()
                        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
                            server.login(SENDER_EMAIL, SENDER_PASSWORD)
                            server.send_message(msg)
                        
                        st.success("✅ Preventivo inviato! Ora il cliente può firmare autonomamente dal link.")
                except Exception as e:
                    st.error(f"❌ Errore: {e}")
    
    with c_btn2:
        # Tasto Download sempre disponibile
        st.download_button(
            label="📥 SCARICA IL PDF",
            data=st.session_state.pdf_bytes,
            file_name=f"{st.session_state.current_cod}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
