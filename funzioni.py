import yfinance as yf
import pandas as pd
import pandas_ta as ta
import matplotlib.pyplot as plt
import pandas as pd
import warnings
import sys
#import streamlit as st
def carica_dati(ticker, start_date, end_date):
    """
    Scarica i dati storici, calcola gli indicatori e pulisce le colonne.
    """
    # 1. Calcoliamo un buffer di 40 giorni
    buffer_start = (pd.to_datetime(start_date) - pd.Timedelta(days=40)).strftime('%Y-%m-%d')

    # 2. Download
    df = yf.download(ticker, start=buffer_start, end=end_date, auto_adjust=True, progress=False)

    # 3. Pulizia MultiIndex (Fondamentale per versioni recenti di yfinance)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 4. Controllo dati vuoti (Gestito PRIMA di calcolare gli indicatori)
    if df.empty:
        print(f"Errore: Nessun dato scaricato per {ticker}.")
        return None # Ritorna None invece di un DF vuoto per una gestione errori più pulita

    # 5. Calcolo indicatori
    # IMPORTANTE: ta.bbands restituisce un DataFrame.
    # Assicuriamoci che i nomi delle colonne siano puliti (spesso ta aggiunge suffissi)
    bb = ta.bbands(df['Close'], length=20, std=2)
    df = pd.concat([df, bb], axis=1)
    df['RSI'] = ta.rsi(df['Close'], length=14)

    # 6. Ritorno del DF tagliato al periodo reale (Opzionale ma consigliato)
    # Se vuoi che il DF parta esattamente da 'start_date' senza il buffer di 40gg:
    return df.loc[start_date:]



def is_rimbalzo(df, index):
  """
  Versione sicura: include controlli per divisione per zero e dati mancanti.
  """
    # Se siamo troppo vicini all'inizio del dataframe, non abbiamo dati
    # sufficienti per calcolare la media dei volumi
  if index < 20:
      return False

  try:
      # 1. Condizioni Base
      price = df.iloc[index]['Close']
      bb_col = [c for c in df.columns if c.startswith('BBL')][0]
      bb_low = df.iloc[index][bb_col]
      rsi = df.iloc[index]['RSI']
      cond_base = (price < bb_low) and (rsi < 35)

      #2. Condizioni MACD
      #hist_col = [c for c in df.columns if c.startswith('MACDh')][0]
      #hist = df.iloc[index][hist_col]
      #hist_prev = df.iloc[index-1][hist_col]
      cond_macd =1 #  (hist > hist_prev)

      # 3. Condizione Volumi con controllo sicurezza
      volume_corrente = df.iloc[index]['Volume']
      media_volumi = df.iloc[index-20:index]['Volume'].mean()

        # Gestione divisione per zero o media nulla
      if media_volumi == 0 or pd.isna(media_volumi):
          return False

      cond_volumi =  (volume_corrente > media_volumi)

      return cond_base and cond_macd and cond_volumi

  except (IndexError, KeyError, ValueError, ZeroDivisionError):
      # Cattura qualsiasi errore di calcolo (es. divisione per zero)
      return False

# # --- 3. FUNZIONE ESTRAZIONE DATE ---

