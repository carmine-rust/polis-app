import streamlit as st
import math
import random
import string
from fpdf import FPDF
from datetime import datetime

# 1. Configurazione
st.set_page_config(page_title="PolisEnergia Suite", page_icon="⚡", layout="wide")

# 2. Costanti TIC 2026
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "DIST_FISSA": 209.62, "DIST_EXTRA": 105.08, 
    "SPOST_ENTRO_10": 226.36, "SPOST_OLTRE_10": 226.36, 
    "ISTRUTTORIA": 27.42, "FISSO_BASE_CALCOLO": 25.88
}

if 'codice_causale' not in st.session_state:
    st.session_state.codice_causale = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# --- INTERFACCIA ---
st.title("⚡ POLIS ENERGIA")
st.caption("Configuratore Professionale v71.9 - Spostamenti Certificati")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Dati Intestatario")
    nome = st.text_input("Ragione Sociale / Nome Cognome").upper()
    indirizzo = st.text_input("Indirizzo Completo")
    uso = st.selectbox("Regime Fiscale / IVA", ["IVA 10% (Domestico)", "IVA 22% (Business)", "P.A. (Split Payment)", "Esente"])
    pod = st.text_input("Codice POD (se presente)").upper()

with col2:
    st.subheader("Parametri Tecnici")
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    tipo_utenza = st.radio("Tipologia Utenza", ["Domestico", "Altri Usi"], horizontal=True)
    
    is_spostamento = "Spostamento" in pratica
    is_nuova = "Nuova" in pratica
    c_dist_totale = 0.0
    c_tec = 0.0
    desc_riga_1 = ""

    if is_spostamento:
        dist_choice = st.radio("Tipologia Spostamento", ["Entro 10 metri", "Oltre 10 metri"], horizontal=True)
        if dist_choice == "Entro 10 metri":
            c_tec = TIC_2026["SPOST_ENTRO_10"]
            desc_riga_1 = "Corrispettivo Fisso Spostamento (Entro 10m)"
        else:
            # BLOCCO CAUTELA SPOSTAMENTO > 10M
            st.warning("⚠️ ATTENZIONE: Per spostamenti oltre 10m, i metri di distanza devono essere desunti esclusivamente dal preventivo del distributore.")
            metri_extra_spost = st.number_input("Quota Distanza (Metri eccedenti i 200m da preventivo distributore)", min_value=0, step=1)
            c_tec = TIC_2026["SPOST_OLTRE_10"]
            c_dist_totale = TIC_2026["DIST_FISSA"] + (math.ceil(metri_extra_spost/100) * TIC_2026["DIST_EXTRA"])
            desc_riga_1 = "Corrispettivo Base Spostamento (> 10m)"
    else:
        c_p1, c_p2 = st.columns(2)
        p_att = c_p1.number_input("Potenza Attuale (kW)", min_value=0.0, value=3.0) if not is_nuova else 0.0
        p_new = c_p2.number_input("Nuova Potenza (kW)", min_value=0.1, value=6.0)
        
        if is_nuova:
            st.info("⚠️ Inserire la distanza solo dopo sopralluogo del distributore.")
            metri_extra = st.number_input("Quota Distanza (Metri eccedenti i primi 200m)", min_value=0, step=1)
            c_dist_totale = TIC_2026["DIST_FISSA"] + (math.ceil(metri_extra/100) * TIC_2026["DIST_EXTRA"])

        t_new = st.selectbox("Tensione", ["BT", "MT"] if tipo_utenza == "Altri Usi" else ["BT"])
        f_new = 1.1 if (t_new == "BT" and p_new <= 30) else 1.0
        f_att = 1.1 if (not is_nuova and p_att <= 30) else 1.0
        px = TIC_2026["MT"] if t_new == "MT" else (TIC_2026["DOM_LE6"] if (tipo_utenza == "Domestico" and p_new <= 6) else TIC_2026["BT_ALTRI"])
        c_tec = max(0.0, (p_new * f_new) - (p_att * f_att)) * px
        desc_riga_1 = f"Quota Potenza TIC ({p_new*f_new:.2f} kW Pd)"

    applica_gestione = st.checkbox("Applica Oneri Gestione Polis (10%)", value=True)

# --- CALCOLI FINALI ---
c_gest = (c_tec + c_dist_totale + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if applica_gestione else 0.0
tot_sogg_iva = c_tec + c_dist_totale + c_gest + TIC_2026["ISTRUTTORIA"]
bollo_2 = 2.0 if (uso == "Esente" and tot_sogg_iva > 77.47) else 0.0
aliq = 0.10 if "10%" in uso else (0.22 if ("22%" in uso or "P.A." in uso) else 0.0)
tot_iva = tot_sogg_iva * aliq
tot_finale = (tot_sogg_iva if "P.A." in uso else tot_sogg_iva + tot_iva) + bollo_2

# --- ANTEPRIMA ANALITICA ---
st.divider()
st.subheader("🔍 Dettaglio Analitico dei Costi")
with st.container():
    c_ant1, c_ant2 = st.columns([2, 1])
    with c_ant1:
        st.markdown(f"**1. Componente Tecnica:** {dettaglio_potenza}")
        if dettaglio_distanza:
            st.markdown(f"**2. Componente Distanza:** {dettaglio_distanza}")
        st.markdown(f"**3. Istruttoria Pratica:** Quota fissa ARERA = **{TIC_2026['ISTRUTTORIA']:.2f} €**")
        if applica_gestione:
            st.markdown(f"**4. Gestione PolisEnergia:** (Tecnica + Distanza + {TIC_2026['FISSO_BASE_CALCOLO']:.2f} € base) x 10% = **{c_gest:.2f} €**")
    
    with c_ant2:
        st.write("### Riepilogo")
        st.write(f"Imponibile: {tot_sogg_iva:.2f} €")
        st.write(f"IVA: {tot_iva:.2f} €")
        st.success(f"**TOTALE: {tot_finale:.2f} €**")

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
    if nome and indirizzo:
        pdf_out = genera_pdf(); st.download_button("📥 Scarica", data=bytes(pdf_out), file_name=f"Polis_{st.session_state.codice_causale}.pdf")
    else: st.warning("Inserisci i dati obbligatori!")
