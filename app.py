import streamlit as st
import math
from fpdf import FPDF
from datetime import datetime  # <--- AGGIUNTO QUESTO PER LA DATA

# ... (tutta la parte delle costanti TIC_2026 e i calcoli rimane invariata) ...

# --- FUNZIONE GENERAZIONE PDF PROFESSIONALE CON LOGO ---
def genera_pdf():
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Header con Logo e Fascia Blu Notte
    pdf.set_fill_color(0, 29, 61) 
    pdf.rect(0, 0, 210, 45, 'F')
    
    # Posizionamento Logo
    try:
        # Cerca il file logo_polis.png nella cartella principale
        pdf.image("logo.png", 10, 8, 45) 
    except:
        # Fallback se l'immagine manca: scrive il testo
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
    # CORREZIONE: datetime.now() invece di st.datetime.now()
    pdf.cell(col_width, 7, f"Codice POD: {pod}", 0)
    pdf.cell(col_width, 7, f"Data Emissione: {datetime.now().strftime('%d/%m/%Y')}", 0, 1, 'R')
    pdf.cell(col_width, 7, f"Tipologia: {pratica}", 0)
    pdf.cell(col_width, 7, f"Potenza Contrattuale: {p_new} kW", 0, 1, 'R')
    pdf.cell(col_width, 7, f"Tensione: {t_new}", 0)
    pdf.cell(col_width, 7, f"Potenza Disponibile (Pd): {p_new*f_new:.2f} kW", 0, 1, 'R')
    
    pdf.ln(10)
    
    # 3. Tabella Riepilogo Costi
    pdf.set_fill_color(0, 180, 216) # Azzurro Polis
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(135, 10, " DESCRIZIONE DETTAGLIATA", 1, 0, 'L', True)
    pdf.cell(55, 10, " IMPORTO", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    
    # Voci dinamiche
    voci = [
        (f"Quota Potenza TIC ({p_new*f_new:.2f} kW disp.)", f"{c_tec:.2f} EUR"),
        ("Oneri Amministrativi (Istruttoria Distributore)", f"{TIC_2026['ISTRUTTORIA']:.2f} EUR")
    ]
    if c_pass > 0:
        voci.append(("Contributo Passaggio Tensione BT/MT", f"{c_pass:.2f} EUR"))
    if applica_gestione:
        voci.append(("Oneri Gestione pratica", f"{c_gest:.2f} EUR"))
    
    for desc, imp in voci:
        pdf.cell(135, 10, f" {desc}", 1)
        pdf.cell(55, 10, f" {imp}", 1, 1, 'R')
        
    # 4. Totali
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
    
    # 5. Piè di pagina
    pdf.set_y(-60)
    pdf.set_text_color(100, 100, 100)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, "Note Tecniche: Il calcolo della potenza disponibile include la franchigia del 10% per forniture in BT fino a 30kW. I costi sono basati sulle tabelle TIC ARERA 2026.")
    
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(95, 10, "Firma per Accettazione Cliente", 0, 0, 'L')
    pdf.cell(95, 10, "Timbro e Firma PolisEnergia", 0, 1, 'R')
    
    # Restituisce il PDF in formato byte
    return pdf.output(dest='S').encode('latin-1')
