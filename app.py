import streamlit as st
import math
import random
import string
import re
from fpdf import FPDF

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="PolisEnergia Suite", page_icon="⚡", layout="wide")

if 'codice_causale' not in st.session_state:
    st.session_state.codice_causale = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def clean_filename(text):
    if not text: return "CLIENTE"
    text = re.sub(r'[^\w\s-]', '', text).strip()
    return re.sub(r'[-\s]+', '_', text).upper()

TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "SPOST_ENTRO_10": 226.36, "SPOST_OLTRE_10": 226.36, 
    "ISTRUTTORIA": 27.42, "FISSO_BASE_CALCOLO": 25.88
}

# --- FUNZIONE PDF ---
def genera_pdf(d):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(0, 29, 61); pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_xy(120, 12); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(80, 5, "POLIS ENERGIA SRL", align='R', ln=1)
    pdf.set_font("Helvetica", "", 8); pdf.cell(80, 4, "www.polisenergia.it", align='R', ln=1)
    pdf.set_xy(10, 55); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"SPETT.LE: {d['nome']}", ln=1)
    pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, f"INDIRIZZO: {d['indirizzo']}", ln=1)
    pdf.ln(10); pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"PREVENTIVO {d['pratica'].upper()} - POD: {d['pod']}", border="B", ln=1)
    
    # Tabella Voci
    pdf.ln(5); pdf.set_fill_color(0, 180, 216); pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, " DESCRIZIONE PRESTAZIONE", 1, 0, 'L', True); pdf.cell(50, 10, " IMPORTO", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 8, " ONERI DISTRIBUTORE", 1, 1, 'L', True)
    pdf.set_font("Helvetica", "", 10)
    
    # Descrizione Tecnica
    desc_pot = f" Quota Potenza: da {d['p_att']}kW ({d['t_att']}) a {d['p_new']}kW ({d['t_new']})"
    pdf.cell(140, 8, desc_pot, 1); pdf.cell(50, 8, f"{d['c_tec']:.2f} EUR", 1, 1, 'R')
    
    if d['c_dist'] > 0:
        pdf.cell(140, 8, " Quota Distanza (Rilievi)", 1); pdf.cell(50, 8, f"{d['c_dist']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Istruttoria Pratica", 1); pdf.cell(50, 8, f"{TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    
    pdf.set_font("Helvetica", "B", 9); pdf.cell(190, 8, " ONERI PROFESSIONALI POLIS ENERGIA", 1, 1, 'L', True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 8, " Gestione Tecnica e Amministrativa (10%)", 1); pdf.cell(50, 8, f"{d['c_gest']:.2f} EUR", 1, 1, 'R')
    
    # Totali
    pdf.ln(2); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 9, " IMPONIBILE", 1); pdf.cell(50, 9, f"{d['imponibile']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, f" IVA ({d['iva_perc']}%)", 1); pdf.cell(50, 9, f"{d['iva_euro']:.2f} EUR", 1, 1, 'R')
    if d['bollo'] > 0:
        pdf.cell(140, 9, " MARCA DA BOLLO", 1); pdf.cell(50, 9, "2.00 EUR", 1, 1, 'R')
    
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Helvetica", "B", 11)
    pdf.cell(140, 11, " TOTALE DA PAGARE", 1, 0, 'L', True); pdf.cell(50, 11, f"{d['totale']:.2f} EUR", 1, 1, 'R', True)
    
    pdf.ln(10); pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(190, 4, f"Causale: {st.session_state.codice_causale}\nIBAN: IT80P0103015200000007044056 - MPS")
    return pdf.output()

# --- INTERFACCIA ---
st.title("⚡ POLIS ENERGIA SUITE")
st.caption(f"v74.1 | Codice: {st.session_state.codice_causale}")

with st.form("main_form"):
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Anagrafica")
        nome = st.text_input("Ragione Sociale").upper()
        indirizzo = st.text_input("Indirizzo")
        uso = st.selectbox("Regime Fiscale", ["IVA 10%", "IVA 22%", "P.A.", "Esente"])
        pod = st.text_input("POD").upper()

    with c2:
        st.subheader("Parametri Tecnici")
        pratica = st.selectbox("Tipo di Pratica", ["Nuova Connessione", "Aumento Potenza", "Subentro con Modifica", "Spostamento"])
        tipo_ut = st.radio("Destinazione Uso", ["Domestico", "Altri Usi"], horizontal=True)
        
        # Logica Tensione
        t_att, t_new = "BT", "BT"
        if tipo_ut == "Altri Usi":
            cambio_tens = st.checkbox("🔄 Cambio Livello Tensione (es. BT -> MT)")
            if cambio_tens:
                col_t1, col_t2 = st.columns(2)
                t_att = col_t1.selectbox("Tensione Partenza", ["BT", "MT"])
                t_new = col_t2.selectbox("Tensione Arrivo", ["BT", "MT"], index=1)
            else:
                t_att = t_new = st.radio("Tensione", ["BT", "MT"], horizontal=True)
        else:
            st.info("Utenza Domestica: Tensione fissa in BT")
            t_att = t_new = "BT"

        # Variabili Potenza
        p_att, p_new, c_dist = 0.0, 0.0, 0.0
        
        if pratica == "Spostamento":
            s_dist = st.radio("Distanza", ["Entro 10m", "Oltre 10m"], horizontal=True)
            if s_dist == "Oltre 10m":
                c_dist = st.number_input("Quota Distanza Distributore (€)", value=0.0)
        
        elif pratica == "Nuova Connessione":
            p_new = st.number_input("Potenza Richiesta (kW)", value=3.0, step=0.5)
            c_dist = st.number_input("Quota Distanza (€)", value=0.0)
            
        else: # Aumento o Subentro
            col_p1, col_p2 = st.columns(2)
            p_att = col_p1.number_input("Potenza ATTUALE (kW)", value=3.0, step=0.5)
            p_new = col_p2.number_input("Potenza RICHIESTA (kW)", value=6.0, step=0.5)

        app_gest = st.checkbox("Gestione Polis (10%)", value=True)
    
    submit = st.form_submit_button("📁 GENERA PREVENTIVO")

# --- MOTORE DI CALCOLO ---
if submit:
    if nome and indirizzo:
        # 1. Coefficienti Franchigia
        f_att = 1.1 if (t_att == "BT" and p_att <= 30) else 1.0
        f_new = 1.1 if (t_new == "BT" and p_new <= 30) else 1.0
        
        # 2. Tariffe Unitarie (Partenza e Arrivo)
        def get_tariffa(tens, pot, ut):
            if tens == "MT": return TIC_2026["MT"]
            if ut == "Domestico" and pot <= 6: return TIC_2026["DOM_LE6"]
            return TIC_2026["BT_ALTRI"]

        px_att = get_tariffa(t_att, p_att, tipo_ut)
        px_new = get_tariffa(t_new, p_new, tipo_ut)
        
        # 3. Quota Tecnica Differenziale
        if pratica == "Spostamento":
            c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in s_dist else TIC_2026["SPOST_OLTRE_10"]
        else:
            # Calcolo: (Nuova Potenza Corretta * Nuova Tariffa) - (Vecchia Potenza Corretta * Vecchia Tariffa)
            # Se è nuova connessione p_att è 0, quindi il calcolo fila.
            c_tec = max(0.0, (p_new * f_new * px_new) - (p_att * f_att * px_att))
            
        # 4. Totali
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
        
        st.success("Analisi Tecnica Completata.")
        pdf_file = genera_pdf(dati)
        st.download_button("📥 SCARICA PDF", data=bytes(pdf_file), file_name=f"Prev_{clean_filename(nome)}.pdf", use_container_width=True)
    else:
        st.error("Inserire Ragione Sociale e Indirizzo.")
