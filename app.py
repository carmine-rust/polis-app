import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- COSTANTI TECNICHE 2026 ---
TIC_DOMESTICO_LE6 = 62.30  
TIC_ALTRI_USI_BT = 78.81
TIC_MT = 62.74
ONERI_ISTRUTTORIA = 27.42
SPOSTAMENTO_10MT = 226.36
FISSO_BASE_CALCOLO = 25.88
COSTO_PASSAGGIO_MT = 494.83
IBAN_POLIS = "IT80P0103015200000007044056 - Monte dei Paschi di Siena"
LOGO_PATH = "logo_polis.png"

st.set_page_config(page_title="PolisEnergia - Preventivatore", layout="wide")

if 'seq' not in st.session_state: st.session_state.seq = 1
if 'pdf_pronto' not in st.session_state: st.session_state.pdf_pronto = None

def reset_form():
    for key in list(st.session_state.keys()):
        if key not in ['seq']: del st.session_state[key]
    st.rerun()

# --- FUNZIONE PDF ---
def genera_pdf_polis(d):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(0, 29, 61); pdf.rect(0, 0, 210, 45, 'F')
    try: pdf.image(LOGO_PATH, 10, 8, 33)
    except:
        pdf.set_xy(10, 15); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "POLIS ENERGIA SRL")
    
    pdf.set_xy(120, 12); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 5, "PolisEnergia srl - Via Terre delle Risaie, 4 - 84131 Salerno (SA)", align='R', ln=1)
    pdf.set_font("Helvetica", "", 8); pdf.cell(0, 5, "P.IVA 05050950657 - assistenza@polisenergia.it", align='R', ln=1)
    
    pdf.set_xy(10, 55); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"PREVENTIVO N. {d['Codice']}", ln=1)
    pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, f"Data: {d['Data']}", ln=1)
    
    pdf.ln(5); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"CLIENTE: {d['Cliente']}", ln=1)
    pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, f"Indirizzo: {d['Indirizzo']}", ln=1); pdf.cell(0, 6, f"POD: {d['POD']}", ln=1)
    
    pdf.ln(10); pdf.set_fill_color(0, 119, 182); pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 10, " DESCRIZIONE", 1, 0, 'L', True); pdf.cell(50, 10, " IMPORTO", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 8, f" Quota Tecnica TIC (Calcolata su Potenza Disponibile Arrotondata)", 1); pdf.cell(50, 8, f"{d['Quota_Tecnica']:.2f} EUR", 1, 1, 'R')
    if d['c_dist'] > 0: pdf.cell(140, 8, " Quota Distanza / Oneri di Rilievo", 1); pdf.cell(50, 8, f"{d['c_dist']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Amministrativi", 1); pdf.cell(50, 8, f"{ONERI_ISTRUTTORIA:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 8, " Oneri Gestione Pratica", 1); pdf.cell(50, 8, f"{d['Gestione_Polis']:.2f} EUR", 1, 1, 'R')
    
    pdf.ln(2); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 9, " TOTALE IMPONIBILE", 1); pdf.cell(50, 9, f"{d['Imponibile']:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, f" IVA APPLICATA ({d['iva_perc']}%)", 1); pdf.cell(50, 9, f"{d['IVA_Euro']:.2f} EUR", 1, 1, 'R')
    if d['bollo'] > 0: pdf.cell(140, 9, " IMPOSTA DI BOLLO", 1); pdf.cell(50, 9, "2.00 EUR", 1, 1, 'R')
    
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(140, 11, " TOTALE DA PAGARE", 1, 0, 'L', True); pdf.cell(50, 11, f"{d['Totale']:.2f} EUR", 1, 1, 'R', True)
    
    pdf.ln(15); pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, "COORDINATE BANCARIE:", ln=1)
    pdf.set_font("Helvetica", "", 10); pdf.cell(0, 6, f"IBAN: {IBAN_POLIS}", ln=1)
    # CAUSALE DINAMICA SOTTO IBAN
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, f"CAUSALE: Accettazione Preventivo {d['Codice']}", ln=1)
    
    pdf.ln(25); pdf.cell(100, 10, "Firma PolisEnergia srl", ln=0); pdf.cell(90, 10, "Firma Accettazione Cliente", ln=1, align='R')
    pdf.line(10, 195, 70, 195); pdf.line(140, 195, 200, 195)
    return bytes(pdf.output())

# --- INTERFACCIA ---
st.title("⚡ PolisEnergia 4.0")

c_head1, c_head2 = st.columns([9, 1])
with c_head2:
    if st.button("🧹 PULISCI"): reset_form()

with st.container():
    c1, c2 = st.columns(2)
    with c1:
        nome = st.text_input("Ragione Sociale", key="k_nome").upper()
        indirizzo = st.text_input("Indirizzo", key="k_ind")
    with c2:
        regime = st.selectbox("Regime Fiscale", ["IVA 10%", "IVA 22%", "P.A.", "Esente"], key="k_reg")
        pod = st.text_input("POD", key="k_pod").upper()

st.divider()

