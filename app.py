import streamlit as st
import math
import random
import string
import re
from fpdf import FPDF

# 1. Configurazione Pagina
st.set_page_config(page_title="Preventivatore PolisEnergia 4.0", page_icon="⚡", layout="wide")

# --- INIZIALIZZAZIONE BLOCCATA (Previene NameError) ---
if 'codice_causale' not in st.session_state:
    st.session_state.codice_causale = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
if 'nome_input' not in st.session_state:
    st.session_state.nome_input = ""
if 'indirizzo_input' not in st.session_state:
    st.session_state.indirizzo_input = ""
if 'pod_input' not in st.session_state:
    st.session_state.pod_input = ""

# --- FUNZIONI DI SERVIZIO ---
def clean_filename(text):
    text = re.sub(r'[^\w\s-]', '', text).strip()
    return re.sub(r'[-\s]+', '_', text).upper()

def reset_campi():
    st.session_state.nome = ""
    st.session_state.indirizzo = ""
    st.session_state.pod = ""
    st.session_state.p_att = 3.0
    st.session_state.p_new = 6.0
    st.session_state.dist_manuale = 0.0
    st.session_state.codice_causale = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

if 'codice_causale' not in st.session_state:
    reset_campi()

# 2. Costanti TIC 2026
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "SPOST_ENTRO_10": 226.36, "SPOST_OLTRE_10": 226.36, 
    "ISTRUTTORIA": 27.42, "FISSO_BASE_CALCOLO": 25.88
}

# --- HEADER ---
col_t1, col_t2 = st.columns([4, 1])
with col_t1:
    st.title("⚡ PolisEnergia srl")
    st.caption(f"Preventivo | Codice: **{st.session_state.codice_causale}**")
with col_t2:
    if st.button("🔴 PULISCI CAMPI", use_container_width=True):
        reset_campi()
        st.rerun()

st.divider()

# --- INPUT ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("Dati Intestatario")
    nome_input = st.text_input("Ragione Sociale / Nome Cognome", key="nome").upper()
    indirizzo = st.text_input("Indirizzo Completo", key="indirizzo")
    uso = st.selectbox("Regime Fiscale / IVA", ["IVA 10% (Domestico)", "IVA 22% (Business)", "P.A. (Split Payment)", "Esente"])
    pod = st.text_input("Codice POD", key="pod").upper()

with col2:
    st.subheader("Parametri Tecnici")
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    tipo_utenza = st.radio("Tipologia Utenza", ["Domestico", "Altri Usi"], horizontal=True)
    
    is_spostamento = "Spostamento" in pratica
    is_nuova = "Nuova" in pratica
    c_tec, c_dist_totale = 0.0, 0.0
    d_potenza = ""

    if is_spostamento:
        dist_choice = st.radio("Tipologia Spostamento", ["Entro 10 metri", "Oltre 10 metri"], horizontal=True)
        if dist_choice == "Entro 10 metri":
            c_tec = TIC_2026["SPOST_ENTRO_10"]
            d_potenza = f"Spostamento Fisso (<10m): **{c_tec:.2f} €**"
        else:
            c_tec = TIC_2026["SPOST_OLTRE_10"]
            c_dist_totale = st.number_input("Importo Quota Distanza (da preventivo Distributore)", min_value=0.0, step=10.0, key="dist_manuale")
            d_potenza = f"Base Spostamento (>10m): **{c_tec:.2f} €**"
    else:
        cp1, cp2 = st.columns(2)
        p_att = cp1.number_input("Potenza Attuale (kW)", min_value=0.0, step=0.5, key="p_att") if not is_nuova else 0.0
        p_new = cp2.number_input("Nuova Potenza (kW)", min_value=0.1, step=0.5, key="p_new")
        
        t_new = st.selectbox("Tensione", ["BT", "MT"] if tipo_utenza == "Altri Usi" else ["BT"])
        f_new = 1.1 if (t_new == "BT" and p_new <= 30) else 1.0
        f_att = 1.1 if (not is_nuova and p_att <= 30) else 1.0
        px = TIC_2026["MT"] if t_new == "MT" else (TIC_2026["DOM_LE6"] if (tipo_utenza == "Domestico" and p_new <= 6) else TIC_2026["BT_ALTRI"])
        
        dp = max(0.0, (p_new * f_new) - (p_att * f_att))
        c_tec = dp * px
        d_potenza = f"Quota Potenza: {dp:.2f} kW x {px:.2f} € = **{c_tec:.2f} €**"

        if is_nuova:
            c_dist_totale = st.number_input("Importo Quota Distanza (da preventivo Distributore)", min_value=0.0, step=10.0, key="dist_manuale")

    applica_gestione = st.checkbox("Applica Oneri Gestione Polis (10%)", value=True)

