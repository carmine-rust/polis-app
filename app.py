import streamlit as st
import math
from fpdf import FPDF

# --- SETUP NATIVO ---
st.set_page_config(page_title="PolisEnergia Suite", page_icon="⚡", layout="wide")

# --- COSTANTI TIC 2026 ---
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "PASS_BT_MT": 494.83, "DIST_FISSA": 209.62, 
    "DIST_EXTRA": 105.08, "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 452.72, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88 
}

# --- INTERFACCIA ---
st.title("⚡ POLIS ENERGIA")
st.caption("Configuratore Professionale - Revisione PDF 2026")

col1, col2 = st.columns(2)
with col1:
    tipo_utenza = st.radio("Tipologia Utenza", ["Domestico", "Altri Usi"], horizontal=True)
    uso = st.selectbox("Regime Fiscale / IVA", ["IVA 10% (Domestico)", "IVA 22% (Business)", "P.A. (Split Payment)", "Esente"])
    nome = st.text_input("Intestatario / Ragione Sociale").upper()
    pod = st.text_input("Codice POD").upper()
with col2:
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    t_att = st.selectbox("Tensione Attuale", ["BT", "MT"])
    op_t_new = ["BT"] if tipo_utenza == "Domestico" else ["BT", "MT"]
    t_new = st.selectbox("Tensione Richiesta", op_t_new)
    applica_gestione = st.checkbox("Applica Oneri Gestione Polis (10%)", value=True)

# --- CALCOLI ---
st.divider()
p_att, p_new, dist_m, c_tec = 0.0, 0.0, 0, 0.0
if "Spostamento" in pratica:
    tipo_sp = st.radio("Distanza", ["Entro 10m", "Oltre 10m"])
    c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in tipo_sp else TIC_2026["SPOST_OLTRE_10"]
    f_new = 1.0
else:
    c_p1, c_p2, c_p3 = st.columns(3)
    if "Nuova" not in pratica: p_att = c_p1.number_input("Potenza Attuale (kW)", min_value=0.0, value=3.0)
    p_new = c_p2.number_input("Nuova Potenza (kW)", min_value=0.1, value=6.0)
    if "Nuova" in pratica: dist_m = c_p3.number_input("Metri oltre i 200m", min_value=0)
    f_new = 1.1 if ("BT" in t_new and p_new <= 30) else 1.0
    f_att = 1.1 if ("BT" in t_att and p_att <= 30) else 1.0
    px = TIC_2026["MT"] if "MT" in t_new else (TIC_2026["DOM_LE6"] if (tipo_utenza == "Domestico" and p_new <= 6) else TIC_2026["BT_ALTRI"])
    if "Nuova" in pratica: c_tec = (p_new * f_new * px) + TIC_2026["DIST_FISSA"] + (math.ceil(dist_m/100) * TIC_2026["DIST_EXTRA"])
    else: c_tec = max(0.0, (p_new * f_new) - (p_att * f_att)) * px