def ottieni_date_rimbalzo(df, start_date, end_date, cooling_off=10):
  """
  Trova le date in cui si attivano i segnali di rimbalzo,
  filtrando gli eventi consecutivi (Signal Clustering).

  giorni_pausa (cooling_off): numero di candele successive da ignorare
                              dopo che un segnale è stato accettato.
    """
    # 1. Tagliamo il DataFrame sul periodo richiesto per l'analisi
  df_periodo = df.loc[start_date:end_date]

  date_segnali_pulite = []
  ultima_posizione_valida = -999  # Valore fittizio iniziale molto basso

  # 2. Cicliamo su tutte le righe del periodo selezionato
  for i in range(len(df_periodo)):
      # Troviamo la data effettiva della riga corrente
      data_corrente = df_periodo.index[i]

      # Per usare la funzione 'is_rimbalzo', dobbiamo passare l'indice
      # riferito al DataFrame ORIGINALE (df), non a quello tagliato!
      posizione_nel_df_originale = df.index.get_loc(data_corrente)

      # 3. Controlliamo se la riga soddisfa i criteri tecnici (RSI, Bollinger, MACD, Volumi)
      if is_rimbalzo(df, posizione_nel_df_originale):

          # 4. FILTRO CONSECUTIVI: Controlliamo se sono passati abbastanza giorni dall'ultimo segnale
          if (posizione_nel_df_originale - ultima_posizione_valida) >= cooling_off:
              # Trasformiamo la data in stringa 'YYYY-MM-DD' prima di salvarla
              date_segnali_pulite.append(data_corrente.strftime('%Y-%m-%d'))
              # Aggiorniamo il marcatore del tempo con l'indice attuale
              ultima_posizione_valida = posizione_nel_df_originale

  return date_segnali_pulite




#############OLD

# def ottieni_date_rimbalzo(df, start_date, end_date):
#     date_rimbalzo = []
#     giorni = pd.date_range(start=start_date, end=end_date, freq='B')

#     for d in giorni:
#         if d not in df.index:
#             idx_pos = df.index.get_indexer([d], method='nearest')[0]
#             data_corrente = df.index[idx_pos]
#         else:
#             data_corrente = d

#         if is_rimbalzo(df, df.index.get_loc(data_corrente)):
#             date_rimbalzo.append(data_corrente.strftime('%Y-%m-%d'))

#     return sorted(list(set(date_rimbalzo))) # Rimuove duplicati e ordina

# #Analisi valore giorni ottimali

def trova_giorni_ottimali(df, elenco_date, range_test=(3, 45)):
    """
    Testa i giorni di holding e restituisce:
    1. Il miglior giorno (int)
    2. La miglior performance (float)
    3. La tabella con TUTTI i risultati storici per il grafico (DataFrame)
    """
    # Se non ci sono segnali, restituiamo valori a zero e una tabella vuota strutturata bene
    if not elenco_date or len(elenco_date) == 0:
        return 0, 0.0, pd.DataFrame(columns=['giorni', 'media'])

    miglior_giorno = 0
    miglior_performance = -999.0
    elenco_date = pd.to_datetime(elenco_date)

    # 🌟 Lista per raccogliere i dati di ogni singolo giorno per il grafico
    storico_grafico = []

    for giorni in range(range_test[0], range_test[1] + 1):
        rendimenti = []

        for data_segnale in elenco_date:
            try:
                if data_segnale in df.index:
                    idx_inizio = df.index.get_loc(data_segnale)
                    idx_fine = idx_inizio + giorni

                    if idx_fine < len(df):
                        prezzo_ingresso = df['Close'].iloc[idx_inizio]
                        prezzo_uscita = df['Close'].iloc[idx_fine]

                        if pd.notna(prezzo_ingresso) and pd.notna(prezzo_uscita) and prezzo_ingresso > 0:
                            rendimento = ((prezzo_uscita - prezzo_ingresso) / prezzo_ingresso) * 100
                            rendimenti.append(float(rendimento))
            except Exception:
                continue

        if len(rendimenti) > 0:
            media = sum(rendimenti) / len(rendimenti)

            # 🌟 Salviamo il risultato del giorno corrente nella lista per il grafico
            storico_grafico.append({'giorni': giorni, 'media': media})

            if media > miglior_performance:
                miglior_performance = media
                miglior_giorno = giorni

    # 🌟 Trasformiamo la lista in un DataFrame perfetto per Plotly
    df_optimal_results = pd.DataFrame(storico_grafico)

    if miglior_giorno == 0 or miglior_performance == -999.0:
        return 0, 0.0, df_optimal_results

    return miglior_giorno, miglior_performance, df_optimal_results

