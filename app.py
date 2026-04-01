import streamlit as st
import math
import pandas as pd
import random
import io
import xml.etree.ElementTree as ET
import re
import os
import smtplib
import ssl
from sqlalchemy import text
from collections import defaultdict
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


# --- 1. CONFIGURAZIONE PAGINA (UNICA CHIAMATA) ---
st.set_page_config(page_title="Operation Suite", layout="wide")

IBAN_POLIS = "IT80P0103015200000007044056" 
NOME_BANCA = "Monte dei Paschi di Siena"
INTESTATARIO = "POLISENERGIA SRL"

st.markdown("""
    <style>
    /* Sfondo blu solo per l'area principale */
    .stApp { background-color: #004a99; }
    
    /* Testo bianco solo nell'area principale */
    .stMain h1, .stMain h2, .stMain h3, .stMain p, .stMain label { color: white !important; }
    
    /* Sidebar (Menu a sinistra) - Testo scuro su sfondo chiaro */
    [data-testid="stSidebar"] { background-color: #f0f2f6; }
    [data-testid="stSidebar"] * { color: #004a99 !important; }

    /* Input bianchi con testo nero */
    .stTextInput input { background-color: white !important; color: black !important; }
    
    /* Bottone Genera Verde */
    div.stButton > button:first-child {
        background-color: #28a745 !important; color: white !important;
        border-radius: 8px !important; font-weight: bold !important; width: 100% !important;
    }

    /* --- GESTIONE FRECCETTA SIDEBAR --- */
    /* Rendiamo visibile l'header (che contiene la freccetta) ma nascondiamo il resto dei menu superflui */
    header { visibility: visible !important; background: transparent !important; }
    footer { visibility: hidden; }

    /* Forza la freccetta di apertura a essere BIANCA e visibile sul blu */
    [data-testid="stSidebarCollapsedControl"] {
        color: white !important;
        background-color: rgba(255, 255, 255, 0.2) !important;
        border-radius: 50% !important;
        left: 10px !important;
        top: 10px !important;
    }
    
    /* Colore dell'icona SVG interna alla freccetta */
    [data-testid="stSidebarCollapsedControl"] svg {
        fill: white !important;
    }
    </style>
""", unsafe_allow_html=True)

def formatta_data_italiana(data_raw):
    """Forza il formato GG/MM/AAAA richiesto dai portali"""
    d = str(data_raw).strip().split(' ')[0]
    try:
        parti = re.split(r'[/.-]', d)
        if len(parti) == 3:
            if len(parti[0]) == 4: # ISO
                anno, mese, giorno = parti[0], parti[1].zfill(2), parti[2].zfill(2)
            else: # ITA
                giorno, mese, anno = parti[0].zfill(2), parti[1].zfill(2), parti[2]
            if len(anno) == 2: anno = "20" + anno
            return f"{giorno}/{mese}/{anno}"
        return d
    except:
        return d

def pulisci_valore(valore):
    """Pulisce i numeri di lettura per il formato XML (9 cifre)"""
    val = str(valore).strip().lower()
    if val in ["", "nan", "none", "0", "0,00", "0.00"]:
        return None
    parte_intera = val.split(',')[0]
    if '.' in parte_intera and len(parte_intera.split('.')[-1]) <= 2:
        parte_intera = parte_intera.rsplit('.', 1)[0]
    solo_n = "".join(filter(str.isdigit, parte_intera.replace('.', '')))
    return solo_n.zfill(9) if solo_n and int(solo_n) > 0 else None
