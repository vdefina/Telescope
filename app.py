import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import io

# Importiamo le tue funzioni dal file funzioni.py
from funzioni import (
    ottieni_componenti_indice,
    individua_top_losers,
    trova_giorni_ottimali,
    ottieni_date_rimbalzo,
    screener_golden_cross_recente
)

# --- 1. CONFIGURAZIONE PAGINA (TEMA DARK & LAYOUT FLUIDO) ---
st.set_page_config(
    page_title="QuantLab Dashboard",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# --- 2. STILE CSS PERSONALIZZATO (FINTECH STYLE) ---
st.markdown("""
    <style>
        /* Sfondo principale scuro stile TradingView */
        .stApp {
            background-color: #0d1117;
            color: #c9d1d9;
        }
        /* Personalizzazione dei blocchi/card */
        .stElementContainer div[data-testid="stBlock"] {
            border-radius: 10px;
        }
        /* Stile dei pulsanti principali */
        .stButton>button {
            width: 100%;
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            color: #0d1117 !important;
            font-weight: bold;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
            color: #0d1117 !important;
        }
        /* Personalizzazione dei Titoli */
        h1, h2, h3 {
            color: #ffffff !important;
            font-family: 'Inter', sans-serif;
            font-weight: 700;
        }
        /* Gradient text per il titolo principale */
        .main-title {
            font-size: 42px;
            font-weight: 800;
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 3. BARRA LATERALE (NAVIGAZIONE APP-STYLE) ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #4facfe;'>⚡ QuantLab v2.0</h2>", unsafe_allow_html=True)
    st.markdown("---")

    # Menu di navigazione principale con icone
    menu_navigazione = st.radio(
        "MENU APPLICAZIONE",
        ["🏠 Home Dashboard", "🔥 Mean Reversion (Rimbalzi)", "📈 Trend Following (Golden Cross)"],
        index=0
    )

    st.markdown("---")
    st.markdown("### ⚙️ Impostazioni Mercato")
    scelta_indice = st.selectbox("Seleziona l'Indice di riferimento", ["SP500", "FTSEMIB"])

    st.markdown("---")
    st.markdown("### 💾 Esporta Risultati")
    excel_filename = f"Screener_Inversioni_{scelta_indice}.xlsx"
    try:
        with open(excel_filename, "rb") as file:
            st.download_button(
                label="Scarica Report Excel",
                data=file,
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except FileNotFoundError:
        st.info("Il report Excel non è ancora stato generato. Esegui uno screening per crearlo.")

    st.markdown("<br><br><br><p style='text-align: center; font-size: 12px; color: #8b949e;'>Powered by Streamlit & Plotly</p>", unsafe_allow_html=True)

# =========================================================================
# PAGINA 1: HOME DASHBOARD
# =========================================================================
if menu_navigazione == "🏠 Home Dashboard":
    st.markdown("<div class='main-title'>Benvenuto in QuantLab</div>", unsafe_allow_html=True)
    st.write("La tua stazione di controllo quantitativa per il monitoraggio e lo screening dei mercati finanziari.")

    # Creazione di card riassuntive dello stato del mercato
    col_card1, col_card2, col_card3 = st.columns(3)

    with col_card1:
        with st.container(border=True):
            st.markdown("<h4 style='color: #4facfe; margin:0;'>🌍 Focus Corrente</h4>", unsafe_allow_html=True)
            st.markdown(f"<h2 style='margin:10px 0;'>Indice: {scelta_indice}</h2>", unsafe_allow_html=True)
            st.caption("I dati vengono aggiornati in tempo reale tramite le API di Yahoo Finance.")

    with col_card2:
        with st.container(border=True):
            st.markdown("<h4 style='color: #00e676; margin:0;'>🔥 Mean Reversion</h4>", unsafe_allow_html=True)
            st.markdown("<h2 style='margin:10px 0;'>Algoritmo Pronto</h2>", unsafe_allow_html=True)
            st.caption("Scansiona i crolli e calcola matematicamente i giorni ottimali di holding.")

    with col_card3:
        with st.container(border=True):
            st.markdown("<h4 style='color: #ffb300; margin:0;'>📈 Golden Cross</h4>", unsafe_allow_html=True)
            st.markdown("<h2 style='margin:10px 0;'>Incroci 50/200</h2>", unsafe_allow_html=True)
            st.caption("Trova le inversioni strutturali di trend di lungo periodo entro 3 giorni di borsa.")

# =========================================================================
# PAGINA 2: STRATEGIA RIMBALZI
# =========================================================================
elif menu_navigazione == "🔥 Mean Reversion (Rimbalzi)":
    st.markdown("<div class='main-title'>Strategia dei Rimbalzi (Ipervenduto)</div>", unsafe_allow_html=True)

    # Sub-navigazione interna orizzontale molto pulita
    sotto_menu = st.segmented_control(
        "Seleziona la modalità operativa:",
        options=["🔍 Screener di Massa", "📊 Analisi Singolo Titolo"],
        default="🔍 Screener di Massa"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if sotto_menu == "🔍 Screener di Massa":
        with st.container(border=True):
            st.subheader("Parametri dello Screener Globale")
            c1, c2, c3 = st.columns(3)
            with c1:
                lookback = st.slider("Finestra Lookback (giorni)", 5, 20, 10)
                n_titoli = st.slider("Numero di titoli da isolare", 3, 15, 5)
            with c2:
                start_ottimizza = st.date_input("Inizio Ottimizzazione", pd.to_datetime("2021-01-01"))
            with c3:
                start_analisi = st.date_input("Inizio Analisi Reale", pd.to_datetime("2025-01-01"))

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 AVVIA SCANSIONE MERCATO"):
                with st.spinner("Scansione quantitativa dell'indice in corso..."):
                    ticker_totali = ottieni_componenti_indice(scelta_indice)
                    peggiori_ticker = individua_top_losers(ticker_totali, lookback_giorni=lookback, quantita=n_titoli)
                    st.success(f"🎯 Screening Completato! Isolate le {n_titoli} aziende peggiori: {', '.join(peggiori_ticker)}")

    else:
        with st.container(border=True):
            st.subheader("Configurazione Asset Singolo")
            c1, c2, c3 = st.columns(3)
            with c1:
                ticker_scelto = st.text_input("Inserisci il Ticker (es. AAPL, TSLA, UCG.MI)", value="AAPL").upper()
            with c2:
                data_inizio = st.date_input("Inizio Storico", pd.to_datetime("2024-01-01"))
            with c3:
                data_fine = st.date_input("Fine Storico", pd.to_datetime("2026-06-01"))

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📊 ELABORA STRATEGIA E GRAFICO"):
                with st.spinner(f"Calcolo metriche per {ticker_scelto}..."):
                    df_ticker = yf.download(ticker_scelto, start=data_inizio, end=data_fine)

                    if df_ticker.empty:
                        st.error("Nessun dato trovato per questo Ticker. Verifica il simbolo.")
                    else:
                        if isinstance(df_ticker.columns, pd.MultiIndex):
                            df_ticker.columns = df_ticker.columns.droplevel(1)

                        date_segnali = ottieni_date_rimbalzo(df_ticker, data_inizio, data_fine)

                        # Call trova_giorni_ottimali and process its DataFrame output
                        df_optimal_results = trova_giorni_ottimali(df_ticker, date_segnali, range_test=(3, 45))

                        giorni_top = 0
                        performance_top = 0.0
                        if not df_optimal_results.empty:
                            miglior_riga = df_optimal_results.loc[df_optimal_results['media'].idxmax()]
                            giorni_top = int(miglior_riga['giorni'])
                            performance_top = miglior_riga['media']

                        if giorni_top == 0:
                            st.warning(f"⚠️ Nessun segnale di rimbalzo rilevato per {ticker_scelto} in queste date.")
                        else:
                            # Box metriche affiancate dal design pulito
                            m1, m2 = st.columns(2)
                            with m1:
                                with st.container(border=True):
                                    st.metric(label="Holding Period Ottimale", value=f"{giorni_top} Giorni di Borsa")
                            with m2:
                                with st.container(border=True):
                                    st.metric(label="Rendimento Medio Atteso per Trade", value=f"+ {performance_top:.2f} %")

                            # Grafico Plotly con Template Dark coordinato
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=df_ticker.index, y=df_ticker['Close'],
                                mode='lines', name='Prezzo Chiusura',
                                line=dict(color='#4facfe', width=2)
                            ))

                            df_segnali = df_ticker[df_ticker.index.isin(date_segnali)]
                            fig.add_trace(go.Scatter(
                                x=df_segnali.index, y=df_segnali['Close'],
                                mode='markers', name='Segnale Buy (Oversold)',
                                marker=dict(color='#00e676', size=12, symbol='triangle-up', line=dict(color='black', width=1))
                            ))

                            fig.update_layout(
                                title=f"Analisi Tecnica Segnali su {ticker_scelto}",
                                template="plotly_dark",  # Sfondo scuro coordinato con l'app!
                                paper_bgcolor="#0d1117",
                                plot_bgcolor="#0d1117",
                                hovermode="x unified"
                            )
                            st.plotly_chart(fig, use_container_width=True)

                            st.subheader("Performance Media per Periodo di Holding")
                            # Bar chart for optimal results
                            bar_fig = go.Figure(data=[go.Bar(
                                x=df_optimal_results['giorni'],
                                y=df_optimal_results['media'],
                                marker_color=['#00f2fe' if g == giorni_top else '#4facfe' for g in df_optimal_results['giorni']]
                            )])
                            bar_fig.update_layout(
                                title='Rendimento Medio per Giorni di Holding',
                                xaxis_title='Giorni di Holding',
                                yaxis_title='Rendimento Medio (%)',
                                template="plotly_dark",
                                paper_bgcolor="#0d1117",
                                plot_bgcolor="#0d1117",
                                hovermode="x unified"
                            )
                            st.plotly_chart(bar_fig, use_container_width=True)

# =========================================================================
# PAGINA 3: GOLDEN CROSS
# =========================================================================
elif menu_navigazione == "📈 Trend Following (Golden Cross)":
    st.markdown("<div class='main-title'>Screener Golden Cross</div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("Filtro di Ricerca Incroci")
        st.write("Isola i titoli in cui la Media Mobile a 50 giorni ha tagliato al rialzo la Media Mobile a 200 giorni di recente.")

        giorni_finestra = st.number_input("Verifica incroci avvenuti negli ultimi (giorni di borsa):", min_value=1, max_value=10, value=3)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔍 EFFETTUA SCREENING DELLE MEDIE"):
            with st.spinner("Calcolo medie mobili a 50 e 200 giorni su tutto l'indice..."):
                ticker_totali = ottieni_componenti_indice(scelta_indice)
                df_golden = screener_golden_cross_recente(ticker_totali, entro_giorni=giorni_finestra)

                if df_golden is not None and not df_golden.empty:
                    st.success(f"🔥 Trovati {len(df_golden)} titoli in Golden Cross recente!")

                    # Tabella formattata in modo stupendo, scura e pulita
                    st.dataframe(
                        df_golden.style.format({"Prezzo Attuale": "{:.2f} $"}),
                        use_container_width=True
                    )
                else:
                    st.warning(f"Nessun titolo nel paniere {scelta_indice} ha registrato un Golden Cross negli ultimi {giorni_finestra} giorni.")
