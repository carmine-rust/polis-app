import streamlit as st
import math
import random
import string
from fpdf import FPDF
from datetime import datetime

# 1. Configurazione Pagina
st.set_page_config(page_title="PolisEnergia Suite", page_icon="⚡", layout="wide")

# 2. Costanti TIC 2026 e Generatore Causale
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "PASS_BT_MT": 494.83, "DIST_FISSA": 209.62, 
    "DIST_EXTRA": 105.08, "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 452.72, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88
}

if 'codice_causale' not in st.session_state:
    st.session_state.codice_causale = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# --- INTERFACCIA UTENTE ---
st.title("⚡ POLIS ENERGIA")
st.caption("Configuratore Professionale Preventivi Connessione")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Dati Intestatario")
    nome = st.text_input("Ragione Sociale / Nome Cognome").upper()
    indirizzo = st.text_input("Indirizzo Completo (Via, Civico, CAP, Città)")
    uso = st.selectbox("Regime Fiscale / IVA", ["IVA 10% (Domestico)", "IVA 22% (Business)", "P.A. (Split Payment)", "Esente"])
    pod = st.text_input("Codice POD (se presente)").upper()

with col2:
    st.subheader("Parametri Tecnici")
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    tipo_utenza = st.radio("Tipologia Utenza", ["Domestico", "Altri Usi"], horizontal=True)
    
    c_p1, c_p2 = st.columns(2)
    p_att = c_p1.number_input("Potenza Attuale (kW)", min_value=0.0, value=3.0) if "Nuova" not in pratica else 0.0
    p_new = c_p2.number_input("Nuova Potenza (kW)", min_value=0.1, value=6.0)
    
    t_new = st.selectbox("Tensione Richiesta", ["BT", "MT"] if tipo_utenza == "Altri Usi" else ["BT"])
    applica_gestione = st.checkbox("Applica Oneri Gestione Polis (10%)", value=True)

# --- LOGICA DI CALCOLO ---
f_new = 1.1 if (t_new == "BT" and p_new <= 30) else 1.0
f_att = 1.1 if ("Nuova" not in pratica and p_att <= 30) else 1.0

# Prezzo unitario TIC
px = TIC_2026["MT"] if t_new == "MT" else (TIC_2026["DOM_LE6"] if (tipo_utenza == "Domestico" and p_new <= 6) else TIC_2026["BT_ALTRI"])

# Calcolo quota tecnica
if "Spostamento" in pratica:
    c_tec = TIC_2026["SPOST_ENTRO_10"] # Default entro 10m
else:
    c_tec = max(0.0, (p_new * f_new) - (p_att * f_att)) * px

