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
# 5b. GENERAZIONE HTML PREVENTIVO (archivio leggero)
# ==============================================================================
import base64 as _b64
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials as SACredentials

# ID della cartella Drive dove archiviare i preventivi HTML
# Creala a mano su Drive, condividila con il service account e incolla l'ID qui
# oppure mettilo in secrets come DRIVE_FOLDER_ID
DRIVE_FOLDER_ID = st.secrets.get("DRIVE_FOLDER_ID", "")

def carica_html_su_drive(html: str, nome_file: str) -> str:
    """
    Carica l'HTML su Google Drive nella cartella DRIVE_FOLDER_ID.
    Restituisce il link pubblico di visualizzazione del file.
    Richiede che il service account abbia accesso alla cartella.
    """
    info = dict(st.secrets["gcp_service_account"])
    creds = SACredentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    # Caricamento file
    meta = {"name": nome_file, "parents": [DRIVE_FOLDER_ID], "mimeType": "text/html"}
    media = MediaIoBaseUpload(
        io.BytesIO(html.encode("utf-8")),
        mimetype="text/html",
        resumable=False,
    )
    file = service.files().create(body=meta, media_body=media, fields="id").execute()
    file_id = file.get("id")

    # Rende il file leggibile da chiunque abbia il link
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    # Link visualizzatore Drive — funziona senza login con file condiviso pubblicamente
    return f"https://drive.google.com/file/d/{file_id}/view"


def genera_html_polis(d: dict) -> str:
    """Genera il preventivo come stringa HTML standalone (~10KB)."""
    data_str = datetime.now().strftime("%d/%m/%Y")
    scad_str = (datetime.now() + timedelta(days=OTP_SCADENZA_GIORNI)).strftime("%d/%m/%Y")

    # Logo incorporato come Base64 — nessuna dipendenza esterna
    logo_tag = '<div class="header-brand">PolisEnergia srl</div>'  # fallback testo
    try:
        with open("logo_polis.png", "rb") as f:
            logo_b64 = _b64.b64encode(f.read()).decode("utf-8")
        logo_tag = f'<img src="data:image/png;base64,{logo_b64}" style="height:40px;max-width:160px;object-fit:contain;" alt="PolisEnergia">'
    except Exception:
        pass  # fallback testo già impostato
    voci = [
        ("Quota Tecnica",          d['C_Tec']),
        ("Oneri Amministrativi",   d['Oneri']),
        ("Oneri Gestione Pratica", d['Gestione']),
    ]
    righe_voci = ""
    for i, (voce, importo) in enumerate(voci):
        bg = "#f7f8fa" if i % 2 == 0 else "#ffffff"
        righe_voci += f"""
        <tr style="background:{bg}">
          <td style="padding:8px 12px;border-bottom:1px solid #e2e6ec;">{voce}</td>
          <td style="padding:8px 12px;text-align:right;border-bottom:1px solid #e2e6ec;">{importo:.2f} EUR</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Preventivo {d['Codice']} — PolisEnergia</title>
<style>
  body{{margin:0;font-family:Helvetica,Arial,sans-serif;font-size:13px;color:#141414;background:#f0f2f5}}
  .page{{max-width:740px;margin:32px auto;background:#fff;box-shadow:0 2px 16px rgba(0,0,0,.10)}}
  .header{{background:#003366;padding:18px 24px;display:flex;justify-content:space-between;align-items:center}}
  .header-brand{{color:#fff;font-size:18px;font-weight:700;letter-spacing:.5px}}
  .header-info{{text-align:right;color:#c8dcf5;font-size:11px;line-height:1.8}}
  .header-info strong{{color:#fff;display:block;font-size:12px;margin-bottom:2px}}
  .accent{{height:3px;background:#005aaa}}
  .body{{padding:28px 24px}}
  .title{{font-size:22px;font-weight:700;margin:0 0 4px}}
  .subtitle{{color:#8c8c8c;font-size:11px;margin:0 0 20px}}
  .cliente-box{{background:#f7f8fa;border-left:3px solid #005aaa;padding:12px 16px;
                display:flex;justify-content:space-between;margin-bottom:24px;border-radius:2px}}
  .cliente-label{{font-size:9px;color:#8c8c8c;text-transform:uppercase;letter-spacing:.5px;margin-bottom:3px}}
  .cliente-name{{font-size:14px;font-weight:700}}
  .pod-val{{font-size:12px;font-weight:700;color:#003366}}
  .pod-addr{{font-size:11px;color:#8c8c8c;margin-top:2px}}
  table{{width:100%;border-collapse:collapse;font-size:12.5px}}
  thead td{{background:#003366;color:#fff;padding:9px 12px;font-weight:700}}
  .subtotal td{{padding:5px 12px;color:#666;font-size:12px}}
  .total-row td{{background:#e6f0fa;color:#003366;font-weight:700;font-size:14px;padding:10px 12px}}
  .section-label{{font-size:9px;font-weight:700;color:#005aaa;letter-spacing:.8px;
                  text-transform:uppercase;margin:24px 0 4px}}
  .section-line{{border:none;border-top:1px solid #005aaa;margin:0 0 10px}}
  .pagamento-row{{display:flex;gap:8px;align-items:baseline;margin-bottom:4px;font-size:12px}}
  .pagamento-label{{color:#8c8c8c;min-width:90px}}
  .iban{{font-family:monospace;background:#f0f2f5;padding:2px 8px;border-radius:3px;font-size:11px}}
  .firma-area{{display:flex;gap:24px;margin-top:28px;align-items:flex-end}}
  .firma-col{{flex:1}}
  .firma-col.data{{max-width:130px}}
  .firma-label{{font-size:10px;color:#8c8c8c;margin-bottom:18px}}
  .firma-line{{border-top:1px solid #aaa;padding-top:4px;color:#ccc;font-size:10px}}
  .footer{{background:#003366;padding:10px 24px}}
  .footer p{{color:#c8dcf5;font-size:10px;margin:0;line-height:1.7}}
  @media print{{body{{background:#fff}}.page{{box-shadow:none;margin:0}}}}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    {logo_tag}
    <div class="header-info">
      <strong>POLISENERGIA SRL</strong>
      Via Terre delle Risaie, 4 — 84131 Salerno (SA)<br>
      P.IVA 05050950657<br>
      assistenza@polisenergia.it · www.polisenergia.it
    </div>
  </div>
  <div class="accent"></div>

  <div class="body">
    <p class="title">Preventivo n. {d['Codice']}</p>
    <p class="subtitle">Emesso il {data_str} &nbsp;—&nbsp; Valido fino al {scad_str}</p>

    <div class="cliente-box">
      <div>
        <div class="cliente-label">Spett.le</div>
        <div class="cliente-name">{d['Cliente']}</div>
      </div>
      <div style="text-align:right">
        <div class="cliente-label">POD</div>
        <div class="pod-val">{d['POD']}</div>
        <div class="pod-addr">{d['Indirizzo']}</div>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <td style="width:76%">Descrizione prestazione</td>
          <td style="text-align:right">Importo</td>
        </tr>
      </thead>
      <tbody>{righe_voci}</tbody>
    </table>

    <table style="margin-top:4px">
      <tbody>
        <tr class="subtotal">
          <td style="text-align:right;width:76%">Totale imponibile</td>
          <td style="text-align:right">{d['Imponibile']:.2f} EUR</td>
        </tr>
        <tr class="subtotal">
          <td style="text-align:right">IVA ({d['IVA_Perc']}%)</td>
          <td style="text-align:right">{d['IVA_Euro']:.2f} EUR</td>
        </tr>
        <tr class="total-row">
          <td>Totale da corrispondere</td>
          <td style="text-align:right">{d['Totale']:.2f} EUR</td>
        </tr>
      </tbody>
    </table>

    <p class="section-label">Modalità di pagamento</p>
    <hr class="section-line">
    <div class="pagamento-row">
      <span class="pagamento-label">Bonifico bancario</span>
      <span class="iban">{d['IBAN']}</span>
    </div>
    <div class="pagamento-row">
      <span class="pagamento-label">Causale:</span>
      <span>Accettazione Preventivo {d['Codice']} — {d['Cliente']}</span>
    </div>

    <div class="firma-area">
      <div class="firma-col">
        <div class="firma-label">Per accettazione (timbro e firma leggibile):</div>
        <div class="firma-line">___________________________________</div>
      </div>
      <div class="firma-col data">
        <div class="firma-label">Data:</div>
        <div class="firma-line">________________</div>
      </div>
    </div>
  </div>

  <div class="footer">
    <p>L'esecuzione della prestazione è subordinata a: conferma della proposta entro 30 gg e
    completamento di eventuali opere/autorizzazioni a cura del cliente finale.<br>
    Inviare il documento firmato a <strong style="color:#fff">assistenza@polisenergia.it</strong></p>
  </div>
</div>
</body>
</html>"""


