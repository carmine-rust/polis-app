import streamlit as st
import math
import random
import string
import re
from fpdf import FPDF

# 1. Configurazione Pagina
st.set_page_config(page_title="PolisEnergia Preventivatore 4.0", page_icon="⚡", layout="wide")

# --- INIZIALIZZAZIONE ---
if 'codice_causale' not in st.session_state:
    st.session_state.codice_causale = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def clean_filename(text):
    if not text: return "CLIENTE"
    text = re.sub(r'[^\w\s-]', '', text).strip()
    return re.sub(r'[-\s]+', '_', text).upper()

def reset_campi():
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()

# --- COSTANTI TIC 2026 ---
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "SPOST_ENTRO_10": 226.36, "SPOST_OLTRE_10": 226.36, 
    "ISTRUTTORIA": 27.42, "FISSO_BASE_CALCOLO": 25.88
}

# --- FUNZIONE PDF (CON DIVISIONE VOCI) ---
def genera_pdf(d):
    pdf = FPDF()
    pdf.add_page()
    # Header Aziendale
    pdf.set_fill_color(0, 29, 61); pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_xy(120, 12); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(80, 5, "PolisEnergia srl", align='R', ln=1)
    pdf.set_font("Helvetica", "", 8); pdf.cell(80, 4, "Sede Legale: Via Terre delle Risaie, 4 Salerno", align='R', ln=1)
    pdf.cell(80, 4, "P.IVA: 0505950657 | www.polisenergia.it", align='R', ln=1)
    
    # Dati Cliente
    pdf.set_xy(10, 55); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"SPETT.LE: {d['nome']}", ln=1)
    pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, f"INDIRIZZO: {d['indirizzo']}", ln=1)
    pdf.ln(10); pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"PREVENTIVO {d['pratica'].upper()} - POD: {d['pod']}", border="B", ln=1)
    
    # Tabella Voci
    pdf.ln(5); pdf.set_fill_color(0, 180, 216); pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, " DESCRIZIONE PRESTAZIONE", 1, 0, 'L', True); pdf.cell(50, 10, " IMPORTO", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 8, " ONERI DISTRIBUTORE (Costi Vivi)", 1, 1, 'L', True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 8, " Quota Potenza / Tecnica TIC", 1); pdf.cell(50, 8, f"{d['c_tec']:.2f} EUR", 1, 1, 'R')
    if d['c_dist'] > 0:
        pdf.cell(140, 8, " Quota Distanza", 1); pdf.cell(50, 8, f"{d['c_dist']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Istruttoria Pratica", 1); pdf.cell(50, 8, f"{TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 8, " ONERI PROFESSIONALI POLIS ENERGIA", 1, 1, 'L', True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 8, " Oneri Gestione Pratica", 1); pdf.cell(50, 8, f"{d['c_gest']:.2f} EUR", 1, 1, 'R')
    
    # Totali
    pdf.ln(2); pdf.set_font("Helvetica", "B", 10); pdf.cell(140, 9, f" IMPONIBILE", 1); pdf.cell(50, 9, f"{d['imponibile']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, f" IVA ({d['iva_perc']}%)", 1); pdf.cell(50, 9, f"{d['iva_euro']:.2f} EUR", 1, 1, 'R')
    if d['bollo'] > 0:
        pdf.cell(140, 9, "BOLLO", 1); pdf.cell(50, 9, "2.00 EUR", 1, 1, 'R')
    
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Helvetica", "B", 11)
    pdf.cell(140, 11, " TOTALE DOVUTO", 1, 0, 'L', True); pdf.cell(50, 11, f"{d['totale']:.2f} EUR", 1, 1, 'R', True)
    
    # Footer
    pdf.ln(10); pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(190, 4, f"Validità preventivo: 30gg. Il pagamento deve essere effettuato tramite bonifico bancario.\nCausale obbligatoria: {st.session_state.codice_causale}\nIBAN: IT80P0103015200000007044056 - MPS")
    return pdf.output()

# --- INTERFACCIA ---
col_t1, col_t2 = st.columns([4, 1])
with col_t1:
    st.title("⚡ POLIS ENERGIA")
    st.caption(f"Configuratore Professionale v73.2 | Codice Preventivo: {st.session_state.codice_causale}")
with col_t2:
    if st.button("🔴 RESET", use_container_width=True):
        reset_campi()

st.divider()

with st.form("main_form"):
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Anagrafica")
        nome = st.text_input("Ragione Sociale", key="nome_form").upper()
        indirizzo = st.text_input("Indirizzo", key="ind_form")
        uso = st.selectbox("Regime Fiscale", ["IVA 10%", "IVA 22%", "P.A.", "Esente"], key="iva_form")
        pod = st.text_input("POD", key="pod_form").upper()

    with c2:
        st.subheader("Dettaglio Tecnico")
        pratica = st.selectbox("Pratica", ["Nuova Connessione", "Aumento Potenza", "Subentro", "Spostamento"], key="prat_form")
        tipo_ut = st.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True, key="ut_form")
        
        c_tec, c_dist = 0.0, 0.0
        if "Spostamento" in pratica:
            tipo_spost = st.radio("Distanza", ["Entro 10m", "Oltre 10m"], horizontal=True)
            c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in tipo_spost else TIC_2026["SPOST_OLTRE_10"]
            if "Oltre" in tipo_spost:
                c_dist = st.number_input("Quota Distanza Distributore (€)", value=0.0)
        else:
            p_att = st.number_input("Potenza Attuale (kW)", value=3.0) if "Nuova" not in pratica else 0.0
            p_new = st.number_input("Nuova Potenza (kW)", value=6.0)
            px = TIC_2026["DOM_LE6"] if (tipo_ut == "Domestico" and p_new <= 6) else TIC_2026["BT_ALTRI"]
            c_tec = max(0.0, (p_new * 1.1) - (p_att * 1.1)) * px
            if "Nuova" in pratica:
                c_dist = st.number_input("Quota Distanza Distributore (€)", value=0.0)

        applica_gest = st.checkbox("Applica Gestione Polis (10%)", value=True)
    
    conferma = st.form_submit_button("📁 CONFERMA E CALCOLA")

# --- CALCOLI FINALI ---
if conferma:
    if nome and indirizzo:
        c_gest = (c_tec + c_dist + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if applica_gest else 0.0
        imponibile = c_tec + c_dist + c_gest + TIC_2026["ISTRUTTORIA"]
        iva_p = 10 if "10" in uso else (22 if ("22" in uso or "P.A." in uso) else 0)
        iva_e = imponibile * (iva_p/100)
        bollo = 2.0 if (uso == "Esente" and imponibile > 77) else 0.0
        totale = (imponibile if "P.A." in uso else imponibile + iva_e) + bollo

        dati = {
            'nome': nome, 'indirizzo': indirizzo, 'pod': pod if pod else "N.D.",
            'pratica': pratica, 'c_tec': c_tec, 'c_dist': c_dist, 'c_gest': c_gest,
            'imponibile': imponibile, 'iva_perc': iva_p, 'iva_euro': iva_e, 
            'bollo': bollo, 'totale': totale
        }
        
        st.success(f"Dati acquisiti! Totale Ivato: {totale:.2f} €")
        
        pdf_out = genera_pdf(dati)
        filename = f"Preventivo_{pratica.replace(' ','')}_{clean_filename(nome)}_{st.session_state.codice_causale}.pdf"
        
        st.download_button("📥 SCARICA PREVENTIVO PDF", data=bytes(pdf_out), file_name=filename, use_container_width=True)
    else:
        st.error("⚠️ Compila i campi obbligatori (Nome e Indirizzo) prima di calcolare.")