c_pass = TIC_2026["PASS_BT_MT"] if ("BT" in t_att and "MT" in t_new) else 0
c_gest = (c_tec + c_pass + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10 if applica_gestione else 0.0
tot_imp = c_tec + c_pass + c_gest + TIC_2026["ISTRUTTORIA"]
is_split = "P.A." in uso
aliq = 0.10 if "10%" in uso else (0.22 if ("22%" in uso or is_split) else 0.0)
tot_iva = tot_imp * aliq
tot_finale = tot_imp if is_split else tot_imp + tot_iva

# --- RISULTATI A VIDEO ---
st.metric("TOTALE PREVENTIVATO", f"{tot_finale:.2f} €")

# --- FUNZIONE GENERAZIONE PDF PROFESSIONALE CON LOGO ---
def genera_pdf():
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Header con Logo e Fascia Blu
    pdf.set_fill_color(0, 29, 61)  # Blu Notte Polis
    pdf.rect(0, 0, 210, 45, 'F')
    
    # Inserimento Logo (Assicurati che 'logo.png' sia nella stessa cartella del codice)
    try:
        # x=10, y=8, w=40 (larghezza 40mm, proporzioni mantenute)
        pdf.image("logo.png", 10, 8, 45) 
    except:
        # Se il logo non viene trovato, scrive il nome come fallback per non far crashare il PDF
        pdf.set_xy(10, 15)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 10, "PolisEnergia", ln=False)

    # Testo Intestazione a destra
    pdf.set_xy(120, 12)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(80, 5, "PolisEnergia SRL", ln=True, align='R')
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(80, 5, "Ufficio Tecnico Connessioni", ln=True, align='R')
    pdf.cell(80, 5, "www.polisenergia.it", ln=True, align='R')
    
    # 2. Dati Cliente e Pratica
    pdf.ln(25)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"PREVENTIVO COMMERCIALE: {nome}", ln=True)
    
    pdf.set_font("Helvetica", "", 10)
    col_width = 95
    pdf.cell(col_width, 7, f"Codice POD: {pod}", 0)
    pdf.cell(col_width, 7, f"Data Emissione: {st.datetime.now().strftime('%d/%m/%Y')}", 0, 1, 'R')
    pdf.cell(col_width, 7, f"Tipologia: {pratica}", 0)
    pdf.cell(col_width, 7, f"Potenza Contrattuale: {p_new} kW", 0, 1, 'R')
    pdf.cell(col_width, 7, f"Tensione: {t_new}", 0)
    pdf.cell(col_width, 7, f"Potenza Disponibile (Pd): {p_new*f_new:.2f} kW", 0, 1, 'R')
    
    pdf.ln(10)
    
    # 3. Tabella Riepilogo Costi
    pdf.set_fill_color(0, 180, 216) # Azzurro Polis per header
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(135, 10, " DESCRIZIONE DETTAGLIATA", 1, 0, 'L', True)
    pdf.cell(55, 10, " IMPORTO", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    
    # Righe dinamiche
    voci = [
        (f"Quota Potenza TIC ({p_new*f_new:.2f} kW disp.)", f"{c_tec:.2f} EUR"),
        ("Oneri Amministrativi (Istruttoria Distributore)", f"{TIC_2026['ISTRUTTORIA']:.2f} EUR")
    ]
    if c_pass > 0:
        voci.append(("Contributo Passaggio Tensione BT/MT", f"{c_pass:.2f} EUR"))
    if applica_gestione:
        voci.append(("Oneri Gestione Tecnica PolisEnergia (10%)", f"{c_gest:.2f} EUR"))
    
    for desc, imp in voci:
        pdf.cell(135, 10, f" {desc}", 1)
        pdf.cell(55, 10, f" {imp}", 1, 1, 'R')
        
    # 4. Totali Finali
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(135, 8, "TOTALE IMPONIBILE", 0, 0, 'R')
    pdf.cell(55, 8, f"{tot_imp:.2f} EUR", 0, 1, 'R')
    
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(135, 8, f"IVA applicata ({int(aliq*100)}%)", 0, 0, 'R')
    pdf.cell(55, 8, f"{tot_iva:.2f} EUR", 0, 1, 'R')
    
    pdf.ln(2)
    pdf.set_text_color(0, 180, 216)
    pdf.set_font("Helvetica", "B", 15)
    label_footer = "TOTALE A PAGARE (IVA Inclusa)" if not is_split else "TOTALE DOVUTO (Split Payment)"
    pdf.cell(135, 12, label_footer, 0, 0, 'R')
    pdf.cell(55, 12, f"{tot_finale:.2f} EUR", 0, 1, 'R')
    
    # 5. Piè di pagina e Note
    pdf.set_y(-60)
    pdf.set_text_color(100, 100, 100)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, "Note Tecniche: Il calcolo della potenza disponibile include la franchigia del 10% per forniture in BT fino a 30kW. I costi sono basati sulle tabelle TIC ARERA 2026. Il presente documento non costituisce fattura.")
    
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(95, 10, "Firma per Accettazione Cliente", 0, 0, 'L')
    pdf.cell(95, 10, "Timbro e Firma PolisEnergia", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# --- DOWNLOAD ---
if st.button("🚀 GENERA PDF PROFESSIONALE"):
    if not nome or not pod:
        st.error("Dati mancanti!")
    else:
        pdf_bytes = genera_pdf()
        st.download_button(label="📥 Scarica Preventivo", data=pdf_bytes, file_name=f"Polis_{pod}.pdf", mime="application/pdf")
