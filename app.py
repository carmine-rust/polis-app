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

# --- CONNESSIONE A GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Errore connessione Cloud: {e}")

# --- FUNZIONE INVIO MAIL  ---
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

def clean_filename(text):
    if not text: return "CLIENTE"
    text = re.sub(r'[^\w\s-]', '', text).strip()
    return re.sub(r'[-\s]+', '_', text).upper()

def reset_campi():
    # Elenco delle chiavi da svuotare (aggiungi quelle che usi)
    chiavi_da_pulire = ['ragione_sociale', 'indirizzo_cliente', 'pod_cliente', 'p_att', 'p_new']
    for key in chiavi_da_pulire:
        if key in st.session_state:
            st.session_state[key] = "" if isinstance(st.session_state[key], str) else 0.0

TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "SPOST_ENTRO_10": 226.36, "SPOST_OLTRE_10": 226.36, 
    "ISTRUTTORIA": 27.42, "FISSO_BASE_CALCOLO": 25.88
}

# --- FUNZIONE PDF ---
def genera_pdf(d, cod_pratica):
    pdf = FPDF()
    pdf.add_page()
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
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 8, " ONERI DISTRIBUTORE", 1, 1, 'L', True)
    pdf.set_font("Helvetica", "", 10)
    
    desc_pot = f" Quota Potenza: da {d['p_att']}kW ({d['t_att']}) a {d['p_new']}kW ({d['t_new']})"
    pdf.cell(140, 8, desc_pot, 1); pdf.cell(50, 8, f"{d['c_tec']:.2f} EUR", 1, 1, 'R')
    
    if d['c_dist'] > 0:
        pdf.cell(140, 8, f" Quota Distanza / Oneri Rilievo", 1); pdf.cell(50, 8, f"{d['c_dist']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Amministrativi", 1); pdf.cell(50, 8, f"{TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    
    pdf.cell(140, 8, " Oneri Gestione Pratica", 1); pdf.cell(50, 8, f"{d['c_gest']:.2f} EUR", 1, 1, 'R')
    
    pdf.ln(2); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 9, " IMPONIBILE", 1); pdf.cell(50, 9, f"{d['imponibile']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, f" IVA ({d['iva_perc']}%)", 1); pdf.cell(50, 9, f"{d['iva_euro']:.2f} EUR", 1, 1, 'R')
    if d['bollo'] > 0:
        pdf.cell(140, 9, "BOLLO", 1); pdf.cell(50, 9, "2.00 EUR", 1, 1, 'R')
    
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Helvetica", "B", 11)
    pdf.cell(140, 11, " TOTALE DA PAGARE", 1, 0, 'L', True); pdf.cell(50, 11, f"{d['totale']:.2f} EUR", 1, 1, 'R', True)
    
    pdf.ln(10); pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(110, 4, f"Causale: {cod_pratica}\nIBAN:PolisEnergia srl - IT80P0103015200000007044056 - Monte dei Paschi di Siena")
    pdf.ln (70)
    curr_y = pdf.get_y()
    pdf.set_xy(130, curr_y)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(70, 5, "Per Accettazione (Il Cliente)", ln=1, align='C')
    pdf.set_xy(130, pdf.get_y() + 10)
    pdf.cell(70, 0, "", border="T") 
    return pdf.output()

# --- INTERFACCIA ---
st.title("⚡ PolisEnergia")
st.caption(f"Preventivatore 4.0 | Codice: {st.session_state.ultimo_codice}")

if st.button("🔴 RESET / PULISCI TUTTI I CAMPI"):
    reset_campi()

st.divider()

with st.form("main_form"):
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📋 1. Anagrafica")
        nome = st.text_input("Ragione Sociale", key="ragione_sociale").upper()
        indirizzo = st.text_input("Indirizzo", key="indirizzo_cliente")
        uso = st.selectbox("Regime Fiscale", ["IVA 10%", "IVA 22%", "P.A.", "Esente"])
        pod = st.text_input("POD", key="pod_cliente").upper()

    with c2:
        st.subheader("⚙️ 2. Dati Tecnici")
        pratica = st.selectbox("Tipo di Pratica", ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento"])
        tipo_ut = st.radio("Destinazione", ["Domestico", "Altri Usi"], horizontal=True)
        
        # Inizializzazione variabili
        p_att, p_new, c_dist = 0.0, 0.0, 0.0
        t_att, t_new = "BT", "BT"

        # --- LOGICA TENSIONE SPECIFICA ---
        if tipo_ut == "Altri Usi":
            # IL FLAG COMPARE SOLO PER AUMENTI O SUBENTRI
            if pratica in ["Aumento Potenza", "Subentro con Modifica"]:
                flag_mt = st.checkbox("🔄 Passaggio da BT a MT?")
                if flag_mt:
                    t_att, t_new = "BT", "MT"
                else:
                    t_att = t_new = st.radio("Tensione", ["BT", "MT"], horizontal=True)
            else:
                # Per Nuove Connessioni o Spostamenti si sceglie la tensione finale
                t_att = t_new = st.radio("Tensione Richiesta", ["BT", "MT"], horizontal=True)
        else:
            t_att = t_new = "BT"

        st.markdown("---")
        
        # --- LOGICA CAMPI POTENZA/DISTANZA RIGIDA ---
        if pratica in ["Aumento Potenza", "Subentro con Modifica"]:
            cp1, cp2 = st.columns(2)
            p_att = cp1.number_input("Potenza DI PARTENZA (kW)", value=3.0, step=0.5)
            p_new = cp2.number_input("Nuova Potenza RICHIESTA (kW)", value=6.0, step=0.5)
            # In questo blocco c_dist rimane 0.0
        
        elif pratica == "Nuova Connessione":
            p_new = st.number_input("Potenza Richiesta (kW)", value=3.0, step=0.5)
            c_dist = st.number_input("Quota Distanza Distributore (€)", value=0.0)
            
        elif pratica == "Spostamento":
            s_choice = st.radio("Distanza", ["Entro 10m", "Oltre 10m"], horizontal=True)
            if s_choice == "Oltre 10m":
                c_dist = st.number_input("Quota Distanza (€)", value=0.0)

        app_gest = st.checkbox("Gestione Polis (10%)", value=True)
    
    submit = st.form_submit_button("📁 GENERA, ARCHIVIA E SCARICA")

# --- CALCOLO E ANTEPRIMA ---
if submit:
    if nome and indirizzo:
        f_att = 1.1 if (t_att == "BT" and p_att <= 30) else 1.0
        f_new = 1.1 if (t_new == "BT" and p_new <= 30) else 1.0
        
        def get_tariffa(tens, pot, ut):
            if tens == "MT": return TIC_2026["MT"]
            if ut == "Domestico" and pot <= 6: return TIC_2026["DOM_LE6"]
            return TIC_2026["BT_ALTRI"]

        px_att = get_tariffa(t_att, p_att, tipo_ut)
        px_new = get_tariffa(t_new, p_new, tipo_ut)
        
        if pratica == "Spostamento":
            c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in s_choice else TIC_2026["SPOST_OLTRE_10"]
        else:
            # 1. Potenza attuale con franchigia 1.1 (se BT <= 30)
            p_att_virtuale = p_att * f_att 
    
            # 2. Potenza nuova ARROTONDATA PER ECCESSO all'intero (come da tua richiesta)
            p_new_arrotondata = math.ceil(p_new) 
    
            # 3. Differenza calcolata tra Intero e Virtuale Partenza
            diff_kw = max(0.0, p_new_arrotondata - p_att_virtuale)
    
            # 4. Calcolo economico
            c_tec = diff_kw * px_new
            
        c_gest = (c_tec + c_dist + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if app_gest else 0.0
        imp = c_tec + c_dist + c_gest + TIC_2026["ISTRUTTORIA"]
        iva_p = 10 if "10" in uso else (22 if ("22" in uso or "P.A." in uso) else 0)
        iva_e = imp * (iva_p/100)
        bollo = 2.0 if (uso == "Esente" and imp > 77.47) else 0.0
        tot = (imp if "P.A." in uso else imp + iva_e) + bollo

        dati = {
            'nome': nome, 'indirizzo': indirizzo, 'pod': pod if pod else "N.D.",
            'pratica': pratica, 't_att': t_att, 't_new': t_new, 'c_tec': c_tec, 'c_dist': c_dist, 
            'c_gest': c_gest, 'p_att': p_att, 'p_new': p_new, 'f_new': f_new,
            'imponibile': imp, 'iva_perc': iva_p, 'iva_euro': iva_e, 'bollo': bollo, 'totale': tot
        }
        cod_pratica = f"BA{int(tot)}{st.session_state.seq}"
        try:
            pdf_generato = genera_pdf(dati, cod_pratica)
            st.session_state.pdf_pronto = pdf_generato
            st.session_state.codice_per_mail = cod_pratica
            st.session_state.pratica_per_mail = pratica

            st.success(f"✅ Preventivo {cod_pratica} generato!")
        except Exception as e:
            st.error(f"Errore generazione PDF: {e}")
            
        
        st.session_state.ultimo_codice = cod_pratica
        st.session_state.seq = (st.session_state.seq + 1) % 10 # Ciclo 0-9
        st.session_state.pdf_pronto = pdf_file
        st.subheader("🔍 Anteprima Riepilogo")
        preview = {
            "Voce": ["Potenza", "Distanza", "Istruttoria", "Gestione Polis", "Imponibile", "IVA", "Bollo", "TOTALE"],
            "Importo (€)": [f"{c_tec:.2f}", f"{c_dist:.2f}", f"{TIC_2026['ISTRUTTORIA']:.2f}", f"{c_gest:.2f}", f"{imp:.2f}", f"{iva_e:.2f}", f"{bollo:.2f}", f"**{tot:.2f}**"]
        }
        st.table(pd.DataFrame(preview))
        st.divider()
        st.subheader("✉️ Preparazione Invio Email")
        
        col_mail1, col_mail2 = st.columns([1, 2])
        with col_mail1:
            dest_mail = st.text_input("Email del cliente", placeholder="cliente@esempio.it")
        
        with col_mail2:
            # Testo predefinito che l'utente può confermare o modificare
            testo_default = f"Gentile Cliente,\n\nin allegato il preventivo {cod_pratica} relativo alla pratica di {pratica}.\n\nRestiamo a disposizione per ogni chiarimento.\n\nCordiali saluti,\nPolisEnergia srl"
            corpo_mail = st.text_area("Modifica il testo della mail se necessario", value=testo_default, height=150)

        # IL TASTO DI CONFERMA FINALE
    if 'pdf_pronto' in st.session_state:
        st.divider()
        st.subheader("✉️ Invia il preventivo via Email")
    
    # Recuperiamo i dati salvati
        pdf_da_inviare = st.session_state.pdf_pronto
        cod = st.session_state.codice_per_mail
        tipo = st.session_state.pratica_per_mail
    
        col1, col2 = st.columns([1, 2])
    with col1:
        dest_mail = st.text_input("Email Destinatario", key="mail_input")
    with col2:
        testo_mail = st.text_area("Messaggio", value=f"Gentile Cliente, in allegato il preventivo {cod}...")
        
    if st.button("🚀 INVIA ORA"):
        if dest_mail:
            with st.spinner("Connessione ai server Aruba in corso..."):
                esito = invia_preventivo_email(dest_mail, f"Preventivo {cod}", testo_mail, pdf_da_inviare, f"{cod}.pdf")
                if esito:
                    st.balloons()
                    st.success("Email inviata correttamente!")
        else:
            st.warning("Inserisci una mail valida.")
    # Generazione PDF
        try:
            pdf_file = genera_pdf(dati, cod_pratica)
            st.success(f"✅ Preventivo {cod_pratica} creato!")
            st.download_button("📥 SCARICA PDF", data=bytes(pdf_file), file_name=f"{cod_pratica}.pdf", use_container_width=True)
            
            # Salvataggio Cloud
            # 1. Leggi i dati esistenti
            df_esistente = conn.read(ttl=0) # ttl=0 forza l'aggiornamento senza cache
            
            # 2. Crea la nuova riga assicurandoti che i nomi delle colonne siano IDENTICI a quelli sul foglio
            nuova_riga = pd.DataFrame([{
                "Data": datetime.now().strftime("%d/%m/%Y"),
                "Codice": str(cod_pratica),
                "Cliente": str(nome),
                "Totale": float(tot)
            }])
            
            # 3. Unisci e pulisci da eventuali valori nulli
            df_finale = pd.concat([df_esistente, nuova_riga], ignore_index=True).fillna("")
            
            # 4. Sovrascrivi il foglio
            conn.update(data=df_finale)
            st.success(f"✅ Archiviato correttamente su Google Sheets!")
        except Exception as e:
            st.error(f"Errore di scrittura nel Cloud: {e}")
            st.info("Assicurati che la prima riga del foglio abbia: Data, Codice, Cliente, Totale")
# --- SEZIONE INVIO MAIL (Compare solo se il PDF è pronto) ---
if st.session_state.pdf_pronto:
    st.divider()
    st.subheader("✉️ Invia Preventivo via Email")
    
    col_m1, col_m2 = st.columns([1, 2])
    with col_m1:
        mail_cliente = st.text_input("Email destinatario")
    with col_m2:
        testo_mail = st.text_area("Testo della mail", value=f"Spett.le Cliente, in allegato il preventivo {st.session_state.ultimo_cod}...")

    if st.button("🚀 INVIA ORA"):
        if mail_cliente:
            with st.spinner("Invio in corso..."):
                ok = invia_mail_aruba(mail_cliente, f"Preventivo Polis - {st.session_state.ultimo_cod}", testo_mail, st.session_state.pdf_pronto, f"{st.session_state.ultimo_cod}.pdf")
                if ok:
                    st.success("📩 Mail inviata correttamente!")
                    st.balloons()
        else:
            st.error("Inserisci l'indirizzo email!")
            
