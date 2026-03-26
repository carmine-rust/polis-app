import streamlit as st
import math, os
from datetime import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# --- CONFIGURAZIONE ESTETICA ---
BRAND = {
    "BLU_DEEP": "#001d3d",
    "BLU_POLIS": "#003566",
    "AZZURRO": "#00b4d8",
    "ORO": "#ffc300",
    "BIANCO": "#ffffff",
    "IBAN": "IT80P0103015200000007044056",
    "BANCA": "Monte dei Paschi di Siena"
}

TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "PASS_BT_MT": 494.83, "DIST_FISSA": 209.62, 
    "DIST_EXTRA": 105.08, "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 452.72, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88 
}

# --- STILE CSS PERSONALIZZATO ---
st.set_page_config(page_title="PolisEnergia Suite", page_icon="⚡", layout="wide")

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] {{ font-family: 'Lato', sans-serif; }}
    
    .main {{ background-color: {BRAND['BLU_DEEP']}; }}
    
    /* Box del Totale */
    .total-card {{
        background: linear-gradient(135deg, {BRAND['BLU_POLIS']} 0%, #000814 100%);
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid {BRAND['AZZURRO']};
        color: white;
        text-align: center;
        margin-bottom: 20px;
    }}
    
    .total-amount {{ font-size: 45px; font-weight: 700; color: {BRAND['AZZURRO']}; }}
    
    /* Bottoni */
    .stButton>button {{
        background-color: {BRAND['AZZURRO']};
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 20px;
        transition: all 0.3s;
    }}
    .stButton>button:hover {{ background-color: {BRAND['ORO']}; color: {BRAND['BLU_DEEP']}; }}
    </style>
    """, unsafe_content_allowed=True)

# --- LOGICA DI CALCOLO ---
def esegui_calcoli(uso, pratica, t_att, t_new, p_att, p_new, dist_m, tipo_spost):
    # Quota Tecnica
    if pratica == "Spostamento Misuratore":
        c_tec = TIC_2026["SPOST_ENTRO_10"] if "Entro" in tipo_spost else TIC_2026["SPOST_OLTRE_10"]
    else:
        px = TIC_2026["MT"] if "MT" in t_new else (TIC_2026["DOM_LE6"] if ("Domestico" in uso and p_new <= 6) else TIC_2026["BT_ALTRI"])
        f = 1.0 if ("MT" in t_new or p_new > 34) else 1.1
        if pratica == "Nuova Connessione":
            c_tec = (p_new * f * px) + TIC_2026["DIST_FISSA"] + (math.ceil(dist_m/100) * TIC_2026["DIST_EXTRA"])
        else:
            c_tec = (p_new - p_att) * f * px
    
    c_pass = TIC_2026["PASS_BT_MT"] if ("BT" in t_att and "MT" in t_new) else 0
    c_gest = (max(0, c_tec) + c_pass + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10
    tot_imp = max(0, c_tec) + c_pass + c_gest + TIC_2026["ISTRUTTORIA"]
    
    is_split = "P.A." in uso
    aliq = 0.22 if is_split else (0.10 if "10%" in uso else (0.22 if "22%" in uso else 0.0))
    tot_iva = tot_imp * aliq
    
    return {
        "tec": c_tec, "pass": c_pass, "gest": c_gest, "istr": TIC_2026["ISTRUTTORIA"],
        "imp": tot_imp, "iva": tot_iva, "aliq": int(aliq*100), "is_split": is_split,
        "tot": tot_imp if is_split else tot_imp + tot_iva
    }

# --- INTERFACCIA ---
with st.sidebar:
    st.image("https://via.placeholder.com/200x80?text=POLIS+ENERGIA", use_container_width=True) # Sostituire con URL logo reale
    st.title("Menu Rapido")
    uso = st.selectbox("Regime Fiscale", ["Domestico (IVA 10%)", "Altri Usi (IVA 22%)", "P.A. (Split Payment)", "Esente (IVA 0%)"])
    pratica = st.selectbox("Pratica", ["Nuova Connessione", "Aumento di Potenza", "Subentro con Modifica", "Spostamento Misuratore"])
    
    st.divider()
    st.info("I calcoli seguono le tabelle TIC 2026 vigenti.")

# Layout Principale
col_main, col_res = st.columns([2, 1])

with col_main:
    tab1, tab2 = st.tabs(["📝 Dati Anagrafici", "⚙️ Parametri Tecnici"])
    
    with tab1:
        nome = st.text_input("Intestatario / Ragione Sociale").upper()
        fornitura = st.text_input("Indirizzo di Fornitura").upper()
        pod = st.text_input("Codice POD (14 caratteri)").upper()
    
    with tab2:
        c1, c2 = st.columns(2)
        t_att = c1.selectbox("Tensione Attuale", ["BT (Bassa Tensione)", "MT (Media Tensione)"])
        opzioni_t_new = ["BT (Bassa Tensione)"] if "Domestico" in uso else ["BT (Bassa Tensione)", "MT (Media Tensione)"]
        t_new = c2.selectbox("Tensione Richiesta", opzioni_t_new)
        
        p_att, p_new, dist_m, tipo_spost = 0.0, 0.0, 0, ""
        
        if pratica == "Spostamento Misuratore":
            tipo_spost = st.radio("Distanza", ["Entro 10 metri", "Oltre 10 metri"])
        else:
            p1, p2 = st.columns(2)
            if "Nuova" not in pratica:
                p_att = p1.number_input("Potenza Attuale (kW)", min_value=0.0, step=0.5, value=3.0)
            p_new = p2.number_input("Potenza Richiesta (kW)", min_value=0.0, step=0.5, value=6.0)
            if pratica == "Nuova Connessione":
                dist_m = st.number_input("Distanza oltre 200m (metri)", min_value=0, step=10)

# Calcolo istantaneo
res = esegui_calcoli(uso, pratica, t_att, t_new, p_att, p_new, dist_m, tipo_spost)

with col_res:
    st.markdown(f"""
        <div class="total-card">
            <p style="margin:0; text-transform:uppercase; font-size:12px; letter-spacing:1px;">Totale Preventivato</p>
            <div class="total-amount">{res['tot']:.2f} €</div>
            <p style="font-size:14px; opacity:0.8;">{"IVA Split Payment" if res['is_split'] else f"IVA {res['aliq']}% Inclusa"}</p>
        </div>
    """, unsafe_content_allowed=True)
    
    with st.expander("Vedi Dettaglio Costi"):
        st.write(f"Quota TIC: {res['tec']:.2f} €")
        st.write(f"Passaggio BT/MT: {res['pass']:.2f} €")
        st.write(f"Gestione Polis (10%): {res['gest']:.2f} €")
        st.write(f"Istruttoria: {res['istr']:.2f} €")
    
    if st.button("🚀 GENERA PDF UFFICIALE"):
        if not nome or not pod:
            st.error("Dati anagrafici incompleti!")
        else:
            # Logica PDF qui (stessa delle versioni precedenti)
            st.toast("PDF in fase di generazione...")