c_gest = (c_tec + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if applica_gestione else 0.0
tot_sogg_iva = c_tec + c_gest + TIC_2026["ISTRUTTORIA"]

# Bollo € 2,00 solo se ESENTE e > 77,47
bollo_2 = 2.0 if (uso == "Esente" and tot_sogg_iva > 77.47) else 0.0

is_split = "P.A." in uso
aliq = 0.10 if "10%" in uso else (0.22 if ("22%" in uso or is_split) else 0.0)
tot_iva = tot_sogg_iva * aliq
tot_finale = (tot_sogg_iva if is_split else tot_sogg_iva + tot_iva) + bollo_2

# --- FUNZIONE GENERAZIONE PDF ---
def genera_pdf():
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Header con Fascia Blu
    pdf.set_fill_color(0, 29, 61) 
    pdf.rect(0, 0, 210, 45, 'F')
    
    # Inserimento Logo (Assicurati che logo_polis.png sia su GitHub)
    try:
        pdf.image("logo_polis.png", x=10, y=10, w=45)
    except:
        pass # Se il logo manca, non scrive testo (come richiesto)

    # Ufficio Tecnico subito sotto il logo
    pdf.set_xy(10, 32)
    pdf.set_font("Helvetica", "I", 9); pdf.set_text_color(200, 200, 200)
    pdf.cell(0, 10, "Ufficio Tecnico Connessioni")

    # Dati Societari a destra
    pdf.set_xy(120, 12); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(80, 5, "POLIS ENERGIA SRL", ln=True, align='R')
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(80, 4, "Sede Operativa: Ufficio Tecnico", ln=True, align='R')
    pdf.cell(80, 4, "www.polisenergia.it", ln=True, align='R')
    
    # 2. Destinatario
    pdf.set_xy(10, 55); pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, "Spett.le Cliente:", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, f"{nome}", ln=True)
    pdf.cell(0, 6, f"{indirizzo}", ln=True)
    
    # 3. Oggetto Preventivo
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 12)
    testo_oggetto = f"PREVENTIVO PER {pratica.upper()}"
    if pod: testo_oggetto += f" - POD: {pod}"
    pdf.cell(0, 10, testo_oggetto, border="B", ln=True)
    
    # 4. Tabella Costi
    pdf.ln(5)
    pdf.set_fill_color(0, 180, 216); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(145, 10, " DESCRIZIONE PRESTAZIONE", 1, 0, 'L', True)
    pdf.cell(45, 10, " IMPORTO", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 10)
    pdf.cell(145, 9, f" Quota Tecnica TIC e Oneri (Potenza {p_new*f_new:.2f} kW disp.)", 1)
    pdf.cell(45, 9, f"{c_tec + TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    
    if applica_gestione:
        pdf.cell(145, 9, " Oneri di Gestione PolisEnergia (10%)", 1)
        pdf.cell(45, 9, f"{c_gest:.2f} EUR", 1, 1, 'R')
    
    if bollo_2 > 0:
        pdf.cell(145, 9, " Imposta di Bollo (Importo Esente)", 1)
        pdf.cell(45, 9, "2.00 EUR", 1, 1, 'R')
    
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(145, 9, f" IVA ({int(aliq*100)}%)", 1)
    pdf.cell(45, 9, f"{tot_iva:.2f} EUR", 1, 1, 'R')
    
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Helvetica", "B", 11)
    pdf.cell(145, 11, " TOTALE DOVUTO", 1, 0, 'L', True)
    pdf.cell(45, 11, f"{tot_finale:.2f} EUR", 1, 1, 'R', True)
    
    # 5. Didascalia e Condizioni
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, "L'esecuzione della prestazione e' pertanto subordinata al verificarsi delle seguenti condizioni:", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, "- Conferma della proposta pervenuta entro 30 gg dalla presente richiesta;")
    pdf.multi_cell(0, 5, "- In caso di consegna della specifica tecnica, comunicazione dell'avvenuto completamento delle eventuali opere e/o concessioni, autorizzazioni, servitu' a cura del cliente finale;")
    
    # IBAN e Causale
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(0, 5, f"- Pagamento del preventivo da effettuarsi tramite bonifico bancario sul conto corrente intestato a PolisEnergia s.r.l. - IT80P0103015200000007044056 - Monte dei Paschi di Siena utilizzando come causale il codice: {st.session_state.codice_causale}")
    
    # 6. Area Firme
    pdf.ln(15)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(95, 5, "Per PolisEnergia s.r.l. (Timbro e Firma)", ln=0)
    pdf.cell(95, 5, "Per Accettazione Cliente (Firma Legale Rapp.)", ln=1, align='R')
    
    pdf.ln(12)
    pdf.line(10, pdf.get_y(), 70, pdf.get_y()) # Linea firma 1
    pdf.line(140, pdf.get_y(), 200, pdf.get_y()) # Linea firma 2
    
    return pdf.output()

# --- AZIONE FINALE ---
st.divider()
if st.button("🚀 GENERA PREVENTIVO PDF UFFICIALE"):
    if nome and indirizzo:
        try:
            pdf_bytes = genera_pdf()
            st.download_button(
                label="📥 Scarica Preventivo",
                data=bytes(pdf_bytes),
                file_name=f"Preventivo_Polis_{st.session_state.codice_causale}.pdf",
                mime="application/pdf"
            )
            st.success(f"Preventivo generato! Codice Causale: {st.session_state.codice_causale}")
        except Exception as e:
            st.error(f"Errore tecnico: {e}")
    else:
        st.warning("⚠️ Compila i campi 'Ragione Sociale' e 'Indirizzo' per generare il PDF.")