def html_to_b64(html: str) -> str:
    """Codifica l'HTML in Base64 per il salvataggio su Google Sheets."""
    return _b64.b64encode(html.encode("utf-8")).decode("utf-8")


def b64_to_html(b64: str) -> str:
    """Decodifica l'HTML da Base64."""
    return _b64.b64decode(b64.encode("utf-8")).decode("utf-8")

        
# ==============================================================================
# 6. PAGINA CLIENTE: ACCETTAZIONE ONLINE (intercettazione via query params)
# ==============================================================================

codice_param = st.query_params.get("codice", "")
otp_param    = st.query_params.get("otp", "")

if codice_param:
    st.title("🖋️ Visualizzazione Preventivo")
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

        if not otp_u:
            st.info(f"🔍 Modalità Anteprima Operatore - Cliente: **{nome_cliente}**")
            dati_per_html = df.iloc[idx].to_dict()
            try:
                codice_html = genera_html_polis(dati_per_html)
                st.components.v1.html(codice_html, height=900, scrolling=True)
                st.download_button(
                    label="📥 Scarica file HTML",
                    data=codice_html,
                    file_name=f"Preventivo_{cod_u}.html",
                    mime="text/html"
                )
            except Exception as e:
                st.error(f"Errore nella generazione grafica: {e}")
                st.write("Dati grezzi preventivo:", dati_per_html)
            
            st.stop()
            
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
# 5. GENERAZIONE PDF PREVENTIVO
# ==============================================================================

