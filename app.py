import streamlit as st
import math
import random
import string
import re
from fpdf import FPDF

# 1. Configurazione Pagina
st.set_page_config(page_title="PolisEnergia Suite", page_icon="⚡", layout="wide")

# --- INIZIALIZZAZIONE ---
if 'codice_causale' not in st.session_state:
    st.session_state.codice_causale = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def clean_filename(text):
    if not text: return "CLIENTE"
    text = re.sub(r'[^\w\s-]', '', text).strip()
    return re.sub(r'[-\s]+', '_', text).upper()

def reset_campi():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- COSTANTI TIC 2026 ---
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
    pdf.ln(5); pdf.set_fill_color(0, 180, 216); pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, " DESCRIZIONE PRESTAZIONE", 1, 0, 'L', True); pdf.cell(50, 10, " IMPORTO", 1, 1, 'C', True)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 8, " ONERI DISTRIBUTORE", 1, 1, 'L', True)
    pdf.set_font("Helvetica", "", 10)
    
    # Descrizione Potenza
    f_text = " (incl. franchigia 10%)" if d['f_new'] > 1.0 else " (Potenza Nominale)"
    pdf.cell(140, 8, f" Quota Potenza: da {d['p_att']} kW a {d['p_new']} kW {f_text}", 1)
    pdf.cell(50, 8, f"{d['c_tec']:.2f} EUR", 1, 1, 'R')
    
    if d['c_dist'] > 0:
        pdf.cell(140, 8, " Quota Distanza (Rilievi)", 1); pdf.cell(50, 8, f"{d['c_dist']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Istruttoria Pratica", 1); pdf.cell(50, 8, f"{TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    
    pdf.set_font("Helvetica", "B", 9); pdf.cell(190, 8, " ONERI PROFESSIONALI POLIS ENERGIA", 1, 1, 'L', True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 8, " Gestione Tecnica e Amministrativa (10%)", 1); pdf.cell(50, 8, f"{d['c_gest']:.2f} EUR", 1, 1, 'R')
    
    pdf.ln(2); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 9, " IMPONIBILE", 1); pdf.cell(50, 9, f"{d['imponibile']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, f" IVA ({d['iva_perc']}%)", 1); pdf.cell(50, 9, f"{d['iva_euro']:.2f} EUR", 1, 1, 'R')
    if d['bollo'] > 0:
        pdf.cell(140, 9, " MARCA DA BOLLO", 1); pdf.cell(50, 9, "2.00 EUR", 1, 1, 'R')
    
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Helvetica", "B", 11)
    pdf.cell(140, 11, " TOTALE DA PAGARE", 1, 0, 'L', True); pdf.cell(50, 11, f"{d['totale']:.2f} EUR", 1, 1, 'R', True)
    
    pdf.ln(10); pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(190, 4, f"Causale Obbligatoria: {st.session_state.codice_causale}\nIBAN: IT80P0103015200000007044056 - MPS")
    return pdf.output()

# --- INTERFACCIA ---
st.title("⚡ POLIS ENERGIA SUITE")
st.caption(f"v73.7 | Codice Unico: {st.session_state.codice_causale}")

if st.button("🔴 RESET"):
    reset_campi()

st.divider()

with st.form("main_form"):
    c1, c2 = st.columns(2)
    with c1:
        nome = st.text_input("Ragione Sociale", key="n_f").upper()
        indirizzo = st.text_input("Indirizzo", key="i_f")
        uso = st.selectbox("Regime IVA", ["IVA 10%", "IVA 22%", "P.A.", "Esente"], key="v_f")
        pod = st.text_input("POD", key="p_f").upper()

    with c2:
        pratica = st.selectbox("Pratica", ["Nuova Connessione", "Aumento Potenza", "Subentro con Modifica", "Spostamento"], key="pr_f")
        tipo_ut = st.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True, key="ut_f")
        
        # --- LOGICA POTENZE (RIFORMULATA) ---
        p_att_val, p_new_val = 0.0, 0.0
        c_dist_manuale = 0.0
        
        if "Spostamento" in pratica:
            s_choice = st.radio("Distanza", ["Entro 10m", "Oltre 10m"], horizontal=True)
            if "Oltre" in s_choice:
                c_dist_manuale = st.number_input("Quota Distanza Distributore (€)", value=0.0)
        else:
            col_pot1, col_pot2 = st.columns(2)
            # Mostra la potenza di partenza se NON è una nuova connessione
            with col_pot1:
                if "Nuova" not in pratica:
                    p_att_val = st.number_input("Potenza Attuale (kW)", value=3.0, step=0.5)
                else:
                    st.write("Potenza Attuale: 0 kW")
            with col_pot2:
                p_new_val = st.number_input("Nuova Richiesta (kW)", value=6.0, step=0.5)
            
            if "Nuova" in pratica:
                c_dist_manuale = st.number_input("Quota Distanza Distributore (€)", value=0.0)
                
        app_gest = st.checkbox("Gestione Polis (10%)", value=True)
    
    submit = st.form_submit_button("📁 CALCOLA E GENERA")

# --- CALCOLI POST-SUBMIT ---
if submit:
    if nome and indirizzo:
        # 1. Calcolo kW con soglia 30 kW
        f_att = 1.1 if p_att_val <= 30 else 1.0
        f_new = 1.1 if p_new_val <= 30 else 1.0
        
        # 2. Quota Tecnica
        px = TIC_2026["DOM_LE6"] if (tipo_ut == "Domestico" and p_new_val <= 6) else TIC_2026["BT_ALTRI"]
        
        if "Spostamento" in pratica:
            c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in s_choice else TIC_2026["SPOST_OLTRE_10"]
        else:
            diff_kw = max(0.0, (p_new_val * f_new) - (p_att_val * f_att))
            c_tec = diff_kw * px
            
        # 3. Altri Oneri
        c_gest = (c_tec + c_dist_manuale + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if app_gest else 0.0
        imp = c_tec + c_dist_manuale + c_gest + TIC_2026["ISTRUTTORIA"]
        iva_p = 10 if "10" in uso else (22 if ("22" in uso or "P.A." in uso) else 0)
        iva_e = imp * (iva_p/100)
        bollo = 2.0 if (uso == "Esente" and imp > 77) else 0.0
        tot = (imp if "P.A." in uso else imp + iva_e) + bollo

        dati = {
            'nome': nome, 'indirizzo': indirizzo, 'pod': pod if pod else "N.D.",
            'pratica': pratica, 'c_tec': c_tec, 'c_dist': c_dist_manuale, 'c_gest': c_gest,
            'p_att': p_att_val, 'p_new': p_new_val, 'f_new': f_new,
            'imponibile': imp, 'iva_perc': iva_p, 'iva_euro': iva_e, 'bollo': bollo, 'totale': tot
        }
        
        st.success(f"Dati calcolati con successo per {nome}!")
        pdf_out = genera_pdf(dati)
        fname = f"Preventivo_{clean_filename(nome)}.pdf"
        st.download_button("📥 SCARICA ORA IL PDF", data=bytes(pdf_out), file_name=fname, use_container_width=True)
    else:
        st.error("Ragione Sociale e Indirizzo sono obbligatori!")
