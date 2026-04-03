import streamlit as st
import math
import pandas as pd
import secrets
import io
import xml.etree.ElementTree as ET
import re
import os
import smtplib
import ssl
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import text
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# ==============================================================================
# 1. CONFIGURAZIONE PAGINA (una sola chiamata, sempre la prima)
# ==============================================================================
st.set_page_config(
    page_title="PolisEnergia - Operation Suite",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="auto",
)

# ==============================================================================
# 2. COSTANTI GLOBALI
# ==============================================================================
IBAN_POLIS          = "IT80P0103015200000007044056"
NOME_BANCA          = "Monte dei Paschi di Siena"
INTESTATARIO        = "POLISENERGIA SRL"
IBAN_LABEL          = f"{IBAN_POLIS} - {NOME_BANCA}"
MAIL_CC             = "assistenza@polisenergia.it"
APP_URL             = "https://operation-polisenergia.streamlit.app"
OTP_SCADENZA_GIORNI = 30   # giorni di validità del link di firma

# Tariffe preventivo
TIC_DOMESTICO_LE6   = 62.30
TIC_ALTRI_USI_BT    = 78.81
TIC_MT              = 62.74
ONERI_ISTRUTTORIA   = 27.42
SPOSTAMENTO_10MT    = 226.36
FISSO_BASE_CALCOLO  = 25.88
COSTO_PASSAGGIO_MT  = 494.83

# ==============================================================================
# 3. CSS (una sola volta)
# ==============================================================================
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
        background-color: rgba(255,255,255,0.2) !important;
        border-radius: 50% !important;
        left: 10px !important;
        top: 10px !important;
    }
    [data-testid="stSidebarCollapsedControl"] svg { fill: white !important; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. FUNZIONI DI UTILITÀ
# ==============================================================================

def formatta_data_italiana(data_raw: str) -> str:
    """Converte qualsiasi formato data in GG/MM/AAAA."""
    d = str(data_raw).strip().split(' ')[0]
    try:
        parti = re.split(r'[/.\-]', d)
        if len(parti) == 3:
            if len(parti[0]) == 4:          # formato ISO: AAAA-MM-GG
                anno, mese, giorno = parti[0], parti[1].zfill(2), parti[2].zfill(2)
            else:                            # formato italiano: GG/MM/AAAA
                giorno, mese, anno = parti[0].zfill(2), parti[1].zfill(2), parti[2]
            if len(anno) == 2:
                anno = "20" + anno
            return f"{giorno}/{mese}/{anno}"
    except Exception:
        pass
    return d


def pulisci_valore(valore) -> str | None:
    """Pulisce un valore di lettura per il formato XML (9 cifre con zfill)."""
    val = str(valore).strip().lower()
    if val in {"", "nan", "none", "0", "0,00", "0.00"}:
        return None
    parte_intera = val.split(',')[0]
    if '.' in parte_intera and len(parte_intera.split('.')[-1]) <= 2:
        parte_intera = parte_intera.rsplit('.', 1)[0]
    solo_n = "".join(filter(str.isdigit, parte_intera.replace('.', '')))
    if not solo_n or not solo_n.isdigit():
        return None
    return solo_n.zfill(9) if int(solo_n) > 0 else None


def format_franchigia(p: float) -> float:
    """Applica la franchigia del 10% arrotondando al decimo superiore se necessario."""
    val = round(p * 1.1, 2)
    return float(math.ceil(val * 10) / 10)


def get_smtp_config() -> dict:
    """Legge le credenziali SMTP dai secrets di Streamlit."""
    return {
        "sender":   st.secrets["EMAIL_SENDER"],
        "password": st.secrets["EMAIL_PASSWORD"],
        "server":   st.secrets["EMAIL_SERVER"],
        "port":     int(st.secrets["EMAIL_PORT"]),
    }


def genera_otp() -> str:
    """Genera un OTP a 6 cifre crittograficamente sicuro."""
    return str(secrets.randbelow(900000) + 100000)


def otp_scaduto(data_creazione_str: str) -> bool:
    """
    Restituisce True se l'OTP è scaduto (oltre OTP_SCADENZA_GIORNI giorni).
    data_creazione_str deve essere nel formato '%d/%m/%Y %H:%M'.
    """
    try:
        data_creazione = datetime.strptime(data_creazione_str, "%d/%m/%Y %H:%M")
        return datetime.now() > data_creazione + timedelta(days=OTP_SCADENZA_GIORNI)
    except Exception:
        return True  # Se non riusciamo a leggere la data, consideriamo scaduto


def invia_email(smtp: dict, to: str, subject: str, body: str,
                pdf_bytes: bytes = None, pdf_name: str = None):
    """Invia una email con allegato PDF opzionale."""
    msg = MIMEMultipart()
    msg['From']    = smtp["sender"]
    msg['To']      = to
    msg['Cc']      = MAIL_CC
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    if pdf_bytes and pdf_name:
        part = MIMEApplication(pdf_bytes, Name=pdf_name)
        part['Content-Disposition'] = f'attachment; filename="{pdf_name}"'
        msg.attach(part)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp["server"], smtp["port"], context=ctx) as server:
        server.login(smtp["sender"], smtp["password"])
        server.send_message(msg)