#Analisi trend rialzista
def is_trend_rialzista(df, i):
  """
  Ritorna True se il titolo soddisfa i criteri quantitativi
  di un forte trend rialzista alla riga 'i'.
  """
  # Prendi i valori alla riga corrente
  prezzo_chiusura = df.iloc[i]['Close']
  sma_50 = df.iloc[i]['SMA_50']
  sma_200 = df.iloc[i]['SMA_200']

  # Assicurati di aver calcolato ADX, +DI e -DI nel tuo df
  adx = df.iloc[i]['ADX']
  piu_di = df.iloc[i]['PLUS_DI']
  meno_di = df.iloc[i]['MINUS_DI']

  # CONDIZIONI DEL TREND RIALZISTA:
  # 1. Il prezzo è sopra entrambe le medie
  condizione_medie = prezzo_chiusura > sma_50 > sma_200

  # 2. Esiste un trend forte (ADX > 25) e i compratori dominano (+DI > -DI)
  condizione_forza = (adx > 25) and (piu_di > meno_di)

  # Se entrambe sono vere, il titolo è in un trend rialzista perfetto
  if condizione_medie and condizione_forza:
      return True
  return False


  #Analisi golden cross

def analizza_stato_golden_cross(df):
  """
  Verifica da quanti giorni di borsa si è verificato l'ultimo Golden Cross
  e se è tuttora attivo.

  Ritorna una tupla: (giorni_passati, is_attivo_oggi)
  Se non viene trovato alcun incrocio, ritorna (-1, False)
  """
  # 1. Calcola le medie mobili se non sono già presenti nel DataFrame
  if 'SMA_50' not in df.columns:
      df['SMA_50'] = df['Close'].rolling(window=50).mean()
  if 'SMA_200' not in df.columns:
      df['SMA_200'] = df['Close'].rolling(window=200).mean()

  # Rimuoviamo le righe iniziali con i NaN per evitare errori di calcolo
  df_pulito = df.dropna(subset=['SMA_50', 'SMA_200'])
  tot_righe = len(df_pulito)

  if tot_righe < 2:
      return -1, False  # Non abbastanza dati per analizzare un incrocio

  # Verifica lo stato attuale all'ultima riga (oggi)
  stato_attuale_sopra = df_pulito['SMA_50'].iloc[-1] > df_pulito['SMA_200'].iloc[-1]

  # 2. Scorriamo il DataFrame al contrario (dall'ultima riga verso il passato)
  # Partiamo dalla penultima riga (tot_righe - 1) fino alla seconda riga (indice 1)
  for i in range(tot_righe - 1, 0, -1):

      # Condizione di INCROCIO RIALZISTA (Golden Cross):
      # Alla riga 'i' la 50 è SOPRA la 200, ma alla riga precedente 'i-1' era SOTTO o UGUALE
      oggi_sopra = df_pulito['SMA_50'].iloc[i] > df_pulito['SMA_200'].iloc[i]
      ieri_sotto = df_pulito['SMA_50'].iloc[i-1] <= df_pulito['SMA_200'].iloc[i-1]

      if oggi_sopra and ieri_sotto:
          # Abbiamo trovato il Golden Cross più recente!
          # Calcoliamo la distanza in righe (giorni di borsa) tra quel giorno e l'ultimo giorno disponibile
          giorni_passati = (tot_righe - 1) - i

          return giorni_passati, stato_attuale_sopra

  # Se il ciclo finisce senza trovare incroci
  return -1, False


