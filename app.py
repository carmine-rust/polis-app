import streamlit as st
import math, os, random, string
from datetime import datetime
from fpdf import FPDF

# 1. Configurazione Base (Niente CSS per ora per evitare il TypeError)
st.set_page_config(page_title="PolisEnergia Suite", layout="centered")

st.title("⚡ POLIS ENERGIA")
st.write("Configuratore Tecnico Fornitura 2026")

# 2. Parametri Fissi
TIC_2026 = {
    "DOM_LE6": 62.30, "BT_ALTRI": 78.81, "MT": 62.74,
    "PASS_BT_MT": 494.83, "DIST_FISSA": 209.62, 
    "DIST_EXTRA": 105.08, "SPOST_ENTRO_10": 226.36, 
    "SPOST_OLTRE_10": 452.72, "ISTRUTTORIA": 27.42, 
    "FISSO_BASE_CALCOLO": 25.88 
}

# 3. Interfaccia Semplice
col1, col2 = st.columns(2)
with col1:
    uso = st.selectbox("Regime Fiscale", ["Domestico (IVA 10%)", "Altri Usi (IVA 22%)", "P.A. (Split Payment)"])
    pratica = st.selectbox("Tipo Pratica", ["Nuova Connessione", "Aumento di Potenza", "Spostamento Misuratore"])

with col2:
    t_att = st.selectbox("Tensione Attuale", ["BT", "MT"])
    t_new = st.selectbox("Tensione Richiesta", ["BT", "MT"])

nome = st.text_input("Intestatario").upper()
pod = st.text_input("POD").upper()

# 4. Logica di Calcolo Base
c_tec = 100.0 # Valore di test per vedere se l'app gira
c_gest = (c_tec + TIC_2026["FISSO_BASE_CALCOLO"]) * 0.10
totale = c_tec + c_gest + TIC_2026["ISTRUTTORIA"]

# 5. Visualizzazione Risultato
st.divider()
st.metric("Totale Stimato (Imponibile)", f"{totale:.2f} €")

if st.button("Genera Test"):
    st.balloons()
    st.success(f"Preventivo per {nome} calcolato correttamente!")