# --- CALCOLI ---
c_gest = (c_tec + c_dist_totale + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if applica_gestione else 0.0
tot_sogg_iva = c_tec + c_dist_totale + c_gest + TIC_2026["ISTRUTTORIA"]
is_pa = "P.A." in uso
aliq = 0.10 if "10%" in uso else (0.22 if ("22%" in uso or is_pa) else 0.0)
iva = tot_sogg_iva * aliq
bollo = 2.0 if (uso == "Esente" and tot_sogg_iva > 77.47) else 0.0
totale = (tot_sogg_iva if is_pa else tot_sogg_iva + iva) + bollo

# --- ANTEPRIMA ---
st.divider()
st.subheader("🔍 Riepilogo Costi")
ca1, ca2 = st.columns(2)
with ca1:
    st.markdown(f"1. **Parte Tecnica**: {d_potenza}")
    if c_dist_totale > 0: st.markdown(f"2. **Quota Distanza**: **{c_dist_totale:.2f} €**")
    st.markdown(f"3. **Istruttoria**: {TIC_2026['ISTRUTTORIA']:.2f} €")
    if applica_gestione: st.markdown(f"4. **Gestione (10%)**: {c_gest:.2f} €")
with ca2:
    st.metric("IMPONIBILE", f"{tot_sogg_iva:.2f} €")
    st.success(f"### TOTALE IVATO: {totale:.2f} €")
# --- PDF ---
def genera_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(0, 29, 61); pdf.rect(0, 0, 210, 45, 'F')
    try: pdf.image("logo_polis.png", x=10, y=10, w=45)
    except: pass
    pdf.set_xy(10, 32); pdf.set_font("Helvetica", "I", 9); pdf.set_text_color(200, 200, 200); pdf.cell(0, 10, "Ufficio Tecnico Connessioni")
    pdf.set_xy(120, 12); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 8); pdf.cell(0, 5, "PolisEnergia srl - Via Terre delle Risaie,4 - 84131 Salerno (SA)", ln=True, align='R')
    pdf.set_font("Helvetica", "", 8); pdf.cell(0, 6, "www.polisenergia.it", ln=True, align='R')
    
    pdf.set_xy(10, 55); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, "Spett.le Cliente:", ln=True)
    pdf.set_font("Helvetica", "", 11); pdf.cell(0, 6, f"{nome}", ln=True); pdf.cell(0, 6, f"{indirizzo}", ln=True)
    
    pdf.ln(10); pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 10, f"PREVENTIVO PER {pratica.upper()} - POD: {pod if pod else 'N.D.'}", border="B", ln=True)
    
    pdf.ln(5); pdf.set_fill_color(0, 180, 216); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 10, " DESCRIZIONE DETTAGLIATA", 1, 0, 'L', True); pdf.cell(50, 10, " IMPORTO", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 10)
    pdf.cell(140, 9, f" {desc_riga_1}", 1); pdf.cell(50, 9, f"{c_tec:.2f} EUR", 1, 1, 'R')
    if is_nuova:
        pdf.cell(140, 9, " Quota Distanza (come da rilievi Distributore Locale)", 1); pdf.cell(50, 9, f"{c_dist_totale:.2f} EUR", 1, 1, 'R')
    pdf.cell(140, 9, " Oneri Amministrativi", 1); pdf.cell(50, 9, f"{TIC_2026['ISTRUTTORIA']:.2f} EUR", 1, 1, 'R')
    if applica_gestione:
        pdf.cell(140, 9, " Oneri di Gestione Pratica", 1); pdf.cell(50, 9, f"{c_gest:.2f} EUR", 1, 1, 'R')
    if bollo_2 > 0:
        pdf.cell(140, 9, " Imposta di Bollo", 1); pdf.cell(50, 9, "2.00 EUR", 1, 1, 'R')
    
    pdf.set_font("Helvetica", "B", 10); pdf.cell(140, 9, f" IVA ({int(aliq*100)}%)", 1); pdf.cell(50, 9, f"{tot_iva:.2f} EUR", 1, 1, 'R')
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Helvetica", "B", 11); pdf.cell(140, 11, " TOTALE DOVUTO", 1, 0, 'L', True); pdf.cell(50, 11, f"{tot_finale:.2f} EUR", 1, 1, 'R', True)
    
    pdf.ln(10); pdf.set_font("Helvetica", "B", 8); pdf.cell(0, 5, "NOTE TECNICHE E CONDIZIONI:", ln=True)
    pdf.set_font("Helvetica", "", 8)
    note = (f"- Gli oneri di connessione sono calcolati sulla base della normativa TIC vigente e dei rilievi del Distributore Locale.\n"
            f"- Eventuali variazioni di distanza o complessità tecnica riscontrate in fase di esecuzione daranno luogo a conguaglio.\n"
            f"- Validità: 30 gg | Pagamento: IT80P0103015200000007044056 - MPS | Causale: {st.session_state.codice_causale}")
    pdf.multi_cell(190, 4, note)
    
    pdf.ln(15); pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 5, "Per Accettazione Cliente (Firma)", ln=1, align='R')
    pdf.line(130, pdf.get_y()+5, 200, pdf.get_y()+5)
    return pdf.output()

# --- BOTTONE ---
if st.button("🚀 GENERA PDF"):
    if nome_val and ind_val:
        dati_per_pdf = {
            'nome': nome_val, 'indirizzo': ind_val, 'pod': pod_val if pod_val else "N.D.",
            'pratica': pratica, 'c_tec': c_tec, 'c_dist': c_dist, 'c_gest': c_gest,
            'iva_perc': iva_perc, 'iva_euro': iva_euro, 'totale': totale_finale
        }
        pdf_finito = genera_pdf(dati_per_pdf)
        nome_file = f"Preventivo_{pratica.replace(' ','')}_{clean_filename(nome_val)}_{st.session_state.codice_causale}.pdf"
        st.download_button("📥 Scarica", data=bytes(pdf_finito), file_name=nome_file)
    else: st.error("Inserisci Nome e Indirizzo!")