def screener_golden_cross_recente(lista_ticker, entro_giorni=3):
  """
  Scansiona una lista di titoli e restituisce quelli che hanno avuto
  un Golden Cross (SMA 50 > SMA 200) negli ultimi X giorni.
  """
  risultati = []
  totale = len(lista_ticker)

  print(f"Inizio scansione Golden Cross su {totale} titoli (Finestra: {entro_giorni} gg)...")

  # Dividiamo in blocchi da 50 per evitare blocchi da Yahoo Finance
  dimensione_blocco = 50
  blocchi = [lista_ticker[i:i + dimensione_blocco] for i in range(0, totale, dimensione_blocco)]

  for idx_b, blocco in enumerate(blocchi):
      sys.stdout.write(f"\rAnalisi blocco {idx_b+1}/{len(blocchi)}... ")
      sys.stdout.flush()

      try:
          # Scarichiamo lo storico necessario (almeno 300 giorni per avere una SMA 200 stabile)
          dati = yf.download(blocco, period="2y", progress=False, group_by='ticker')

          for ticker in blocco:
              # Gestione scaricamento singolo o multi-ticker
              if ticker not in dati.columns.levels[0]: continue
              df_tick = dati[ticker].dropna()

              if len(df_tick) < 200: continue

              # Calcolo Medie
              sma50 = df_tick['Close'].rolling(window=50).mean()
              sma200 = df_tick['Close'].rolling(window=200).mean()

              # Verifichiamo gli ultimi X giorni
              # Partiamo dall'ultima riga e andiamo a ritroso
              for i in range(1, entro_giorni + 1):
                  # Indici per il controllo (oggi vs ieri relativo)
                  idx_oggi = -i
                  idx_ieri = -(i + 1)

                  try:
                      # Condizione Golden Cross:
                      # Oggi la 50 è sopra la 200, ieri era sotto o uguale
                      if (sma50.iloc[idx_oggi] > sma200.iloc[idx_oggi]) and \
                          (sma50.iloc[idx_ieri] <= sma200.iloc[idx_ieri]):

                          data_cross = df_tick.index[idx_oggi]
                          giorni_fa = i - 1 # 0 se è successo oggi

                          risultati.append({
                              "Ticker": ticker,
                              "Data Cross": data_cross.strftime('%Y-%m-%d'),
                              "Giorni fa": giorni_fa,
                              "Prezzo Attuale": df_tick['Close'].iloc[-1]
                          })
                          break # Trovato l'incrocio più recente per questo ticker, passa al prossimo
                  except IndexError:
                      continue

      except Exception as e:
          print(f"\nErrore nel blocco {idx_b}: {e}")
          continue

  print("\n[OK] Scansione completata.")
  return pd.DataFrame(risultati)
def ottieni_componenti_indice(indice="SP500"):
    """
    Scarica la lista ufficiale dei ticker.
    Usa un CSV pubblico su GitHub per lo S&P 500 per evitare che i server
    di Google Colab vengano bloccati per IP da Wikipedia (HTTPError).
    """
    if indice == "SP500":
        # Archivio CSV pubblico, costantemente aggiornato e libero da blocchi IP
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"

        try:
            # Leggiamo direttamente il CSV online con Pandas
            df_sp = pd.read_csv(url)

            # Puliamo i ticker formattando i punti in trattini (es. BRK.B diventa BRK-B)
            ticker_list = df_sp['Symbol'].str.replace('.', '-', regex=False).tolist()
            return ticker_list

        except Exception as e:
            print(f"Errore nel recupero dello S&P 500 da GitHub: {e}")
            return []

    elif indice == "FTSEMIB":
        # Per il mercato italiano la lista è interna e non richiede chiamate di rete
        ticker_mib = [
            "A2A.MI", "AMP.MI", "AZM.MI", "BAMI.MI", "BCA.MI", "BG.MI", "BMED.MI",
            "BMPS.MI", "BPER.MI", "BRN.MI", "CPR.MI", "DIA.MI", "ENEL.MI", "ENI.MI",
            "ERG.MI", "FBK.MI", "G.MI", "HER.MI", "INW.MI", "ISP.MI", "IVG.MI",
            "LDO.MI", "MB.MI", "MONC.MI", "NEXI.MI", "PIRC.MI", "PRY.MI", "PST.MI",
            "RACE.MI", "REC.MI", "SPM.MI", "SRG.MI", "STLAM.MI", "STMMI.MI", "TEN.MI",
            "TIT.MI", "TRN.MI", "UCG.MI", "UNIP.MI", "VOW.MI"
        ]
        return ticker_mib
    return []