def genera_pdf_polis(d: dict) -> bytes:
    """Genera il PDF del preventivo con font Lato e logo aziendale."""

    # --- PALETTE ---
    BLUE_DARK  = (0,   51, 102)   # header, intestazioni tabella, totale
    BLUE_LIGHT = (230, 240, 250)  # sfondo riga totale
    BLUE_MID   = (0,   90, 170)   # accento linea decorativa e bordo sinistro box
    GRAY_BG    = (247, 248, 250)  # sfondo box cliente e righe alternate
    GRAY_TEXT  = (60,  60,  60)   # testo corpo
    GRAY_MUTED = (140, 140, 140)  # note, label secondari
    WHITE      = (255, 255, 255)
    BLACK      = (20,  20,  20)

    pdf = FPDF()
    pdf.set_margins(14, 14, 14)
    pdf.add_page()

    # --- FONT LATO (con fallback su Helvetica se i file non esistono) ---
    try:
        pdf.add_font("Lato", "",  "Lato-Regular.ttf", uni=True)
        pdf.add_font("Lato", "B", "Lato-Bold.ttf",    uni=True)
        FONT = "Lato"
    except Exception:
        FONT = "helvetica"

    # ── HEADER ────────────────────────────────────────────────────────────────
    # Banda blu piena
    pdf.set_fill_color(*BLUE_DARK)
    pdf.rect(0, 0, 210, 48, 'F')

    # Linea decorativa sottile azzurra sotto l'header
    pdf.set_fill_color(*BLUE_MID)
    pdf.rect(0, 48, 210, 1.5, 'F')

    # Logo (larghezza 38 mm, verticalmente centrato nella banda)
    LOGO_W = 38
    try:
        pdf.image("logo_polis.png", x=14, y=7, w=LOGO_W)
    except Exception:
        # Fallback testuale se il logo non è disponibile
        pdf.set_xy(14, 14)
        pdf.set_text_color(*WHITE)
        pdf.set_font(FONT, "B", 18)
        pdf.cell(60, 10, "PolisEnergia")

    # Dati aziendali — allineati a destra
    pdf.set_xy(110, 10)
    pdf.set_text_color(*WHITE)
    pdf.set_font(FONT, "B", 8.5)
    pdf.cell(86, 5, "POLISENERGIA SRL", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(110)
    pdf.set_font(FONT, "", 7.5)
    for riga in [
        "Via Terre delle Risaie, 4  —  84131 Salerno (SA)",
        "P.IVA 05050950657",
        "assistenza@polisenergia.it  |  www.polisenergia.it",
    ]:
        pdf.set_x(110)
        pdf.set_text_color(200, 220, 245)   # bianco leggermente smorzato
        pdf.cell(86, 4.5, riga, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── TITOLO DOCUMENTO ──────────────────────────────────────────────────────
    pdf.set_xy(14, 57)
    pdf.set_text_color(*BLACK)
    pdf.set_font(FONT, "B", 17)
    pdf.cell(0, 9, f"Preventivo n. {d['Codice']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_x(14)
    pdf.set_font(FONT, "", 9)
    pdf.set_text_color(*GRAY_MUTED)
    data_str  = datetime.now().strftime("%d/%m/%Y")
    scad_str  = (datetime.now() + timedelta(days=OTP_SCADENZA_GIORNI)).strftime("%d/%m/%Y")
    pdf.cell(0, 5.5, f"Emesso il {data_str}  —  Valido fino al {scad_str}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── BOX DATI CLIENTE ──────────────────────────────────────────────────────
    pdf.ln(6)
    box_y = pdf.get_y()
    box_h = 20

    # Sfondo grigio + bordo sinistro colorato (effetto accent)
    pdf.set_fill_color(*GRAY_BG)
    pdf.rect(14, box_y, 182, box_h, 'F')
    pdf.set_fill_color(*BLUE_MID)
    pdf.rect(14, box_y, 3, box_h, 'F')

    pdf.set_xy(20, box_y + 3.5)
    pdf.set_text_color(*GRAY_MUTED)
    pdf.set_font(FONT, "", 7.5)
    pdf.cell(0, 4, "SPETT.LE", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_x(20)
    pdf.set_text_color(*BLACK)
    pdf.set_font(FONT, "B", 10.5)
    pdf.cell(100, 5, d['Cliente'], new_x=XPos.RIGHT, new_y=YPos.TOP)

    # POD e indirizzo — colonna destra del box
    pdf.set_xy(122, box_y + 3.5)
    pdf.set_text_color(*GRAY_MUTED)
    pdf.set_font(FONT, "", 7.5)
    pdf.cell(0, 4, "POD", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(122)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.set_font(FONT, "", 9)
    pdf.cell(74, 4.5, d['POD'], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(122)
    pdf.set_font(FONT, "", 8)
    pdf.set_text_color(*GRAY_MUTED)
    pdf.cell(74, 4, d['Indirizzo'], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── TABELLA VOCI ──────────────────────────────────────────────────────────
    pdf.ln(9)
    pdf.set_draw_color(220, 225, 232)
    pdf.set_line_width(0.2)

    # Intestazione tabella
    pdf.set_fill_color(*BLUE_DARK)
    pdf.set_text_color(*WHITE)
    pdf.set_font(FONT, "B", 9)
    pdf.cell(134, 9, "  Descrizione prestazione", border=0, fill=True)
    pdf.cell(48,  9, "Importo", border=0, fill=True, align='R',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    voci = [
        ("Quota Tecnica",           d['C_Tec']),
        ("Oneri Amministrativi",    d['Oneri']),
        ("Oneri Gestione Pratica",  d['Gestione']),
    ]
    for i, (voce, importo) in enumerate(voci):
        bg = GRAY_BG if i % 2 == 0 else WHITE
        pdf.set_fill_color(*bg)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.set_font(FONT, "", 9.5)
        pdf.cell(134, 9, f"  {voce}", border='B', fill=True)
        pdf.cell(48,  9, f"{importo:.2f} EUR", border='B', fill=True, align='R',
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── SUBTOTALI ─────────────────────────────────────────────────────────────
    pdf.ln(2)
    pdf.set_font(FONT, "", 9)
    pdf.set_text_color(*GRAY_MUTED)
    for label, valore in [
        ("Totale imponibile", f"{d['Imponibile']:.2f} EUR"),
        (f"IVA ({d['IVA_Perc']}%)",    f"{d['IVA_Euro']:.2f} EUR"),
    ]:
        pdf.cell(134, 7, label, align='R')
        pdf.cell(48,  7, valore, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Riga totale finale — evidenziata
    pdf.ln(1)
    pdf.set_fill_color(*BLUE_LIGHT)
    pdf.set_text_color(*BLUE_DARK)
    pdf.set_font(FONT, "B", 11)
    pdf.cell(134, 12, "  Totale da corrispondere", fill=True)
    pdf.cell(48,  12, f"{d['Totale']:.2f} EUR", fill=True, align='R',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── SEZIONE PAGAMENTO ─────────────────────────────────────────────────────
    pdf.ln(10)
    # Piccola label categoria
    pdf.set_font(FONT, "B", 8)
    pdf.set_text_color(*BLUE_MID)
    pdf.cell(0, 5, "MODALITA' DI PAGAMENTO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    # Linea sottile separatrice
    pdf.set_draw_color(*BLUE_MID)
    pdf.set_line_width(0.4)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(3)

    pdf.set_text_color(*GRAY_TEXT)
    pdf.set_font(FONT, "", 9.5)
    pdf.cell(30, 5.5, "Bonifico bancario")
    pdf.set_font(FONT, "B", 9.5)
    pdf.cell(0, 5.5, f"IBAN: {d['IBAN']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font(FONT, "", 9)
    pdf.set_text_color(*GRAY_MUTED)
    pdf.cell(30, 5, "Causale:")
    pdf.set_text_color(*GRAY_TEXT)
    pdf.cell(0, 5, f"Accettazione Preventivo {d['Codice']} — {d.get('Cliente', '')}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── FIRMA ─────────────────────────────────────────────────────────────────
    pdf.ln(8)
    pdf.set_font(FONT, "", 8.5)
    pdf.set_text_color(*GRAY_MUTED)
    pdf.cell(96, 5, "Per accettazione (timbro e firma leggibile):", align='L')
    pdf.cell(86, 5, "Data:", align='L', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)
    pdf.set_draw_color(*GRAY_MUTED)
    pdf.set_line_width(0.3)
    pdf.line(14,  pdf.get_y(), 106, pdf.get_y())   # linea firma
    pdf.line(112, pdf.get_y(), 160, pdf.get_y())   # linea data

    # ── FOOTER ────────────────────────────────────────────────────────────────
    pdf.set_y(-28)
    # Banda blu piena
    pdf.set_fill_color(*BLUE_DARK)
    pdf.rect(0, pdf.get_y(), 210, 28, 'F')
    pdf.set_x(14)
    pdf.set_text_color(200, 220, 245)
    pdf.set_font(FONT, "", 6.5)
    pdf.set_line_width(0)
    note = (
        "L'esecuzione della prestazione e' subordinata a: conferma della proposta entro 30 gg e "
        "completamento di eventuali opere/autorizzazioni a cura del cliente.  "
        "Inviare il documento firmato a assistenza@polisenergia.it"
    )
    pdf.multi_cell(182, 4, note, align='L')

    return bytes(pdf.output())

# ==============================================================================
# 5b. GENERAZIONE HTML PREVENTIVO + UPLOAD GOOGLE DRIVE
# ==============================================================================
import base64 as _b64
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials as SACredentials

DRIVE_FOLDER_ID = st.secrets.get("DRIVE_FOLDER_ID", "")


def carica_html_su_drive(html: str, nome_file: str) -> str:
    """Carica l'HTML su Drive e restituisce il link /file/d/ID/view (nessun login richiesto)."""
    info   = dict(st.secrets["gcp_service_account"])
    creds  = SACredentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    svc    = build("drive", "v3", credentials=creds, cache_discovery=False)
    meta   = {"name": nome_file, "parents": [DRIVE_FOLDER_ID], "mimeType": "text/html"}
    media  = MediaIoBaseUpload(io.BytesIO(html.encode("utf-8")), mimetype="text/html", resumable=False)
    fid    = svc.files().create(body=meta, media_body=media, fields="id").execute().get("id")
    svc.permissions().create(fileId=fid, body={"type": "anyone", "role": "reader"}).execute()
    # /file/d/ID/view apre il visualizzatore Drive senza richiedere login
    return f"https://drive.google.com/file/d/{fid}/view"


def genera_html_polis(d: dict) -> str:
    """Genera il preventivo come HTML standalone con logo Base64 incorporato."""
    data_str = datetime.now().strftime("%d/%m/%Y")
    scad_str = (datetime.now() + timedelta(days=OTP_SCADENZA_GIORNI)).strftime("%d/%m/%Y")

    # Logo Base64 — nessuna dipendenza esterna
    logo_tag = '<div style="color:#fff;font-size:20px;font-weight:700;">PolisEnergia srl</div>'
    try:
        with open("logo_polis.png", "rb") as f:
            logo_b64 = _b64.b64encode(f.read()).decode("utf-8")
        logo_tag = (f'<img src="data:image/png;base64,{logo_b64}" '
                    f'style="height:40px;max-width:160px;object-fit:contain;" alt="PolisEnergia">')
    except Exception:
        pass

    voci = [
        ("Quota Tecnica",          d['C_Tec']),
        ("Oneri Amministrativi",   d['Oneri']),
        ("Oneri Gestione Pratica", d['Gestione']),
    ]
    righe_voci = ""
    for i, (voce, importo) in enumerate(voci):
        bg = "#f7f8fa" if i % 2 == 0 else "#ffffff"
        righe_voci += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e6ec;">{voce}</td>'
            f'<td style="padding:8px 12px;text-align:right;border-bottom:1px solid #e2e6ec;">'
            f'{importo:.2f} EUR</td></tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="it"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Preventivo {d['Codice']} — PolisEnergia</title>
<style>
  body{{margin:0;font-family:Helvetica,Arial,sans-serif;font-size:13px;color:#141414;background:#f0f2f5}}
  .page{{max-width:740px;margin:32px auto;background:#fff;box-shadow:0 2px 16px rgba(0,0,0,.10)}}
  .header{{background:#003366;padding:18px 24px;display:flex;justify-content:space-between;align-items:center}}
  .header-info{{text-align:right;color:#c8dcf5;font-size:11px;line-height:1.8}}
  .header-info strong{{color:#fff;display:block;font-size:12px;font-weight:700;margin-bottom:2px}}
  .accent{{height:3px;background:#005aaa}}
  .body{{padding:28px 24px}}
  .title{{font-size:22px;font-weight:700;margin:0 0 4px;color:#141414}}
  .subtitle{{color:#8c8c8c;font-size:11px;margin:0 0 20px}}
  .cliente-box{{background:#f7f8fa;border-left:3px solid #005aaa;padding:12px 16px;
                display:flex;justify-content:space-between;margin-bottom:24px;border-radius:2px}}
  .cliente-label{{font-size:9px;color:#8c8c8c;text-transform:uppercase;letter-spacing:.5px;margin-bottom:3px}}
  .cliente-name{{font-size:14px;font-weight:700;color:#141414}}
  .pod-val{{font-size:12px;font-weight:700;color:#003366}}
  .pod-addr{{font-size:11px;color:#8c8c8c;margin-top:2px}}
  table{{width:100%;border-collapse:collapse;font-size:12.5px}}
  thead td{{background:#003366;color:#fff;padding:9px 12px;font-weight:700}}
  .subtotal td{{padding:5px 12px;color:#8c8c8c;font-size:12px}}
  .total-row td{{background:#e6f0fa;color:#003366;font-weight:700;font-size:14px;padding:10px 12px}}
  .section-label{{font-size:9px;font-weight:700;color:#005aaa;letter-spacing:.8px;
                  text-transform:uppercase;margin:24px 0 4px}}
  .section-line{{border:none;border-top:1px solid #005aaa;margin:0 0 10px}}
  .pagamento-row{{display:flex;gap:8px;align-items:baseline;margin-bottom:4px;font-size:12px}}
  .pagamento-label{{color:#8c8c8c;min-width:90px}}
  .iban{{font-family:monospace;background:#f0f2f5;padding:2px 8px;border-radius:3px;font-size:11px}}
  .firma-area{{display:flex;gap:24px;margin-top:28px;align-items:flex-end}}
  .firma-col{{flex:1}}.firma-col.data{{max-width:130px}}
  .firma-label{{font-size:10px;color:#8c8c8c;margin-bottom:18px}}
  .firma-line{{border-top:1px solid #aaa;padding-top:4px;color:#ccc;font-size:10px}}
  .footer{{background:#003366;padding:10px 24px}}
  .footer p{{color:#c8dcf5;font-size:10px;margin:0;line-height:1.7}}
  @media print{{body{{background:#fff}}.page{{box-shadow:none;margin:0}}}}
</style></head><body>
<div class="page">
  <div class="header">
    {logo_tag}
    <div class="header-info">
      <strong>POLISENERGIA SRL</strong>
      Via Terre delle Risaie, 4 — 84131 Salerno (SA)<br>
      P.IVA 05050950657<br>
      assistenza@polisenergia.it · www.polisenergia.it
    </div>
  </div>
  <div class="accent"></div>
  <div class="body">
    <p class="title">Preventivo n. {d['Codice']}</p>
    <p class="subtitle">Emesso il {data_str} &nbsp;—&nbsp; Valido fino al {scad_str}</p>
    <div class="cliente-box">
      <div>
        <div class="cliente-label">Spett.le</div>
        <div class="cliente-name">{d['Cliente']}</div>
      </div>
      <div style="text-align:right">
        <div class="cliente-label">POD</div>
        <div class="pod-val">{d['POD']}</div>
        <div class="pod-addr">{d['Indirizzo']}</div>
      </div>
    </div>
    <table style="margin-bottom:4px">
      <thead><tr>
        <td style="width:76%">Descrizione prestazione</td>
        <td style="text-align:right">Importo</td>
      </tr></thead>
      <tbody>{righe_voci}</tbody>
    </table>
    <table style="margin-top:4px;margin-bottom:4px">
      <tbody>
        <tr class="subtotal">
          <td style="text-align:right;width:76%">Totale imponibile</td>
          <td style="text-align:right">{d['Imponibile']:.2f} EUR</td>
        </tr>
        <tr class="subtotal">
          <td style="text-align:right">IVA ({d['IVA_Perc']}%)</td>
          <td style="text-align:right">{d['IVA_Euro']:.2f} EUR</td>
        </tr>
        <tr class="total-row">
          <td>Totale da corrispondere</td>
          <td style="text-align:right">{d['Totale']:.2f} EUR</td>
        </tr>
      </tbody>
    </table>
    <p class="section-label">Modalità di pagamento</p>
    <hr class="section-line">
    <div class="pagamento-row">
      <span class="pagamento-label">Bonifico bancario</span>
      <span class="iban">{d['IBAN']}</span>
    </div>
    <div class="pagamento-row">
      <span class="pagamento-label">Causale:</span>
      <span>Accettazione Preventivo {d['Codice']} — {d['Cliente']}</span>
    </div>
    <div class="firma-area">
      <div class="firma-col">
        <div class="firma-label">Per accettazione (timbro e firma leggibile):</div>
        <div class="firma-line">___________________________________</div>
      </div>
      <div class="firma-col data">
        <div class="firma-label">Data:</div>
        <div class="firma-line">________________</div>
      </div>
    </div>
  </div>
  <div class="footer">
    <p>L'esecuzione della prestazione è subordinata a: conferma della proposta entro 30 gg e
    completamento di eventuali opere/autorizzazioni a cura del cliente finale.<br>
    Inviare il documento firmato a <strong style="color:#fff">assistenza@polisenergia.it</strong></p>
  </div>
</div></body></html>"""

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
    ["Autoletture", "Preventivo di Connessione", "📋 Archivio Preventivi",
     "📊 Statistiche", "⚙️ Impostazioni"]
)
st.sidebar.divider()
st.sidebar.caption(f"PolisEnergia Internal Tools v1.4 © {datetime.now().year}")

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

                            xml_str = ET.tostring(root, encoding='utf-8', xml_declaration=True)

                            # Mese/anno dalla data della prima lettura del gruppo (formato MMAAAA)
                            try:
                                data_prima = formatta_data_italiana(lista[0]['data'])  # GG/MM/AAAA
                                parti_d    = data_prima.split('/')
                                mmaaaa     = f"{parti_d[1]}{parti_d[2]}"              # MMAAAA
                            except Exception:
                                mmaaaa = datetime.now().strftime("%m%Y")

                            # Cartella = ragione sociale del distributore (safe per filesystem)
                            rag_soc_safe = re.sub(r'[\\/:*?"<>|]+', '_',
                                                   lista[0]['distr_nome'])[:40].strip()

                            # Nome file: TAL_0050_PIVA_MITTENTE_PIVA_DISTR_MMAAAA.xml
                            piva_mitt_clean = "".join(filter(str.isdigit, piva_mittente))
                            nome_file = f"TAL_0050_{piva_mitt_clean}_{piva_d}_{mmaaaa}.xml"

                            # Path dentro lo ZIP: RAGIONE_SOCIALE/nome_file.xml
                            zip_file.writestr(f"{rag_soc_safe}/{nome_file}", xml_str)
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

    no_lim_attuale   = False
    richiesta_no_lim = False

    if "Potenza" in pratica or "Subentro" in pratica:
        col1, col2 = st.columns(2)
        if tipo_ut == "Altri Usi":
            t_partenza   = col1.selectbox("Tensione", ["BT", "MT"], key="t")
            if t_partenza == "BT":
                passaggio_mt = col1.checkbox("Passaggio a MT?", key="mt")
        p_att = col1.number_input("kW Attuali (Contrattuali)",   value=0.0, key="pa")
        p_new = col2.number_input("kW Richiesti (Contrattuali)", value=0.0, key="pn")

        # --- LOGICA FRANCHIGIA INVERTITA ---
        if tipo_ut == "Altri Usi" and p_new <= 30:
            st.info("⚙️ Gestione Limitatore (Franchigia 10%)")
            cx1, cx2 = st.columns(2)
            no_lim_attuale   = cx1.checkbox(
                "Stato Attuale: POD SENZA limitatore", value=False,
                help="Spunta se il cliente ha già il prelievo libero (senza +10%)"
            )
            richiesta_no_lim = cx2.checkbox(
                "Nuova Config: Rimuovere Limitatore", value=False,
                help="Spunta per richiedere potenza a prelievo libero (senza franchigia)"
            )

    elif "Nuova" in pratica:
        p_new  = st.number_input("kW Richiesti",    value=0.0, key="pnc")
        c_dist = st.number_input("Quota Distanza €", 0.0,      key="dist")
        if tipo_ut == "Altri Usi" and p_new <= 30:
            richiesta_no_lim = st.checkbox(
                "Richiedere potenza a prelievo LIBERO (senza franchigia)", value=False
            )

    elif "Spostamento" in pratica:
        s_dist = st.radio("Distanza", ["Entro 10 metri", "Oltre 10 metri"], key="sd")
        c_dist = (SPOSTAMENTO_10MT if "Entro" in s_dist
                  else st.number_input("Costo Rilievo €", 0.0, key="sdc"))

    # Calcolo delta e tariffa
    if p_new > 0:
        # Nuova potenza: +10% se Domestico o se Altri Usi non ha chiesto rimozione limitatore
        if p_new <= 30 and (tipo_ut == "Domestico" or not richiesta_no_lim):
            v_new = round(p_new * 1.1, 1)
        else:
            v_new = p_new

        # Potenza attuale: +10% se Domestico o se Altri Usi ha ancora il limitatore
        if p_att > 0:
            if tipo_ut == "Domestico" or not no_lim_attuale:
                v_att = round(p_att * 1.1, 1)
            else:
                v_att = p_att
        else:
            v_att = 0.0

        delta = max(round(v_new - v_att, 1), 0.0)

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

                # --- Controllo duplicati POD ---
                try:
                    conn_check = st.connection("gsheets", type=GSheetsConnection)
                    df_check   = conn_check.read(ttl=0)
                    if not df_check.empty and "POD" in df_check.columns:
                        attivi = df_check[
                            (df_check["POD"].astype(str).str.strip() == pod.strip()) &
                            (df_check["Stato"].astype(str).str.strip().isin(["Inviato", "INVIATO"]))
                        ]
                        if not attivi.empty:
                            cod_esistente = attivi.iloc[-1]["Codice"]
                            st.warning(
                                f"⚠️ Esiste già un preventivo attivo per il POD **{pod}** "
                                f"(codice: `{cod_esistente}`). "
                                f"Il nuovo sarà archiviato come revisione."
                            )
                            # Storico versioni: il nuovo codice porta il riferimento al precedente
                            cod_padre = str(cod_esistente).strip()
                        else:
                            cod_padre = ""
                    else:
                        cod_padre = ""
                except Exception:
                    cod_padre = ""

                dati_preventivo = {
                    "Codice": cod, "Cliente": nome, "POD": pod, "Indirizzo": indirizzo,
                    "C_Tec": c_tec, "Oneri": ONERI_ISTRUTTORIA, "Gestione": c_gest,
                    "Imponibile": imp, "IVA_Perc": iva_p, "IVA_Euro": iva_e,
                    "Totale": totale, "IBAN": IBAN_LABEL,
                }
                st.session_state.pdf_bytes = genera_pdf_polis(dati_preventivo)
                html_preventivo            = genera_html_polis(dati_preventivo)

                # Caricamento HTML su Drive
                link_html = ""
                try:
                    with st.spinner("Archiviazione su Drive..."):
                        link_html = carica_html_su_drive(
                            html_preventivo,
                            f"Preventivo_{cod}_{nome[:20]}.html"
                        )
                except Exception as e:
                    st.warning(f"PDF generato, ma errore upload Drive: {e}")

                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    df   = conn.read(ttl=0)
                    nuova_riga = pd.DataFrame([{
                        "Data":      datetime.now().strftime("%d/%m/%Y"),
                        "Codice":    str(cod),
                        "Versione_Di": cod_padre,       # riferimento al preventivo sostituito
                        "Cliente":   nome,
                        "POD":       pod,
                        "Totale":    totale,
                        "Stato":     "Inviato",
                        "Email":     email_dest,        # salviamo l'email per il reinvio
                        "Link_HTML": link_html,
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
            st.session_state.current_otp = genera_otp()

        otp  = st.session_state.current_otp
        cod  = st.session_state.current_cod
        link = f"{APP_URL}/?codice={cod}&otp={otp}"

        # Template da impostazioni (con fallback al default)
        template = st.session_state.get("email_template",
            "Spett.le {nome},\n"
            "in allegato il preventivo n. {codice}.\n\n"
            "Per firmare digitalmente clicca qui: {link}\n"
            "OTP: {otp}\n\n"
            "Il link è valido per {giorni} giorni.\n\n"
            "Cordiali saluti,\nPolisEnergia srl"
        )
        testo_default = template.format(
            nome=nome, codice=cod, link=link,
            otp=otp, giorni=OTP_SCADENZA_GIORNI,
            totale=f"{totale:.2f}", pod=pod,
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

        # Stato effettivo con scadenza
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

        # ── FILTRI ────────────────────────────────────────────────────────────
        col_f1, col_f2 = st.columns([2, 1])
        filtro_testo = col_f1.text_input("🔍 Cerca per cliente, codice o POD", "")
        filtro_stato = col_f2.selectbox("Stato", ["Tutti", "INVIATO", "ACCETTATO", "SCADUTO"])

        df_view = df.copy()
        if filtro_testo:
            mask = (
                df_view["Cliente"].astype(str).str.contains(filtro_testo, case=False, na=False) |
                df_view["Codice"].astype(str).str.contains(filtro_testo, case=False, na=False)  |
                df_view["POD"].astype(str).str.contains(filtro_testo, case=False, na=False)
            )
            df_view = df_view[mask]
        if filtro_stato != "Tutti":
            df_view = df_view[df_view["Stato Reale"] == filtro_stato]

        # ── TABELLA ───────────────────────────────────────────────────────────
        cols_show = [c for c in ["Data", "Codice", "Versione_Di", "Cliente", "POD",
                                  "Totale", "Stato Reale", "Data Firma"]
                     if c in df_view.columns]
        df_show = df_view[cols_show].copy()

        EMOJI_STATO = {"ACCETTATO": "🟢 ACCETTATO", "SCADUTO": "🔴 SCADUTO", "INVIATO": "🟡 INVIATO"}
        if "Stato Reale" in df_show.columns:
            df_show["Stato Reale"] = df_show["Stato Reale"].map(
                lambda v: EMOJI_STATO.get(str(v).strip(), str(v))
            )

        # Link_HTML: presente solo se la colonna esiste e la cella non è vuota
        ha_link = "Link_HTML" in df_view.columns

        # Colonna PDF separata — contiene il link Drive solo dove disponibile
        if ha_link:
            links = df_view["Link_HTML"].fillna("").astype(str)
            # Valore per la colonna PDF: link Drive se esiste, stringa vuota altrimenti
            df_show["PDF"] = links.where(links.str.startswith("http"), "").values

        col_cfg = {
            "Data":        st.column_config.TextColumn("Data",        width="small"),
            "Codice":      st.column_config.TextColumn("Codice",      width="medium"),
            "Versione_Di": st.column_config.TextColumn("Revisione di",width="medium"),
            "Cliente":     st.column_config.TextColumn("Cliente",     width="large"),
            "POD":         st.column_config.TextColumn("POD",         width="medium"),
            "Totale":      st.column_config.NumberColumn("Totale €",  format="%.2f", width="small"),
            "Stato Reale": st.column_config.TextColumn("Stato",       width="medium"),
            "Data Firma":  st.column_config.TextColumn("Firmato il",  width="small"),
        }

        if ha_link:
            col_cfg["PDF"] = st.column_config.LinkColumn(
                "Preventivo",
                display_text="📄 Apri",
                help="Clicca per aprire il preventivo HTML su Drive",
                width="small",
            )

        st.dataframe(df_show, use_container_width=True, hide_index=True, column_config=col_cfg)

        # ── EXPORT EXCEL ──────────────────────────────────────────────────────
        buf_xls = io.BytesIO()
        export_cols = [c for c in ["Data", "Codice", "Versione_Di", "Cliente", "POD",
                                    "Totale", "Stato Reale", "Email", "Data Firma"]
                       if c in df_view.columns]
        df_view[export_cols].to_excel(buf_xls, index=False, engine="openpyxl")
        buf_xls.seek(0)
        st.download_button(
            label="📊 Esporta in Excel",
            data=buf_xls,
            file_name=f"Archivio_Preventivi_{datetime.now().strftime('%d%m%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        # ── METRICHE ──────────────────────────────────────────────────────────
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🟡 Inviati",   len(df[df["Stato Reale"] == "INVIATO"]))
        c2.metric("🟢 Accettati", len(df[df["Stato Reale"] == "ACCETTATO"]))
        c3.metric("🔴 Scaduti",   len(df[df["Stato Reale"] == "SCADUTO"]))
        try:
            c4.metric("💶 Valore accettato",
                      f"{df[df['Stato Reale'] == 'ACCETTATO']['Totale'].astype(float).sum():.2f} €")
        except Exception:
            pass

        # ── REINVIO EMAIL / NUOVO OTP ─────────────────────────────────────────
        st.divider()
        st.subheader("📨 Reinvia email a cliente")

        reinviabili = df_view[
            df_view["Stato Reale"].isin(["INVIATO", "SCADUTO"])
        ]["Codice"].astype(str).tolist()

        if not reinviabili:
            st.info("Nessun preventivo da reinviare nei risultati correnti.")
        else:
            cod_reinvio = st.selectbox("Seleziona preventivo:", reinviabili, key="sel_reinvio")
            row_r = df[df["Codice"].astype(str) == cod_reinvio]

            if not row_r.empty:
                r = row_r.iloc[0]
                nome_r  = str(r.get("Cliente", ""))
                email_r = str(r.get("Email", ""))
                pod_r   = str(r.get("POD", ""))

                col_r1, col_r2 = st.columns(2)
                email_reinvio = col_r1.text_input(
                    "Email destinatario",
                    value=email_r if email_r not in {"", "nan"} else "",
                    key="email_reinvio"
                )

                # Genera nuovo OTP per questo reinvio
                otp_key = f"otp_reinvio_{cod_reinvio}"
                if otp_key not in st.session_state:
                    st.session_state[otp_key] = genera_otp()
                nuovo_otp  = st.session_state[otp_key]
                link_reinvio = f"{APP_URL}/?codice={cod_reinvio}&otp={nuovo_otp}"

                template = st.session_state.get("email_template",
                    "Spett.le {nome},\n"
                    "in allegato il preventivo n. {codice}.\n\n"
                    "Per firmare digitalmente clicca qui: {link}\n"
                    "OTP: {otp}\n\n"
                    "Il link è valido per {giorni} giorni.\n\n"
                    "Cordiali saluti,\nPolisEnergia srl"
                )
                try:
                    testo_r = template.format(
                        nome=nome_r, codice=cod_reinvio, link=link_reinvio,
                        otp=nuovo_otp, giorni=OTP_SCADENZA_GIORNI,
                        totale=str(r.get("Totale", "")), pod=pod_r,
                    )
                except Exception:
                    testo_r = (
                        f"Spett.le {nome_r},\nin allegato il preventivo n. {cod_reinvio}.\n\n"
                        f"Firma qui: {link_reinvio}\nOTP: {nuovo_otp}\n\n"
                        f"Cordiali saluti,\nPolisEnergia srl"
                    )
                corpo_r = st.text_area("Testo email:", value=testo_r, height=160, key="corpo_reinvio")

                if col_r2.button("🚀 REINVIA EMAIL", use_container_width=True, key="btn_reinvio"):
                    if not email_reinvio.strip():
                        st.error("Inserisci l'indirizzo email.")
                    else:
                        try:
                            with st.spinner("Invio in corso..."):
                                smtp = get_smtp_config()
                                invia_email(
                                    smtp=smtp,
                                    to=email_reinvio.strip(),
                                    subject=f"Preventivo PolisEnergia n. {cod_reinvio}",
                                    body=corpo_r,
                                )
                            # Aggiorna OTP nel Sheet
                            idx_r = df[df["Codice"].astype(str) == cod_reinvio].index[0]
                            df.at[idx_r, "Stato"] = "Inviato"
                            if "Email" in df.columns:
                                df.at[idx_r, "Email"] = email_reinvio.strip()
                            conn.update(data=df.drop(columns=["Stato Reale"], errors="ignore"))
                            # Reset OTP in session per forzare nuovo codice al prossimo reinvio
                            del st.session_state[otp_key]
                            st.success(f"✅ Email reinviata con nuovo OTP a {email_reinvio}!")
                        except Exception as e:
                            st.error(f"Errore invio: {e}")

        # ── STORICO VERSIONI ──────────────────────────────────────────────────
        if "Versione_Di" in df.columns and df["Versione_Di"].notna().any():
            st.divider()
            st.subheader("🔄 Storico revisioni")
            pod_con_rev = df[df["Versione_Di"].astype(str).str.strip() != ""]["POD"].unique()
            if len(pod_con_rev):
                pod_sel = st.selectbox("POD:", pod_con_rev, key="pod_storico")
                catena = df[df["POD"].astype(str) == pod_sel][
                    ["Data", "Codice", "Versione_Di", "Totale", "Stato Reale"]
                ].sort_values("Data")
                st.dataframe(catena, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error("Impossibile caricare l'archivio.")
        st.caption(f"Dettaglio tecnico: {e}")

# ==============================================================================
# 12. SEZIONE: STATISTICHE
# ==============================================================================
elif scelta == "📊 Statistiche":
    st.title("📊 Statistiche")
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df   = conn.read(ttl=0)

        if df.empty:
            st.info("Nessun dato disponibile.")
            st.stop()

        oggi = datetime.now()
        def stato_eff(row):
            if str(row.get("Stato", "")).strip() == "ACCETTATO":
                return "ACCETTATO"
            try:
                data_c = datetime.strptime(str(row["Data"]).strip(), "%d/%m/%Y")
                if oggi > data_c + timedelta(days=OTP_SCADENZA_GIORNI):
                    return "SCADUTO"
            except Exception:
                pass
            return "INVIATO"

        df["Stato Reale"] = df.apply(stato_eff, axis=1)
        df["Totale_N"] = pd.to_numeric(df["Totale"], errors="coerce").fillna(0)

        # Prova a estrarre mese/anno dalla colonna Data
        try:
            df["_Data"] = pd.to_datetime(df["Data"], format="%d/%m/%Y", errors="coerce")
            df["Mese"]  = df["_Data"].dt.to_period("M").astype(str)
        except Exception:
            df["Mese"] = "N/D"

        # ── KPI ───────────────────────────────────────────────────────────────
        k1, k2, k3, k4 = st.columns(4)
        n_tot  = len(df)
        n_acc  = len(df[df["Stato Reale"] == "ACCETTATO"])
        val_acc = df[df["Stato Reale"] == "ACCETTATO"]["Totale_N"].sum()
        tasso   = round(n_acc / n_tot * 100, 1) if n_tot else 0
        k1.metric("Preventivi totali", n_tot)
        k2.metric("Accettati",         n_acc)
        k3.metric("Tasso accettazione", f"{tasso}%")
        k4.metric("Valore accettato",  f"{val_acc:.2f} €")

        st.divider()

        # ── GRAFICI ───────────────────────────────────────────────────────────
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.subheader("Preventivi per mese")
            mese_grp = (df.groupby("Mese")
                          .size()
                          .reset_index(name="Conteggio")
                          .sort_values("Mese"))
            st.bar_chart(mese_grp.set_index("Mese")["Conteggio"])

        with col_g2:
            st.subheader("Valore accettato per mese (€)")
            val_grp = (df[df["Stato Reale"] == "ACCETTATO"]
                         .groupby("Mese")["Totale_N"]
                         .sum()
                         .reset_index(name="Valore")
                         .sort_values("Mese"))
            if not val_grp.empty:
                st.bar_chart(val_grp.set_index("Mese")["Valore"])
            else:
                st.info("Nessun preventivo accettato.")

        st.divider()
        st.subheader("Distribuzione stati")
        stato_grp = df["Stato Reale"].value_counts().reset_index()
        stato_grp.columns = ["Stato", "Conteggio"]
        st.bar_chart(stato_grp.set_index("Stato")["Conteggio"])

    except Exception as e:
        st.error("Impossibile caricare le statistiche.")
        st.caption(f"Dettaglio tecnico: {e}")

# ==============================================================================
# 13. SEZIONE: IMPOSTAZIONI (template email)
# ==============================================================================
elif scelta == "⚙️ Impostazioni":
    st.title("⚙️ Impostazioni")

    st.subheader("📝 Template Email")
    st.markdown(
        "Personalizza il testo della mail inviata ai clienti. "
        "Usa le variabili tra `{` `}` per inserire i dati dinamici:"
    )
    st.code(
        "{nome}  →  Ragione Sociale cliente\n"
        "{codice}  →  Numero preventivo\n"
        "{link}  →  Link di firma\n"
        "{otp}  →  Codice OTP\n"
        "{giorni}  →  Giorni di validità\n"
        "{totale}  →  Importo totale\n"
        "{pod}  →  Codice POD",
        language=None
    )

    default_template = (
        "Spett.le {nome},\n"
        "in allegato il preventivo n. {codice}.\n\n"
        "Per firmare digitalmente clicca qui: {link}\n"
        "OTP: {otp}\n\n"
        "Il link è valido per {giorni} giorni.\n\n"
        "Cordiali saluti,\nPolisEnergia srl"
    )
    template_attuale = st.session_state.get("email_template", default_template)
    nuovo_template   = st.text_area(
        "Template email:",
        value=template_attuale,
        height=220,
        key="input_template"
    )

    col_s1, col_s2 = st.columns(2)
    if col_s1.button("💾 Salva template", use_container_width=True):
        # Verifica che le variabili obbligatorie siano presenti
        mancanti = [v for v in ["{nome}", "{codice}", "{link}", "{otp}"]
                    if v not in nuovo_template]
        if mancanti:
            st.error(f"⚠️ Il template deve contenere: {', '.join(mancanti)}")
        else:
            st.session_state["email_template"] = nuovo_template
            st.success("✅ Template salvato per questa sessione!")
            st.info("ℹ️ Il template viene salvato in sessione — verrà reimpostato al riavvio dell'app.")

    if col_s2.button("↩️ Ripristina default", use_container_width=True):
        st.session_state["email_template"] = default_template
        st.success("Template ripristinato.")
        st.rerun()

    # Anteprima con dati fittizi
    st.divider()
    st.subheader("👁 Anteprima")
    try:
        anteprima = nuovo_template.format(
            nome="ROSSI MARIO SRL",
            codice="260403143022",
            link=f"{APP_URL}/?codice=260403143022&otp=123456",
            otp="123456",
            giorni=OTP_SCADENZA_GIORNI,
            totale="414.40",
            pod="IT001E12345678",
        )
        st.text(anteprima)
    except KeyError as e:
        st.warning(f"Variabile non riconosciuta nel template: {e}")
