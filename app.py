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

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="PolisEnergia 4.0", layout="wide")

if 'seq' not in st.session_state: st.session_state.seq = 0
if 'pdf_pronto' not in st.session_state: st.session_state.pdf_pronto = None
if 'ultimo_codice' not in st.session_state: st.session_state.ultimo_codice = "---"

TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "SPOST_ENTRO_10": 226.36, "SPOST_OLTRE_10": 226.36, 
    "ISTRUTTORIA": 27.42, "FISSO_BASE_CALCOLO": 25.88
}

# --- FUNZIONI CORE ---
def invia_mail_aruba(destinatario, oggetto, corpo, pdf_bytes, nome_file):
    try:
        s = st.secrets["connections"]["gsheets"]
        msg = MIMEMultipart()
        msg['From'] = s["EMAIL_SENDER"]
        msg['To'] = destinatario
        msg['Subject'] = oggetto
        msg.attach(MIMEText(corpo, 'plain'))
        part = MIMEApplication(pdf_bytes, Name=nome_file)
        part['Content-Disposition'] = f'attachment; filename="{nome_file}"'
        msg.attach(part)
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(s["EMAIL_SERVER"], int(s["EMAIL_PORT"]), context=context) as server:
            server.login(s["EMAIL_SENDER"], s["EMAIL_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Errore Mail: {e}"); return False

def genera_pdf(d, cod):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(0, 29, 61); pdf.rect(0, 0, 210, 45, 'F')
    if os.path.exists("logo_polis.png"): pdf.image("logo_polis.png", 10, 10, 33)
    pdf.set_xy(120, 12); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 5, "PolisEnergia srl - Via Terre delle Risaie, 4 - 84131 Salerno (SA)", align='R', ln=1)
    pdf.set_xy(10, 55); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"SPETT.LE: {d['nome']}", ln=1)
    pdf.cell(0, 6, f"INDIRIZZO: {d['indirizzo']}", ln=1)
    pdf.ln(5); pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"PREVENTIVO {d['pratica'].upper()} - POD: {d['pod']}", border="B", ln=1)
    pdf.ln(5); pdf.set_fill_color(0, 180, 216); pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, " DESCRIZIONE", 1, 0, 'L', True); pdf.cell(50, 10, " IMPORTO", 1, 1, 'C', True)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 8, f" Quota Potenza/Tecnica ({d['t_att']} -> {d['t_new']})", 1); pdf.cell(50, 8, f"{d['c_tec']:.2f} EUR", 1, 1, 'R')
    if d['c_dist'] > 0: pdf.cell(140, 8, " Quota Distanza / Oneri Rilievo", 1); pdf.cell(50, 8, f"{d['c_dist']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Amministrativi", 1); pdf.cell(50, 8, f"{TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Gestione Pratica", 1); pdf.cell(50, 8, f"{d['c_gest']:.2f} EUR", 1, 1, 'R')
    pdf.ln(2); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 9, " IMPONIBILE", 1); pdf.cell(50, 9, f"{d['imponibile']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, f" IVA ({d['iva_perc']}%)", 1); pdf.cell(50, 9, f"{d['iva_euro']:.2f} EUR", 1, 1, 'R')
    if d['bollo'] > 0: pdf.cell(140, 9, " BOLLO", 1); pdf.cell(50, 9, "2.00 EUR", 1, 1, 'R')
    pdf.set_fill_color(240, 240, 240); pdf.cell(140, 11, " TOTALE", 1, 0, 'L', True); pdf.cell(50, 11, f"{d['totale']:.2f} EUR", 1, 1, 'R', True)
    
    # RITORNO CORRETTO PER STREAMLIT (BYTES)
    return bytes(pdf.output())

# --- INTERFACCIA ---
st.title("⚡ PolisEnergia")
st.caption(f"Preventivatore 4.0 | Codice: {st.session_state.ultimo_codice}")

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
        
        p_att, p_new, c_dist = 0.0, 0.0, 0.0
        t_att, t_new = "BT", "BT"

        if tipo_ut == "Altri Usi":
            if pratica in ["Aumento Potenza", "Subentro con Modifica"]:
                flag_mt = st.checkbox("🔄 Passaggio da BT a MT?")
                if flag_mt:
                    t_att, t_new = "BT", "MT"
                else:
                    t_att = t_new = st.radio("Tensione", ["BT", "MT"], horizontal=True, key="t_radio")
            else:
                t_att = t_new = st.radio("Tensione Richiesta", ["BT", "MT"], horizontal=True, key="tr_radio")
        else:
            t_att = t_new = "BT"

        st.markdown("---")
        if "Nuova" in pratica:
            p_new = st.number_input("Potenza Richiesta (kW)", value=3.0, step=0.5)
            c_dist = st.number_input("Quota Distanza Distributore (€)", value=187.0)
        elif "Spostamento" in pratica:
            s_choice = st.radio("Distanza", ["Entro 10m", "Oltre 10m"], horizontal=True)
            if "Oltre" in s_choice:
                c_dist = st.number_input("Quota Distanza (€)", value=0.0)
        else: # Aumento o Subentro
            cp1, cp2 = st.columns(2)
            p_att = cp1.number_input("Potenza Partenza (kW)", value=3.0, step=0.5)
            p_new = cp2.number_input("Potenza Richiesta (kW)", value=6.0, step=0.5)

        app_gest = st.checkbox("Gestione Polis (10%)", value=True)
    
    submit = st.form_submit_button("📁 GENERA PREVENTIVO")

# --- CALCOLO ---
if submit:
    if nome and indirizzo:
        def get_tariffa(tens, pot, ut):
            if tens == "MT": return TIC_2026["MT"]
            if ut == "Domestico" and pot <= 6: return TIC_2026["DOM_LE6"]
            return TIC_2026["BT_ALTRI"]

        px_att = get_tariffa(t_att, p_att, tipo_ut)
        px_new = get_tariffa(t_new, p_new, tipo_ut)
        
        # LOGICA TECNICA RIPRISTINATA
        if "Spostamento" in pratica:
            c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in s_choice else TIC_2026["SPOST_OLTRE_10"]
        elif "Nuova" in pratica:
            c_tec = math.ceil(p_new) * px_new
        else: # Aumento / Subentro
            f_att = 1.1 if (t_att == "BT" and p_att <= 30) else 1.0
            c_tec = max(0.0, (math.ceil(p_new) * px_new) - (p_att * f_att * px_att))
            
        c_gest = (c_tec + c_dist + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if app_gest else 0.0
        imp = c_tec + c_dist + c_gest + TIC_2026["ISTRUTTORIA"]
        iva_p = 10 if "10" in uso else (22 if ("22" in uso or "P.A." in uso) else 0)
        iva_e = imp * (iva_p/100)
        bollo = 2.0 if (uso == "Esente" and imp > 77.47) else 0.0
        tot = (imp if "P.A." in uso else imp + iva_e) + bollo

        dati = {
            'nome': nome, 'indirizzo': indirizzo, 'pod': pod if pod else "N.D.",
            'pratica': pratica, 't_att': t_att, 't_new': t_new, 'c_tec': c_tec, 'c_dist': c_dist, 
            'c_gest': c_gest, 'imponibile': imp, 'iva_perc': iva_p, 'iva_euro': iva_e, 'bollo': bollo, 'totale': tot
        }
        
        cod_pratica = f"BA{int(tot)}{st.session_state.seq}"
        st.session_state.pdf_pronto = genera_pdf(dati, cod_pratica)
        st.session_state.ultimo_codice = cod_pratica
        st.session_state.seq = (st.session_state.seq + 1) % 10
        st.rerun()

# --- SEZIONE INVIO E DOWNLOAD ---
if st.session_state.pdf_pronto:
    st.divider()
    col_dl, col_mail = st.columns([1, 2])
    with col_dl:
        st.download_button("📥 SCARICA PDF", data=st.session_state.pdf_pronto, file_name=f"{st.session_state.ultimo_codice}.pdf", mime="application/pdf")
    with col_mail:
        mail_c = st.text_input("Email Cliente")
        txt = st.text_area("Messaggio", value=f"In allegato il preventivo {st.session_state.ultimo_codice}")
        if st.button("🚀 INVIA"):
            if invia_mail_aruba(mail_c, f"Preventivo {st.session_state.ultimo_codice}", txt, st.session_state.pdf_pronto, f"{st.session_state.ultimo_codice}.pdf"):
                st.success("Inviato!"); st.balloons()