# ==============================================================================
# 5. GENERAZIONE PDF PREVENTIVO
# ==============================================================================

def genera_pdf_polis(d: dict) -> bytes:
    """Genera il PDF del preventivo e restituisce i bytes."""
    BLUE_P     = (0, 51, 102)
    GRAY_LIGHT = (245, 245, 245)
    GRAY_TEXT  = (60, 60, 60)

    pdf = FPDF()
    pdf.add_page()

    # Header blu
    pdf.set_fill_color(*BLUE_P)
    pdf.rect(0, 0, 210, 45, 'F')

    try:
        pdf.image("logo_polis.png", 10, 12, 35)
    except Exception:
        pdf.set_xy(10, 15)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("helvetica", "B", 20)
        pdf.cell(0, 10, "PolisEnergia srl")

    pdf.set_xy(120, 12)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "", 8)
    pdf.multi_cell(
        80, 4,
        "Via Terre delle Risaie, 4 - 84131 Salerno (SA)\n"
        "P.IVA 05050950657\nassistenza@polisenergia.it\nwww.polisenergia.it",
        align='R'
    )

    # Titolo e data
    pdf.set_xy(10, 55)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, f"PREVENTIVO N. {d['Codice']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Emesso il: {datetime.now().strftime('%d/%m/%Y')}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Dati cliente
    pdf.ln(8)
    pdf.set_fill_color(*GRAY_LIGHT)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 10, f"  SPETT.LE CLIENTE: {d['Cliente']}",
             fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.cell(0, 7, f"  POD: {d['POD']} | Indirizzo: {d['Indirizzo']}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Tabella prestazioni
    pdf.ln(10)
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.2)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(*BLUE_P)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, "  DESCRIZIONE PRESTAZIONE", border='B', fill=True)
    pdf.cell(50, 10, "IMPORTO  ", border='B', fill=True, align='R',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_text_color(*GRAY_TEXT)
    voci = [
        ("Quota Tecnica",           d['C_Tec']),
        ("Oneri Amministrativi",    d['Oneri']),
        ("Oneri Gestione Pratica",  d['Gestione']),
    ]
    fill = False
    for voce, importo in voci:
        pdf.set_fill_color(250, 250, 250) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_font("helvetica", "", 10)
        pdf.cell(140, 9, f"  {voce}", border='B', fill=True)
        pdf.cell(50, 9, f"{importo:.2f} EUR  ", border='B', fill=True, align='R',
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        fill = not fill

    # Totali
    pdf.ln(3)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(140, 8, "Totale Imponibile", align='R')
    pdf.cell(50, 8, f"{d['Imponibile']:.2f} EUR  ", align='R',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(140, 8, f"IVA ({d['IVA_Perc']}%)", align='R')
    pdf.cell(50, 8, f"{d['IVA_Euro']:.2f} EUR  ", align='R',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(*BLUE_P)
    pdf.set_fill_color(230, 240, 250)
    pdf.cell(140, 12, "  TOTALE DA CORRISPONDERE", fill=True)
    pdf.cell(50, 12, f"{d['Totale']:.2f} EUR  ", fill=True, align='R',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Pagamento
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, "MODALITA' DI PAGAMENTO:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(0, 5, f"Bonifico Bancario IBAN: {d['IBAN']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 5, f"CAUSALE OBBLIGATORIA: Accettazione Preventivo {d['Codice']}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Note a piè di pagina
    pdf.set_y(-65)
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(120, 120, 120)
    for riga in [
        "L'esecuzione della prestazione è subordinata al verificarsi delle seguenti condizioni:",
        "- conferma della proposta pervenuta entro 30 gg dalla presente richiesta;",
        "- comunicazione dell'avvenuto completamento di eventuali opere/autorizzazioni a cura del cliente finale.",
        "Il presente documento deve essere inviato firmato a: assistenza@polisenergia.it",
    ]:
        pdf.cell(0, 3.5, riga, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Riga firma
    pdf.set_y(-35)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, "Firma per Accettazione Cliente", align='R',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.line(140, pdf.get_y() + 15, 200, pdf.get_y() + 15)

    return bytes(pdf.output())

# ==============================================================================
# 6. PAGINA CLIENTE: ACCETTAZIONE ONLINE (intercettazione via query params)
# ==============================================================================

codice_param = st.query_params.get("codice", "")
otp_param    = st.query_params.get("otp", "")

if otp_param and codice_param:
    st.title("🖋️ Accettazione Online Preventivo")
    cod_u = str(codice_param).strip().replace('.0', '')
    otp_u = str(otp_param).strip()

    try:
        conn   = st.connection("gsheets", type=GSheetsConnection)
        df     = conn.read(ttl=0)
        df['Codice_Clean'] = df['Codice'].astype(str).str.strip().str.replace('.0', '', regex=False)

        if cod_u not in df['Codice_Clean'].values:
            st.error("⚠️ Link non valido o preventivo non trovato. Contatta PolisEnergia.")
            st.stop()

        idx            = df[df['Codice_Clean'] == cod_u].index[0]
        nome_cliente   = df.at[idx, "Cliente"]
        stato_attuale  = str(df.at[idx, "Stato"]).strip()

        # Già firmato
        if stato_attuale == "ACCETTATO":
            st.success("✅ Questo preventivo è già stato firmato. Grazie!")
            st.stop()

        # Verifica scadenza OTP (usa la colonna "Data" di creazione preventivo)
        data_creazione = str(df.at[idx, "Data"]).strip()
        # La colonna Data contiene solo GG/MM/AAAA — aggiungiamo orario fittizio 00:00
        # Se esiste una colonna Data_OTP più precisa, usare quella
        try:
            data_per_scadenza = datetime.strptime(data_creazione, "%d/%m/%Y")
            scaduto = datetime.now() > data_per_scadenza + timedelta(days=OTP_SCADENZA_GIORNI)
        except Exception:
            scaduto = True

        if scaduto:
            st.error(
                f"⏰ Il link di firma è scaduto (validità {OTP_SCADENZA_GIORNI} giorni). "
                f"Contatta PolisEnergia per ricevere un nuovo preventivo."
            )
            st.stop()

        try:
            importo_totale = float(df.at[idx, "Totale"])
        except Exception:
            importo_totale = 0.0

        # Calcolo giorni rimanenti
        data_scadenza   = data_per_scadenza + timedelta(days=OTP_SCADENZA_GIORNI)
        giorni_rimanenti = (data_scadenza - datetime.now()).days

        # Box istruzioni pagamento
        st.markdown(f"""
            <div style="background:rgba(255,255,255,0.1);padding:20px;border-radius:10px;
                        border:1px solid white;margin-bottom:25px;">
                <h3 style="color:white;margin-top:0;">💳 Istruzioni per il pagamento</h3>
                <p style="color:white;font-size:1.1em;"><strong>Cliente:</strong> {nome_cliente}</p>
                <p style="color:white;font-size:1.1em;">
                    <strong>Importo:</strong> {importo_totale:.2f} EUR
                </p>
                <p style="color:#ffe08a;font-size:0.9em;">
                    ⏳ Link valido ancora per <strong>{giorni_rimanenti} giorni</strong>
                    (scade il {data_scadenza.strftime('%d/%m/%Y')})
                </p>
                <hr style="border-color:rgba(255,255,255,0.3);">
                <p style="color:white;font-weight:bold;margin-bottom:5px;">COORDINATE BANCARIE:</p>
                <ul style="color:white;list-style-type:none;padding-left:0;">
                    <li><strong>Intestatario:</strong> {INTESTATARIO}</li>
                    <li><strong>Banca:</strong> {NOME_BANCA}</li>
                    <li><strong>IBAN:</strong>
                        <span style="font-family:monospace;background:rgba(0,0,0,0.2);
                                     padding:2px 5px;">{IBAN_POLIS}</span>
                    </li>
                    <li><strong>Causale:</strong> Accettazione Preventivo {cod_u} - {nome_cliente}</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<p style='color:white;font-weight:bold;'>Inserisci l'OTP ricevuto via mail:</p>",
                    unsafe_allow_html=True)
        otp_in = st.text_input("OTP:", max_chars=6, label_visibility="collapsed")

        if st.button("✅ FIRMA E ACCETTA ORA"):
            if not otp_in.strip():
                st.warning("Inserisci il codice OTP prima di procedere.")
            elif otp_in.strip() == otp_u:
                df.at[idx, "Stato"]      = "ACCETTATO"
                df.at[idx, "Data Firma"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                conn.update(data=df.drop(columns=['Codice_Clean']))

                # Notifica interna (silenziosa in caso di errore)
                try:
                    smtp = get_smtp_config()
                    invia_email(
                        smtp=smtp,
                        to=smtp["sender"],
                        subject=f"✅ PREVENTIVO FIRMATO: {nome_cliente}",
                        body=(
                            f"Il cliente {nome_cliente} ha accettato il preventivo {cod_u}.\n"
                            f"Data firma: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                            f"Controlla il database."
                        )
                    )
                except Exception:
                    pass

                st.success("✅ Documento firmato con successo!")
                st.balloons()
            else:
                st.error("❌ OTP non corretto. Riprova o contatta PolisEnergia.")

    except Exception as e:
        st.error("Si è verificato un errore tecnico. Contatta PolisEnergia.")
        # Log tecnico solo in sviluppo — rimuovere in produzione:
        st.caption(f"Dettaglio tecnico: {e}")

    st.stop()   # Il cliente non vede mai l'area operativa

# ==============================================================================
# 7. AUTENTICAZIONE OPERATORI
# ==============================================================================
if "autenticato" not in st.session_state:
    st.session_state.autenticato = False

if not st.session_state.autenticato:
    st.sidebar.title("🔒 Area Riservata")
    pwd = st.sidebar.text_input("Password", type="password")
    if pwd:
        password_corretta = st.secrets.get("APP_PASSWORD", "")
        if password_corretta and pwd == password_corretta:
            st.session_state.autenticato = True
            st.rerun()
        else:
            st.sidebar.error("Password errata")
    st.title("Polisenergia - Operation Suite")
    st.info("Effettua il login nella barra laterale per accedere.")
    st.stop()

# ==============================================================================
# 8. NAVIGAZIONE (solo per operatori autenticati)
# ==============================================================================
st.sidebar.success("✅ Accesso Autorizzato")
st.sidebar.title("Navigazione")
scelta = st.sidebar.radio(
    "Cosa vuoi fare?",
    ["Autoletture", "Preventivo di Connessione", "📋 Archivio Preventivi"]
)
st.sidebar.divider()
st.sidebar.caption(f"PolisEnergia Internal Tools v1.3 © {datetime.now().year}")

# ==============================================================================
# 9. SEZIONE: AUTOLETTURE
# ==============================================================================
if scelta == "Autoletture":
    st.header("📊 Generatore Flussi Autoletture")
    FILE_ARERA = "arera.csv"

    if not os.path.exists(FILE_ARERA):
        st.error(f"❌ File '{FILE_ARERA}' non trovato. Caricalo nel repository per continuare.")
        st.stop()

    piva_mittente = st.text_input("P.IVA Venditore (Mittente)", value="05050950657")
    st.divider()
    st.subheader("📁 Caricamento File")
    col1, col2 = st.columns(2)
    file_tech   = col1.file_uploader("1. Anagrafica Tecnica (Excel)", type=["xlsx", "xls"])
    file_letture = col2.file_uploader("2. Autoletture (CSV)", type="csv")

    if file_tech and file_letture:
        if st.button("🚀 GENERA PACCHETTO XML (.ZIP)", use_container_width=True):
            try:
                zip_buffer   = io.BytesIO()
                progress_bar = st.progress(0)

                with st.spinner("Elaborazione in corso..."):
                    # --- Lettura ARERA ---
                    df_arera = pd.read_csv(
                        FILE_ARERA, encoding='latin-1', sep=';',
                        on_bad_lines='skip', dtype=str
                    )
                    df_arera.columns = [c.strip().upper() for c in df_arera.columns]
                    mappa_piva_distr = {
                        "".join(filter(str.isdigit, str(r['PARTITA IVA']))).zfill(11):
                        {'nome': str(r['RAGIONE SOCIALE']).strip().upper()}
                        for _, r in df_arera.iterrows()
                    }

                    # --- Lettura Anagrafica Tecnica ---
                    df_tech = pd.read_excel(file_tech, dtype=str)
                    df_tech.columns = [c.strip().upper() for c in df_tech.columns]

                    piva_polis_clean = "".join(filter(str.isdigit, piva_mittente)).zfill(11)
                    df_tech['PIVA_UDD_CLEAN'] = (df_tech['PIVA_UDD']
                                                  .str.replace(r'\D', '', regex=True).str.zfill(11))
                    df_tech['PIVA_DD_CLEAN']  = (df_tech['PIVA_DD']
                                                  .str.replace(r'\D', '', regex=True).str.zfill(11))
                    df_tech['COD_PDR_CLEAN']  = (df_tech['COD_PDR']
                                                  .str.split('.').str[0].str.strip().str.zfill(14))

                    df_tech_polis   = df_tech[df_tech['PIVA_UDD_CLEAN'] == piva_polis_clean].copy()
                    df_tech_esterni = df_tech[df_tech['PIVA_UDD_CLEAN'] != piva_polis_clean].copy()

                    mappa_matr_pdr  = pd.Series(
                        df_tech_polis['MATR_MIS'].values,
                        index=df_tech_polis['COD_PDR_CLEAN']
                    ).to_dict()
                    mappa_pdr_distr = pd.Series(
                        df_tech_polis['PIVA_DD_CLEAN'].values,
                        index=df_tech_polis['COD_PDR_CLEAN']
                    ).to_dict()
                    c_matr_corr = next((c for c in df_tech.columns if 'CORR' in c), None)
                    mappa_matr_corr = (
                        pd.Series(df_tech_polis[c_matr_corr].values,
                                  index=df_tech_polis['COD_PDR_CLEAN']).to_dict()
                        if c_matr_corr else {}
                    )

                    # --- Lettura Autoletture ---
                    df_let = pd.read_csv(
                        file_letture, sep=None, engine='python',
                        encoding='utf-8-sig', dtype=str
                    )
                    df_let.columns = [c.strip().upper() for c in df_let.columns]
                    col_pdr  = next(c for c in df_let.columns if 'PDR' in c)
                    col_data = next(c for c in df_let.columns if 'DATA' in c)
                    col_lett = next(c for c in df_let.columns if 'LETTURA' in c and 'CORRE' not in c)
                    col_corr = next((c for c in df_let.columns if 'CORRETTORE' in c or 'CONVERT' in c), None)

                    progress_bar.progress(25)

                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:

                        # Excel per distributori esterni
                        if not df_tech_esterni.empty:
                            grp_cols = ['PIVA_UDD', 'RAGIONE_SOCIALE_UDD']
                            for (piva_udd, rag_soc), group in df_tech_esterni.groupby(grp_cols):
                                group_pdr_clean  = group['COD_PDR_CLEAN'].tolist()
                                autolett_est = df_let[
                                    df_let[col_pdr].str.split('.').str[0].str.zfill(14)
                                    .isin(group_pdr_clean)
                                ]
                                if not autolett_est.empty:
                                    nome_ex = (f"AUTOLETTURE_ESTERNE_{piva_udd}_"
                                               f"{re.sub(r'\\W+', '', rag_soc)[:15]}.xlsx")
                                    buf = io.BytesIO()
                                    autolett_est.to_excel(buf, index=False)
                                    zip_file.writestr(nome_ex, buf.getvalue())

                        progress_bar.progress(50)

                        # Raggruppamento XML per Polis
                        gruppi: dict[str, list] = defaultdict(list)
                        for _, riga in df_let.iterrows():
                            pdr_clean   = str(riga[col_pdr]).split('.')[0].zfill(14)
                            piva_dd     = mappa_pdr_distr.get(pdr_clean)
                            if not piva_dd:
                                continue
                            info_arera = mappa_piva_distr.get(piva_dd)
                            if not info_arera:
                                continue
                            ln = pulisci_valore(riga[col_lett])
                            lc = pulisci_valore(riga[col_corr]) if col_corr else None
                            if ln:
                                gruppi[piva_dd].append({
                                    'distr_nome': info_arera['nome'],
                                    'pdr':   pdr_clean,
                                    'data':  formatta_data_italiana(riga[col_data]),
                                    'lett':  ln,
                                    'corr':  lc,
                                    'm_pdr': str(mappa_matr_pdr.get(pdr_clean, "0")).split('.')[0],
                                    'm_corr': (str(mappa_matr_corr[pdr_clean]).split('.')[0]
                                               if pdr_clean in mappa_matr_corr else None),
                                })

                        # Scrittura XML nello ZIP
                        tot_g = len(gruppi)
                        for i, (piva_d, lista) in enumerate(gruppi.items()):
                            root = ET.Element("Prestazione", cod_servizio="TAL", cod_flusso="0050")
                            id_req = ET.SubElement(root, "IdentificativiRichiesta")
                            ET.SubElement(id_req, "piva_utente").text = piva_mittente
                            ET.SubElement(id_req, "piva_distr").text  = piva_d
                            for item in lista:
                                d = ET.SubElement(root, "DatiPdR")
                                ET.SubElement(d, "cod_pdr").text             = item['pdr']
                                ET.SubElement(d, "matr_mis").text            = item['m_pdr']
                                ET.SubElement(d, "data_com_autolet_cf").text = item['data']
                                ET.SubElement(d, "let_tot_prel").text        = item['lett']
                                if item['corr']:
                                    ET.SubElement(d, "let_tot_conv").text = item['corr']
                                    if item['m_corr'] and item['m_corr'] not in {"nan", "None", ""}:
                                        ET.SubElement(d, "matr_conv").text = item['m_corr']

                            xml_str    = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                            clean_name = re.sub(r'\W+', '', lista[0]['distr_nome'])[:15]
                            zip_file.writestr(f"TAL_0050_{piva_d}_{clean_name}.xml", xml_str)
                            progress_bar.progress(50 + int(((i + 1) / tot_g) * 50))

                zip_buffer.seek(0)
                progress_bar.empty()
                st.success(f"✅ Completato! Creati {len(gruppi)} file XML.")
                st.download_button(
                    label="📥 SCARICA PACCHETTO ZIP",
                    data=zip_buffer,
                    file_name=f"Autoletture_{datetime.now().strftime('%d_%m_%H%M')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

            except Exception as e:
                st.error(f"Errore durante l'elaborazione: {e}")

# ==============================================================================
# 10. SEZIONE: PREVENTIVO DI CONNESSIONE
# ==============================================================================
elif scelta == "Preventivo di Connessione":
    st.title("⚡ PolisEnergia - Preventivatore")

    # --- Dati cliente ---
    c1, c2 = st.columns(2)
    nome        = c1.text_input("Ragione Sociale", key="n").upper()
    email_dest  = c1.text_input("Email Cliente",   key="m")
    indirizzo   = c1.text_input("Indirizzo Impianto", key="ind")
    pod         = c2.text_input("POD",              key="p").upper()
    regime      = c2.selectbox("Regime IVA", ["10%", "22%", "Esente", "P.A."], key="r")

    st.divider()

    # --- Configurazione pratica ---
    c3, c4 = st.columns([2, 1])
    pratica  = c3.selectbox(
        "Tipo Pratica",
        ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento Contatore"],
        key="prat"
    )
    tipo_ut = c4.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True, key="ut")

    # Inizializzazione valori
    p_att, p_new, c_dist, delta, tar = 0.0, 0.0, 0.0, 0.0, 0.0
    passaggio_mt = False
    t_partenza   = "BT"

    if "Potenza" in pratica or "Subentro" in pratica:
        col1, col2 = st.columns(2)
        if tipo_ut == "Altri Usi":
            t_partenza   = col1.selectbox("Tensione", ["BT", "MT"], key="t")
            if t_partenza == "BT":
                passaggio_mt = col1.checkbox("Passaggio a MT?", key="mt")
        p_att = col1.number_input("kW Attuali",   value=0.0, key="pa")
        p_new = col2.number_input("kW Richiesti", value=0.0, key="pn")

    elif "Nuova" in pratica:
        p_new  = st.number_input("kW Richiesti",  value=0.0, key="pnc")
        c_dist = st.number_input("Quota Distanza €", 0.0,    key="dist")

    elif "Spostamento" in pratica:
        s_dist = st.radio("Distanza", ["Entro 10 metri", "Oltre 10 metri"], key="sd")
        c_dist = (SPOSTAMENTO_10MT if "Entro" in s_dist
                  else st.number_input("Costo Rilievo €", 0.0, key="sdc"))

    # Franchigia
    limitatore = False
    if tipo_ut == "Altri Usi" and 15 < p_new <= 30:
        limitatore = st.checkbox("Abilita Limitatore (Franchigia +10%)", value=True, key="lim_flag")

    # Calcolo delta e tariffa
    if p_new > 0:
        applica_franchigia = tipo_ut == "Domestico" or (tipo_ut == "Altri Usi" and limitatore)
        if p_new <= 30 and applica_franchigia:
            v_new = round(p_new * 1.1, 1)
            v_att = round(p_att * 1.1, 1) if p_att > 0 else 0.0
        else:
            v_new, v_att = p_new, p_att
        delta = round(v_new - v_att, 1)

        if "Nuova" in pratica:
            tar = TIC_ALTRI_USI_BT
        elif tipo_ut == "Domestico" and p_new <= 6:
            tar = TIC_DOMESTICO_LE6
        elif t_partenza == "MT" or passaggio_mt:
            tar = TIC_MT
        else:
            tar = TIC_ALTRI_USI_BT

    # Calcolo importi
    if "Spostamento" in pratica:
        c_tec = c_dist
    elif "Nuova" in pratica:
        c_tec = round((delta * tar) + c_dist, 2)
    else:
        c_tec = round(delta * tar, 2)

    if passaggio_mt:
        c_tec += COSTO_PASSAGGIO_MT

    c_gest = round((c_tec + FISSO_BASE_CALCOLO) * 0.1, 2)
    imp    = round(c_tec + c_gest + ONERI_ISTRUTTORIA, 2)
    iva_p  = 10 if "10" in regime else (22 if "22" in regime or "P.A." in regime else 0)
    iva_e  = round(imp * (iva_p / 100), 2)
    bollo  = 2.0 if (regime == "Esente" and imp > 77.47) else 0.0
    totale = (round(imp + bollo, 2)
              if "P.A." in regime
              else round(imp + iva_e + bollo, 2))

    # --- Anteprima calcolo ---
    st.subheader("📊 Anteprima Calcolo")
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        st.table(pd.DataFrame({
            "Voce":       ["Quota TIC", "Gestione Polis", "Istruttoria", "IVA", "Bollo"],
            "Valore (€)": [f"{c_tec:.2f}", f"{c_gest:.2f}",
                           f"{ONERI_ISTRUTTORIA:.2f}", f"{iva_e:.2f}", f"{bollo:.2f}"],
        }))
    with col_t2:
        st.metric("TOTALE", f"{totale:.2f} €")
        if "Spostamento" not in pratica:
            st.info(f"Delta: {delta} kW | Tariffa: {tar} €/kW")

    st.divider()

    # --- Azioni principali ---
    btn1, btn2 = st.columns(2)

    with btn1:
        if st.button("📄 1. GENERA PDF E ARCHIVIA", type="primary",
                     use_container_width=True, key="btn_genera"):
            # Validazione campi obbligatori
            errori = []
            if not nome.strip():
                errori.append("Ragione Sociale")
            if not pod.strip():
                errori.append("POD")
            if not email_dest.strip():
                errori.append("Email Cliente")
            if p_new <= 0 and "Spostamento" not in pratica:
                errori.append("kW Richiesti (deve essere > 0)")
            if errori:
                st.error(f"⚠️ Compila i campi obbligatori: {', '.join(errori)}")
            else:
                cod = datetime.now().strftime("%y%m%d%H%M%S")
                st.session_state.current_cod  = cod
                st.session_state.pdf_bytes    = genera_pdf_polis({
                    "Codice": cod, "Cliente": nome, "POD": pod, "Indirizzo": indirizzo,
                    "C_Tec": c_tec, "Oneri": ONERI_ISTRUTTORIA, "Gestione": c_gest,
                    "Imponibile": imp, "IVA_Perc": iva_p, "IVA_Euro": iva_e,
                    "Totale": totale, "IBAN": IBAN_LABEL,
                })
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    df   = conn.read(ttl=0)
                    nuova_riga = pd.DataFrame([{
                        "Data":    datetime.now().strftime("%d/%m/%Y"),
                        "Codice":  str(cod),
                        "Cliente": nome,
                        "POD":     pod,
                        "Totale":  totale,
                        "Stato":   "Inviato",
                    }])
                    conn.update(data=pd.concat([df, nuova_riga], ignore_index=True))
                    st.success(f"✅ Preventivo {cod} generato e archiviato!")
                except Exception as e:
                    st.warning(f"PDF generato, ma errore salvataggio Google Sheets: {e}")

    with btn2:
        if 'pdf_bytes' in st.session_state and st.session_state.pdf_bytes:
            st.download_button(
                label="📥 2. SCARICA PDF",
                data=io.BytesIO(st.session_state.pdf_bytes),
                file_name=f"Preventivo_{st.session_state.get('current_cod', 'draft')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="btn_download",
            )
        else:
            st.button("📥 2. SCARICA PDF", disabled=True,
                      use_container_width=True, key="btn_download_dis")

    # --- Invio email (abilitato solo dopo generazione PDF) ---
    if 'current_cod' in st.session_state and 'pdf_bytes' in st.session_state:
        st.divider()
        st.subheader("📧 Invio Documentazione al Cliente")

        if 'current_otp' not in st.session_state:
            st.session_state.current_otp = genera_otp()   # OTP crittograficamente sicuro

        otp      = st.session_state.current_otp
        cod      = st.session_state.current_cod
        link     = f"{APP_URL}/?codice={cod}&otp={otp}"
        testo_default = (
            f"Spett.le {nome},\n"
            f"in allegato il preventivo n. {cod}.\n\n"
            f"Per firmare digitalmente clicca qui: {link}\n"
            f"OTP: {otp}\n\n"
            f"Il link è valido per {OTP_SCADENZA_GIORNI} giorni.\n\n"
            f"Cordiali saluti,\nPolisEnergia srl"
        )
        corpo_mail = st.text_area("Modifica testo email:", value=testo_default, height=180)

        if st.button("🚀 INVIA EMAIL AL CLIENTE", use_container_width=True, key="btn_invia"):
            if not email_dest:
                st.error("Inserisci l'indirizzo email del cliente prima di inviare.")
            else:
                try:
                    with st.spinner("Invio in corso..."):
                        smtp = get_smtp_config()
                        invia_email(
                            smtp=smtp,
                            to=email_dest,
                            subject=f"Preventivo PolisEnergia n. {cod}",
                            body=corpo_mail,
                            pdf_bytes=st.session_state.pdf_bytes,
                            pdf_name=f"Preventivo_{cod}.pdf",
                        )
                    st.success("✅ Email inviata con successo!")
                except Exception as e:
                    st.error(f"Errore durante l'invio: {e}")
    else:
        st.info("ℹ️ Genera il PDF prima di procedere con l'invio della mail.")

    st.divider()

    # Pulisci con conferma
    if 'conferma_pulizia' not in st.session_state:
        st.session_state.conferma_pulizia = False

    if not st.session_state.conferma_pulizia:
        if st.button("🧹 PULISCI TUTTO", use_container_width=True, key="pulisci"):
            st.session_state.conferma_pulizia = True
            st.rerun()
    else:
        st.warning("⚠️ Sei sicuro? Tutti i dati del preventivo corrente verranno persi.")
        c_si, c_no = st.columns(2)
        if c_si.button("✅ Sì, pulisci", use_container_width=True, key="pulisci_si"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        if c_no.button("❌ Annulla", use_container_width=True, key="pulisci_no"):
            st.session_state.conferma_pulizia = False
            st.rerun()

# ==============================================================================
# 11. SEZIONE: ARCHIVIO PREVENTIVI
# ==============================================================================
elif scelta == "📋 Archivio Preventivi":
    st.title("📋 Archivio Preventivi")

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df   = conn.read(ttl=0)

        if df.empty:
            st.info("Nessun preventivo in archivio.")
            st.stop()

        # Calcolo stato effettivo con scadenza
        oggi = datetime.now()
        def stato_effettivo(row):
            if str(row.get("Stato", "")).strip() == "ACCETTATO":
                return "ACCETTATO"
            try:
                data_c = datetime.strptime(str(row["Data"]).strip(), "%d/%m/%Y")
                if oggi > data_c + timedelta(days=OTP_SCADENZA_GIORNI):
                    return "SCADUTO"
            except Exception:
                pass
            return "INVIATO"

        df["Stato Reale"] = df.apply(stato_effettivo, axis=1)

        # Filtri
        col_f1, col_f2 = st.columns([2, 1])
        filtro_testo = col_f1.text_input("🔍 Cerca per cliente o codice", "")
        filtro_stato = col_f2.selectbox("Filtra per stato", ["Tutti", "INVIATO", "ACCETTATO", "SCADUTO"])

        df_view = df.copy()
        if filtro_testo:
            mask = (
                df_view["Cliente"].astype(str).str.contains(filtro_testo, case=False, na=False) |
                df_view["Codice"].astype(str).str.contains(filtro_testo, case=False, na=False)
            )
            df_view = df_view[mask]
        if filtro_stato != "Tutti":
            df_view = df_view[df_view["Stato Reale"] == filtro_stato]

        # Badge colorati
        def colora_stato(val):
            colori = {
                "ACCETTATO": "background-color: #d4edda; color: #155724; font-weight: bold;",
                "SCADUTO":   "background-color: #f8d7da; color: #721c24; font-weight: bold;",
                "INVIATO":   "background-color: #fff3cd; color: #856404; font-weight: bold;",
            }
            return colori.get(val, "")

        cols_show = [c for c in ["Data", "Codice", "Cliente", "POD", "Totale", "Stato Reale", "Data Firma"]
                     if c in df_view.columns]
        st.dataframe(
            df_view[cols_show].style.applymap(colora_stato, subset=["Stato Reale"]),
            use_container_width=True,
            hide_index=True,
        )

        # Riepilogo numerico
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("🟡 Inviati",   len(df[df["Stato Reale"] == "INVIATO"]))
        c2.metric("🟢 Accettati", len(df[df["Stato Reale"] == "ACCETTATO"]))
        c3.metric("🔴 Scaduti",   len(df[df["Stato Reale"] == "SCADUTO"]))

    except Exception as e:
        st.error("Impossibile caricare l'archivio.")
        st.caption(f"Dettaglio tecnico: {e}")