def individua_top_losers(lista_ticker, lookback_giorni=10, quantita=10):
    """
    Analizza l'intero indice a blocchi di 50 titoli per evitare blocchi HTTP da Yahoo Finance,
    e isola i X titoli peggiori.
    """
    import yfinance as yf
    print(f"Scansione in corso su {len(lista_ticker)} titoli dell'indice...")

    # Dividiamo i 500 titoli in blocchi da 50
    dimensione_blocco = 50
    blocchi_ticker = [lista_ticker[i:i + dimensione_blocco] for i in range(0, len(lista_ticker), dimensione_blocco)]

    df_chiusure_totale = pd.DataFrame()

    # Scarichiamo un blocco alla volta
    for idx, blocco in enumerate(blocchi_ticker, 1):
        try:
            # Scarica il mini-blocco attuale
            df_blocco = yf.download(blocco, period="30d", progress=False)['Close']

            # Se il blocco ha dati, lo uniamo al DataFrame principale
            if not df_blocco.empty:
                df_chiusure_totale = pd.concat([df_chiusure_totale, df_blocco], axis=1)
        except Exception as e:
            # Se un blocco fallisce per vie di rete, passa oltre senza far crashare l'intero programma
            continue

    if df_chiusure_totale.empty:
        print("Errore critico: Impossibile recuperare dati da Yahoo Finance per l'intero indice.")
        return []

    # Pulizia colonne vuote
    df_chiusure_totale = df_chiusure_totale.dropna(how='all', axis=1)

    # Calcolo variazione percentuale degli ultimi X giorni
    prezzo_oggi = df_chiusure_totale.iloc[-1]
    prezzo_passato = df_chiusure_totale.iloc[-lookback_giorni]
    performance = ((prezzo_oggi - prezzo_passato) / prezzo_passato) * 100

    # Classifica finale dei peggiori
    classifica = pd.DataFrame(performance, columns=['Perf']).sort_values(by='Perf')
    classifica = classifica.dropna()

    return classifica.head(quantita).index.tolist()
# --- 4. FUNZIONE PERFORMANCE ---
def analizza_performance_segnale(df, data_segnale, giorni_holding=30):
    target_dt = pd.to_datetime(data_segnale)
    idx_pos = df.index.get_indexer([target_dt], method='nearest')[0]

    prezzo_entrata = df.iloc[idx_pos]['Close']
    if idx_pos + giorni_holding < len(df):
        prezzo_uscita = df.iloc[idx_pos + giorni_holding]['Close']
    else:
        prezzo_uscita = df.iloc[-1]['Close']

    return ((prezzo_uscita - prezzo_entrata) / prezzo_entrata) * 100

# esegue backtest su un periodo selezionato
def calcola_backtest(ticker, start_date, end_date, giorni_holding=5):
    # 1. Download e Preparazione
    df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    # 2. Indicatori
    bb = ta.bbands(df['Close'], length=20, std=2)
    df = pd.concat([df, bb], axis=1)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    bb_lower = [c for c in df.columns if 'BBL' in c][0]

    # 3. Ciclo di Backtest
    profitti = []
    print(f"\n--- Backtest: {ticker} (Holding: {giorni_holding}gg) ---")

    for i in range(20, len(df) - giorni_holding):
        if df.iloc[i]['Close'] < df.iloc[i][bb_lower] and df.iloc[i]['RSI'] < 35:
            # --- RICHIAMO LA FUNZIONE SPECIALIZZATA ---
            rendimento = analizza_performance_segnale(df, i, giorni_holding)
            profitti.append(rendimento)

            data = df.index[i].strftime('%Y-%m-%d')
            print(f"Data: {data} | Rendimento: {rendimento:+.2f}%")

    if profitti:
        print(f"\n>>> RISULTATO: Media su {len(profitti)} trade: {sum(profitti)/len(profitti):.2f}%")
    else:
        print("Nessun segnale trovato.")