pratica = st.selectbox("Operazione", ["Aumento Potenza", "Subentro con Modifica", "Nuova Connessione", "Spostamento"], key="k_prat")
tipo_ut = st.radio("Utenza", ["Domestico", "Altri Usi"], horizontal=True, key="k_tipo")

p_att, p_new, c_dist, t_att, t_new, flag_mt, s_dist = 0.0, 0.0, 0.0, "BT", "BT", False, ""

if "Potenza" in pratica or "Subentro" in pratica:
    col1, col2 = st.columns(2)
    with col1:
        if tipo_ut == "Altri Usi":
            flag_mt = st.checkbox("🔄 Passaggio a MT?", key="k_mt")
            if flag_mt: t_att, t_new = "BT", "MT"
            else:
                t_att = st.radio("Tensione Attuale", ["BT", "MT"], horizontal=True, key="k_ta")
                t_new = st.radio("Nuova Tensione", ["BT", "MT"], horizontal=True, key="k_tn")
        p_att = st.number_input("Potenza Attuale (kW)", value=2.0, step=0.5, key="k_pa")
    with col2:
        p_new = st.number_input("Nuova Potenza (kW)", value=3.0, step=0.5, key="k_pn")
elif "Nuova" in pratica:
    c1, c2 = st.columns(2)
    p_new = c1.number_input("Potenza (kW)", value=3.0, step=0.5, key="k_pnc")
    c_dist = c2.number_input("Quota Distanza (€)", 0.0, key="k_dist")
elif "Spostamento" in pratica:
    s_dist = st.radio("Distanza", ["Entro 10 mt", "Oltre 10 mt"], horizontal=True, key="k_sdist")
    if "Oltre" in s_dist: c_dist = st.number_input("Costo (€)", 0.0, key="k_sdist_c")

# --- MOTORE DI CALCOLO CON ARROTONDAMENTO PER ECCESSO (CEIL) ---
if t_new == "MT": tar = TIC_MT
elif tipo_ut == "Domestico" and p_new <= 6: tar = TIC_DOMESTICO_LE6
else: tar = TIC_ALTRI_USI_BT

# Logica Arrotondamento franchigia 10%
def calcola_disponibile(p, tensione):
    if tensione == "BT":
        return math.ceil(p * 1.1) # ES: 4.5 * 1.1 = 4.95 -> 5
    return p

if "Spostamento" in pratica:
    c_tec = SPOSTAMENTO_10MT if "Entro" in s_dist else 0.0
elif "Nuova" in pratica:
    disp_new = calcola_disponibile(p_new, t_new)
    c_tec = disp_new * tar
else:
    disp_new = calcola_disponibile(p_new, t_new)
    disp_att = calcola_disponibile(p_att, t_att)
    c_tec = (disp_new - disp_att) * tar
    if flag_mt: c_tec += COSTO_PASSAGGIO_MT

app_gest = st.checkbox("Gestione Polis (10%)", value=True, key="k_gest_chk")
c_gest = (c_tec + c_dist + FISSO_BASE_CALCOLO) * 0.1 if app_gest else 0.0
imp = c_tec + c_dist + c_gest + ONERI_ISTRUTTORIA
iva_p = 10 if "10" in regime else (22 if "22" in regime or "P.A." in regime else 0)
iva_e = imp * (iva_p/100)
bollo = 2.0 if (regime == "Esente" and imp > 77.47) else 0.0
tot = (imp if "P.A." in regime else imp + iva_e) + bollo

st.subheader(f"Totale: {tot:.2f} €")

if st.button("📁 GENERA PREVENTIVO", type="primary", use_container_width=True):
    if nome and pod:
        cod = f"PREV2026{st.session_state.seq:04d}"
        
        dati_finali = {
            'Data': datetime.now().strftime("%d/%m/%Y"),
            'Codice': cod,
            'Cliente': nome,
            'Indirizzo': indirizzo,
            'POD': pod,
            'Potenza_Att': round(p_att, 2),
            'Potenza_New': round(p_new, 2),
            'Quota_Tecnica': round(c_tec, 2),
            'Gestione_Polis': round(c_gest, 2),
            'Imponibile': round(imp, 2),
            'IVA_Euro': round(iva_e, 2),
            'Totale': round(tot, 2),
            'iva_perc': iva_p,
            'bollo': bollo,
            'c_dist': c_dist
        }
        
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df_esistente = conn.read()
            df_nuovo = pd.concat([df_esistente, pd.DataFrame([{k: v for k, v in dati_finali.items() if k not in ['iva_perc', 'bollo', 'c_dist', 'Indirizzo']}])], ignore_index=True)
            conn.update(data=df_nuovo)
        except: pass
        
        st.session_state.pdf_pronto = genera_pdf_polis(dati_finali)
        st.session_state.ultimo_codice = cod
        st.session_state.seq += 1
        st.rerun()

if st.session_state.pdf_pronto:
    st.download_button(f"📥 SCARICA {st.session_state.ultimo_codice}", st.session_state.pdf_pronto, f"{st.session_state.ultimo_codice}.pdf", use_container_width=True)