def genera_pdf_polis(d):
    pdf = FPDF()
    pdf.add_page()
    
    # --- COLORI BRAND ---
    BLUE_P = (0, 51, 102)
    GRAY_LIGHT = (245, 245, 245)
    GRAY_TEXT = (60, 60, 60)

    # --- HEADER BLU ---
    pdf.set_fill_color(*BLUE_P)
    pdf.rect(0, 0, 210, 45, 'F')
    
    # Logo o Nome Azienda
    try:
        pdf.image("logo_polis.png", 10, 12, 35)
    except:
        pdf.set_xy(10, 15)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("helvetica", "B", 20)
        pdf.cell(0, 10, "PolisEnergia srl")

    # Dati Aziendali
    pdf.set_xy(120, 12)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "", 8)
    pdf.multi_cell(80, 4, "Via Terre delle Risaie, 4 - 84131 Salerno (SA)\nP.IVA 05050950657\nassistenza@polisenergia.it\nwww.polisenergia.it", align='R')

    # --- TITOLO E DATA ---
    pdf.set_xy(10, 55)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, f"PREVENTIVO N. {d['Codice']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Emesso il: {datetime.now().strftime('%d/%m/%Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- DATI CLIENTE (Box elegante) ---
    pdf.ln(8)
    pdf.set_fill_color(*GRAY_LIGHT)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 10, f"  SPETT.LE CLIENTE: {d['Cliente']}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.cell(0, 7, f"  POD: {d['POD']} | Indirizzo: {d['Indirizzo']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- TABELLA PRESTAZIONI ---
    pdf.ln(10)
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.2)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(*BLUE_P)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, "  DESCRIZIONE PRESTAZIONE", border='B', fill=True)
    pdf.cell(50, 10, "IMPORTO  ", border='B', fill=True, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_text_color(*GRAY_TEXT)
    voci = [
        ("Quota Tecnica", d['C_Tec']),
        ("Oneri Amministrativi", d['Oneri']),
        ("Oneri Gestione Pratica", d['Gestione'])
    ]
    
    fill = False
    for voce, importo in voci:
        pdf.set_fill_color(250, 250, 250) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_font("helvetica", "", 10)
        pdf.cell(140, 9, f"  {voce}", border='B', fill=True)
        pdf.cell(50, 9, f"{importo:.2f} EUR  ", border='B', fill=True, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        fill = not fill

    # --- TOTALI ---
    pdf.ln(3)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(140, 8, "Totale Imponibile", align='R')
    pdf.cell(50, 8, f"{d['Imponibile']:.2f} EUR  ", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.cell(140, 8, f"IVA ({d['IVA_Perc']}%)", align='R')
    pdf.cell(50, 8, f"{d['IVA_Euro']:.2f} EUR  ", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(*BLUE_P)
    pdf.set_fill_color(230, 240, 250)
    pdf.cell(140, 12, "  TOTALE DA CORRISPONDERE", fill=True)
    pdf.cell(50, 12, f"{d['Totale']:.2f} EUR  ", fill=True, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- PAGAMENTO ---
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, "MODALITA' DI PAGAMENTO:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(0, 5, f"Bonifico Bancario IBAN: {d['IBAN']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 5, f"CAUSALE OBBLIGATORIA: Accettazione Preventivo {d['Codice']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Note
    pdf.set_y(-65)
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(120, 120, 120)
    note = [
        "L'esecuzione della prestazione è subordinata al verificarsi delle seguenti condizioni:",
        "- conferma della proposta pervenuta entro 30 gg dalla presente richiesta;",
        "- comunicazione dell'avvenuto completamento di eventuali opere/autorizzazioni a cura del cliente finale.",
        "Il presente documento deve essere inviato firmato a: assistenza@polisenergia.it"
    ]
    for riga in note:
        pdf.cell(0, 3.5, riga, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Firma
    pdf.set_y(-35)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, "Firma per Accettazione Cliente", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.line(140, pdf.get_y() + 15, 200, pdf.get_y() + 15)

    return bytes(pdf.output())

query_params = st.query_params

# Recuperiamo i parametri dall'URL (se esistono)
otp_param = query_params.get("otp", "")
codice_param = query_params.get("codice", "")

# --- BLOCCO A: INTERCETTAZIONE CLIENTE (Solo se i parametri sono presenti) ---
if otp_param and codice_param:
    st.title("🖋️ Accettazione Online")
    
    # Pulizia codici dai parametri
    cod_u = str(codice_param).strip().replace('.0', '')
    otp_u = str(otp_param).strip()
    
    try:
        # Connessione al Database per recuperare i dati del preventivo
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl=0)
        df_c = df["Codice"].astype(str).str.strip().str.replace('.0', '')

        if cod_u in df_c.values:
            idx = df_c[df_c == cod_u].index[0]
            nome_cliente = df.at[idx, "Cliente"]
            importo_totale = float(df.at[idx, "Totale"])

            # --- BOX INFORMAZIONI PAGAMENTO (BIANCO SU BLU) ---
            st.markdown(f"""
                <div style="background-color: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 10px; border: 1px solid white; margin-bottom: 25px;">
                    <h3 style="color: white; margin-top: 0;">💳 Istruzioni per il pagamento</h3>
                    <p style="color: white; font-size: 1.1em;"><strong>Cliente:</strong> {nome_cliente}</p>
                    <p style="color: white; font-size: 1.1em;"><strong>Importo da corrispondere:</strong> {importo_totale:.2f} EUR</p>
                    <hr style="border-color: rgba(255,255,255,0.3);">
                    <p style="color: white; font-weight: bold; margin-bottom: 5px;">COORDINATE BANCARIE:</p>
                    <ul style="color: white; list-style-type: none; padding-left: 0;">
                        <li><strong>Intestatario:</strong> POLISENERGIA SRL</li>
                        <li><strong>Banca:</strong> Monte dei Paschi di Siena</li>
                        <li><strong>IBAN:</strong> <span style="font-family: monospace; background: rgba(0,0,0,0.2); padding: 2px 5px;">{IBAN_POLIS}</span></li>
                        <li><strong>Causale:</strong> Accettazione Preventivo {cod_u} - {nome_cliente}</li>
                    </ul>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("<p style='color: white; font-weight: bold; margin-bottom: 0;'>Inserisci l'OTP ricevuto via mail per confermare:</p>", unsafe_allow_html=True)
            otp_in = st.text_input("OTP_INPUT", label_visibility="collapsed", max_chars=6)
            
            if st.button("✅ FIRMA E ACCETTA ORA"):
                if otp_in.strip() == otp_u:
                    # 1. Aggiornamento Database
                    df.at[idx, "Stato"] = "ACCETTATO"
                    df.at[idx, "Data Firma"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    conn.update(data=df)
                    
                    # 2. Invio Notifica Email
                    try:
                        msg = MIMEMultipart()
                        msg['From'] = SENDER_EMAIL
                        msg['To'] = SENDER_EMAIL
                        msg['Cc'] = MAIL_CC
                        msg['Subject'] = f"✅ PREVENTIVO FIRMATO: {nome_cliente}"
                        corpo_mail = f"Il cliente {nome_cliente} ha accettato il preventivo {cod_u}.\nControlla il database."
                        msg.attach(MIMEText(corpo_mail, 'plain'))
                        
                        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ssl.create_default_context()) as s:
                            s.login(SENDER_EMAIL, SENDER_PASSWORD)
                            s.send_message(msg)
                    except:
                        pass # Silenzioso se la mail fallisce ma il database è ok
                        
                    st.success("Documento firmato con successo!")
                    st.balloons()
                else:
                    st.error("L'OTP inserito non è corretto.")
            
            # --- BLOCCO FONDAMENTALE ---
            st.stop() # Impedisce al cliente di vedere il menu operativo
            
        else:
            st.error("Errore: Preventivo non trovato o link scaduto.")
            st.stop()

    except Exception as e:
        st.error(f"Errore tecnico nel caricamento: {e}")
        st.stop()

if "autenticato" not in st.session_state:
    st.session_state.autenticato = False

# La sidebar si espande da sola solo se non sei ancora loggato
stato_sidebar = "expanded" if not st.session_state.autenticato else "auto"

st.set_page_config(
    page_title="PolisEnergia Suite", 
    layout="wide", 
    initial_sidebar_state=stato_sidebar
)

# --- 2. CSS PERSONALIZZATO (Sfondo, Testi e Freccetta Bianca) ---
st.markdown("""
    <style>
    .stApp { background-color: #004a99; }
    .stMain h1, .stMain h2, .stMain h3, .stMain p, .stMain label { color: white !important; }
    [data-testid="stSidebar"] { background-color: #f0f2f6; }
    [data-testid="stSidebar"] * { color: #004a99 !important; }
    .stTextInput input { background-color: white !important; color: black !important; }
    div.stButton > button:first-child {
        background-color: #28a745 !important; color: white !important;
        border-radius: 8px !important; font-weight: bold !important; width: 100% !important;
    }
    header { visibility: visible !important; background: transparent !important; }
    footer { visibility: hidden; }
    [data-testid="stSidebarCollapsedControl"] {
        color: white !important;
        background-color: rgba(255, 255, 255, 0.2) !important;
        border-radius: 50% !important;
        left: 10px !important;
        top: 10px !important;
    }
    [data-testid="stSidebarCollapsedControl"] svg { fill: white !important; }
    </style>
""", unsafe_allow_html=True)
if not st.session_state.autenticato:
    st.sidebar.title("🔒 Area Riservata")
    password_segreta = "Polis2026"
    password_inserita = st.sidebar.text_input("Inserisci Password", type="password")

    if password_inserita:
        if password_inserita == password_segreta:
            st.session_state.autenticato = True
            st.rerun() 
        else:
            st.sidebar.error("Password errata")

    # Schermata che vede chi apre l'app senza link e senza password
    st.title("Polisenergia - Operation Suite")
    st.info("Effettua il login nella barra laterale per accedere.")
    st.stop() 

# --- 5. ACCESSO AUTORIZZATO (SUITE COMPLETA) ---
st.sidebar.success("✅ Accesso Autorizzato")
st.sidebar.title("Navigazione")
scelta = st.sidebar.radio("Cosa vuoi fare?", 
                         ["Autoletture (TAL 0050)", "Preventivo di Connessione"])


if scelta == "Autoletture (TAL 0050)":
    st.header("📊 Generatore Flussi Autoletture (TAL 0050)")
    file_arera_path = "arera.csv"
    if not os.path.exists(file_arera_path):
        st.error("❌ File 'arera.csv' non trovato su GitHub. Caricalo nel repository per continuare.")
        st.stop()
    
    # 2. Input Dati
    piva_mittente = st.text_input("P.IVA Venditore (Mittente)", value="05050950657", help="Inserisci la tua Partita IVA")

    st.divider()
    st.subheader("📁 Caricamento File Privati")
    st.caption("I dati caricati qui non vengono salvati sul server e spariscono alla chiusura della pagina.")

    col1, col2 = st.columns(2)
    with col1:
        file_tech = st.file_uploader("1. Carica Anagrafica Tecnica (Excel)", type=["xlsx", "xls"])
    with col2:
        file_letture = st.file_uploader("2. Carica File Autoletture (CSV)", type="csv")

    if file_tech and file_letture:
        if st.button("🚀 GENERA FILE XML", use_container_width=True):
            try:
                # Lettura ARERA
                df_arera = pd.read_csv(file_arera_path, encoding='latin-1', sep=';', on_bad_lines='skip', dtype=str)
                df_arera.columns = [c.strip().upper() for c in df_arera.columns]
                
                mappa_distr = {}
                for _, r in df_arera.iterrows():
                    pref = str(r['CODICE PDR']).strip().split('.')[0].zfill(4)
                    piva_d = "".join(filter(str.isdigit, str(r['PARTITA IVA'])))[:11].zfill(11)
                    mappa_distr[pref] = {'piva': piva_d, 'nome': str(r['RAGIONE SOCIALE']).strip()}

                # Lettura Anagrafica Tecnica
                df_tech = pd.read_excel(file_tech, dtype=str)
                df_tech.columns = [c.strip().upper() for c in df_tech.columns]
                mappa_matr_pdr = pd.Series(df_tech['MATR_MIS'].values, index=df_tech.COD_PDR.str.strip()).to_dict()
                c_matr_corr = next((c for c in df_tech.columns if 'CORR' in c), None)
                mappa_matr_corr = pd.Series(df_tech[c_matr_corr].values, index=df_tech.COD_PDR.str.strip()).to_dict() if c_matr_corr else {}

                # Lettura Autoletture
                df_let = pd.read_csv(file_letture, sep=None, engine='python', encoding='utf-8-sig', dtype=str)
                df_let.columns = [c.strip().upper() for c in df_let.columns]
                
                col_pdr = next(c for c in df_let.columns if 'PDR' in c)
                col_data = next(c for c in df_let.columns if 'DATA' in c)
                col_lett = next(c for c in df_let.columns if 'LETTURA' in c and 'CORRE' not in c)
                col_corr = next((c for c in df_let.columns if 'CORRETTORE' in c or 'CONVERT' in c), None)

                # Raggruppamento
                gruppi = defaultdict(list)
                for _, riga in df_let.iterrows():
                    pdr = str(riga[col_pdr]).strip().split('.')[0].zfill(14)
                    pref = pdr[:4]
                    if pref in mappa_distr:
                        info = mappa_distr[pref]
                        ln = pulisci_valore(riga[col_lett])
                        lc = pulisci_valore(riga[col_corr]) if col_corr else None
                        if ln:
                            gruppi[info['piva']].append({
                                'distr_nome': info['nome'], 'pdr': pdr, 
                                'data': formatta_data_italiana(riga[col_data]),
                                'lett': ln, 'corr': lc,
                                'm_pdr': str(mappa_matr_pdr.get(pdr, "0")).split('.')[0],
                                'm_corr': str(mappa_matr_corr.get(pdr, "")).split('.')[0] if pdr in mappa_matr_corr else None
                            })

                # Risultati e Download
                st.success(f"Elaborazione completata! Trovati {len(gruppi)} distributori.")
                st.divider()

                for piva_d, lista in gruppi.items():
                    # Creazione XML
                    root = ET.Element("Prestazione", cod_servizio="TAL", cod_flusso="0050")
                    id_req = ET.SubElement(root, "IdentificativiRichiesta")
                    ET.SubElement(id_req, "piva_utente").text = piva_mittente
                    ET.SubElement(id_req, "piva_distr").text = piva_d
                    
                    for item in lista:
                        d = ET.SubElement(root, "DatiPdR")
                        ET.SubElement(d, "cod_pdr").text = item['pdr']
                        ET.SubElement(d, "matr_mis").text = item['m_pdr']
                        ET.SubElement(d, "data_com_autolet_cf").text = item['data']
                        ET.SubElement(d, "let_tot_prel").text = item['lett']
                        if item['corr']:
                            ET.SubElement(d, "let_tot_conv").text = item['corr']
                            if item['m_corr'] and item['m_corr'] not in ["nan", "None", ""]:
                                ET.SubElement(d, "matr_conv").text = item['m_corr']

                    # Preparazione file per scaricamento
                    xml_str = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                    clean_name = re.sub(r'\W+', '', lista[0]['distr_nome'])[:15]
                    
                    st.download_button(
                        label=f"⬇️ Scarica XML: {lista[0]['distr_nome']} ({piva_d})",
                        data=xml_str,
                        file_name=f"TAL_0050_{piva_d}_{clean_name}.xml",
                        mime="application/xml",
                        key=piva_d # Chiave univoca per streamlit
                    )

            except Exception as e:
                st.error(f"Errore durante l'elaborazione: {e}")

elif scelta == "Preventivo di Connessione":
    
    # --- COSTANTI ---
    TIC_DOMESTICO_LE6 = 62.30  
    TIC_ALTRI_USI_BT = 78.81
    TIC_MT = 62.74
    ONERI_ISTRUTTORIA = 27.42
    SPOSTAMENTO_10MT = 226.36
    FISSO_BASE_CALCOLO = 25.88
    COSTO_PASSAGGIO_MT = 494.83
    IBAN_POLIS = "IT80P0103015200000007044056 - Monte dei Paschi di Siena"
    
    # --- INIZIALIZZAZIONE VARIABILI (Evita l'errore NameError riga 595) ---
    delta, tar, c_tec, c_gest, imp, totale = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    p_att, p_new, c_dist = 0.0, 0.0, 0.0
    passaggio_mt = False
    t_partenza = "BT"

    # --- STILE CSS ---
    st.markdown("""
        <style>
        .stApp { background-color: #004a99; }
        h1, h2, h3, p, span, label, .stMarkdown { color: white !important; }
        .stTextInput>div>div>input { background-color: white !important; color: black !important; }
        div.stButton > button:first-child { background-color: #28a745 !important; color: white !important; border-radius: 8px; font-weight: bold; width: 100%; }
        </style>
    """, unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        try: st.image("logo_polis.png", width=250)
        except: st.markdown("<h1 style='text-align: center;'>POLIS</h1>", unsafe_allow_html=True)

    st.title("⚡ PolisEnergia - Preventivatore")

    if st.button("🧹 PULISCI TUTTO", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
  # --- 1. DATI CLIENTE ---
    with st.container():
        c1, c2 = st.columns(2)
        nome = c1.text_input("Ragione Sociale", key="n").upper()
        email_dest = c1.text_input("Email Cliente", key="m")
        pod = c2.text_input("POD", key="p").upper()
        indirizzo = c1.text_input("Indirizzo Impianto", key="ind")
        regime = c2.selectbox("Regime IVA", ["10%", "22%", "Esente", "P.A."], key="r")

    st.divider()
    # --- 2. CONFIGURAZIONE PRATICA ---
    c3, c4 = st.columns([2, 1])
    pratica = c3.selectbox("Tipo Pratica", ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento Contatore"], key="prat")
    tipo_ut = c4.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True, key="ut")

    if "Potenza" in pratica or "Subentro" in pratica:
        col1, col2 = st.columns(2)
        if tipo_ut == "Altri Usi":
            t_partenza = col1.selectbox("Tensione", ["BT", "MT"], key="t")
            if t_partenza == "BT": passaggio_mt = col1.checkbox("Passaggio a MT?", key="mt")
        p_att = col1.number_input("kW Attuali", value=0.0, key="pa")
        p_new = col2.number_input("kW Richiesti", value=0.0, key="pn")
    elif "Nuova" in pratica:
        p_new = st.number_input("kW Richiesti", value=0.0, key="pnc")
        c_dist = st.number_input("Quota Distanza €", 0.0, key="dist")
    elif "Spostamento" in pratica:
        s_dist = st.radio("Distanza", ["Entro 10 metri", "Oltre 10 metri"], key="sd")
        c_dist = SPOSTAMENTO_10MT if "Entro" in s_dist else st.number_input("Costo Rilievo €", 0.0, key="sdc")

    # --- 3. LOGICA DI CALCOLO ---
    
    limitatore = False
    if tipo_ut == "Altri Usi" and 15 < p_new <= 30:
        limitatore = st.checkbox("Abilita Limitatore (Franchigia +10%)", value=True, key="lim_flag")

    if p_new > 0:
        if p_new <= 30 and (tipo_ut == "Domestico" or (tipo_ut == "Altri Usi" and limitatore)):
            v_new = round(p_new * 1.1, 1)
            v_att = round(p_att * 1.1, 1) if p_att > 0 else 0.0
        else:
            v_new, v_att = p_new, p_att
        delta = round(v_new - v_att, 1)

        # Selezione Tariffa
        if "Nuova" in pratica: tar = TIC_ALTRI_USI_BT
        elif tipo_ut == "Domestico" and p_new <= 6: tar = TIC_DOMESTICO_LE6
        elif t_partenza == "MT" or passaggio_mt: tar = TIC_MT
        else: tar = TIC_ALTRI_USI_BT

    # Calcolo Imponibile
    c_tec = c_dist if "Spostamento" in pratica else round(delta * tar, 2)
    if passaggio_mt: c_tec += COSTO_PASSAGGIO_MT
    
    c_gest = round((c_tec + FISSO_BASE_CALCOLO) * 0.1, 2)
    imp = round(c_tec + c_gest + ONERI_ISTRUTTORIA, 2)
    iva_p = 10 if "10" in regime else (22 if "22" in regime or "P.A." in regime else 0)
    iva_e = round(imp * (iva_p/100), 2)
    bollo = 2.0 if (regime == "Esente" and imp > 77.47) else 0.0
    totale = round(imp + bollo, 2) if "P.A." in regime else round(imp + iva_e + bollo, 2)
  
    # --- 4. ANTEPRIMA ---
    
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
   
    # --- 5. AZIONI ---
    
    if st.button("📄 1. GENERA PDF E ARCHIVIA", type="primary", use_container_width=True):
        cod = datetime.now().strftime("%y%m%d%H%M%S")
        st.session_state.current_cod = cod
        # Passaggio dati alla funzione
        st.session_state.pdf_bytes = genera_pdf_polis({
            "Codice": cod, "Cliente": nome, "POD": pod, "Indirizzo": indirizzo, 
            "C_Tec": c_tec, "Oneri": ONERI_ISTRUTTORIA, "Gestione": c_gest, 
            "Imponibile": imp, "IVA_Perc": iva_p, "IVA_Euro": iva_e, "Totale": totale, "IBAN": IBAN_POLIS
        })
        st.success(f"Archiviato con codice {cod}")

    if 'pdf_bytes' in st.session_state:
        pdf_buffer = io.BytesIO(st.session_state.pdf_bytes)
        st.download_button(label="📥 SCARICA PDF",
            data=pdf_buffer,
            file_name=f"{st.session_state.current_cod}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
# --- 6. INVIO EMAIL ---
        st.divider()
        st.subheader("📧 Invio Documentazione")
        
        # Generazione parametri per la firma (Link e OTP)
        otp = str(random.randint(100000, 999999))
        # Assicurati che l'URL sia quello della tua app pubblicata
        link_firma = f"https://operation-polisenergia.streamlit.app/?codice={st.session_state.current_cod}&otp={otp}"
        
        testo_predefinito = (
            f"Spett.le {nome},\n\n"
            f"in allegato trasmettiamo il preventivo n. {st.session_state.current_cod} relativo all'impianto sito in {indirizzo}.\n\n"
            f"Puoi procedere alla firma elettronica cliccando sul seguente link:\n{link_firma}\n"
            f"Codice OTP di accesso: {otp}\n\n"
            "Restiamo a disposizione per ogni chiarimento.\n"
            "Cordiali saluti,\nPolisEnergia srl"
        )
        
        corpo_mail = st.text_area("Modifica il testo dell'email:", value=testo_predefinito, height=200)
        
        if st.button("🚀 INVIA EMAIL AL CLIENTE", use_container_width=True):
            if not email_dest:
                st.error("Inserisci l'email del cliente prima di inviare!")
            else:
                try:
                    with st.spinner("Invio in corso..."):
                        # Configurazione Messaggio
                        msg = MIMEMultipart()
                        msg['From'] = SENDER_EMAIL
                        msg['To'] = email_dest
                        msg['Cc'] = MAIL_CC
                        msg['Subject'] = f"Preventivo PolisEnergia n. {st.session_state.current_cod} - {nome}"
                        
                        msg.attach(MIMEText(corpo_mail, 'plain'))
                        
                        # Allegato PDF
                        part = MIMEApplication(st.session_state.pdf_bytes, Name=f"Preventivo_{st.session_state.current_cod}.pdf")
                        part['Content-Disposition'] = f'attachment; filename="Preventivo_{st.session_state.current_cod}.pdf"'
                        msg.attach(part)
                        
                        # Invio tramite SMTP
                        context = ssl.create_default_context()
                        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
                            server.login(SENDER_EMAIL, SENDER_PASSWORD)
                            # Creiamo la lista dei destinatari inclusa la CC
                            destinatari = [email_dest] + ([MAIL_CC] if MAIL_CC else [])
                            server.send_message(msg)
                            
                        st.success(f"✅ Email inviata con successo a {email_dest}!")
                except Exception as e:
                    st.error(f"Errore durante l'invio: {e}")

    # --- FOOTER (Opzionale) ---
    st.sidebar.divider()
    st.sidebar.caption(f"PolisEnergia Internal Tools v1.1 © {datetime.now().year}")
    # Logo o Nome Azienda



    # --- VISTA CARMINE ---
    st.title("⚡ PolisEnergia - Preventivatore")

    # Modifica la riga aggiungendo key="pulisci_prev"
    if st.button("🧹 PULISCI TUTTO", use_container_width=True, key="pulisci_prev"):
        for key in list(st.session_state.keys()): 
            del st.session_state[key]
        st.rerun()

    # --- 4. AZIONI ---
    if st.button("📄 1. GENERA PDF E ARCHIVIA", type="primary", use_container_width=True, key="genera_pdf_preventivatore_unico"):
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
        link = f"https://operation-polisenergia.streamlit.app/?codice={st.session_state.current_cod}&otp={otp}"
    
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
        
    st.set_page_config(page_title="Operation PolisEnergia", page_icon="🖋️")


    # --- FUNZIONI TECNICHE ---
    def format_franchigia(p):
        val = round(p * 1.1, 2)
        if round(val, 1) != val:
            return float(math.ceil(val))
        return val
    # Footer
    st.sidebar.divider()
    st.sidebar.caption(f"Versione Web 1.0 - {datetime.now().year}")
