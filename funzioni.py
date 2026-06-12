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
    Testa i giorni di holding e trova quello con la performance media migliore.
    Previene il ZeroDivisionError se l'elenco dei rendimenti è vuoto.
    """
    # 1. Protezione iniziale: se non ci sono proprio segnali in partenza
    if not elenco_date or len(elenco_date) == 0:
        return 0, 0.0

    miglior_giorno = 0
    miglior_performance = -999.0
    elenco_date = pd.to_datetime(elenco_date)

    for giorni in range(range_test[0], range_test[1] + 1):
        rendimenti = []
        
        for data_segnale in elenco_date:
            try:
                if data_segnale in df.index:
                    # Trova la posizione numerica della riga della data
                    idx_inizio = df.index.get_loc(data_segnale)
                    idx_fine = idx_inizio + giorni
                    
                    # Verifica che ci siano abbastanza giorni nel futuro per chiudere il trade
                    if idx_fine < len(df):
                        prezzo_ingresso = df['Close'].iloc[idx_inizio]
                        prezzo_uscita = df['Close'].iloc[idx_fine]
                        
                        # Gestione robusta per evitare formati strani o valori nulli
                        if pd.notna(prezzo_ingresso) and pd.notna(prezzo_uscita) and prezzo_ingresso > 0:
                            rendimento = ((prezzo_uscita - prezzo_ingresso) / prezzo_ingresso) * 100
                            rendimenti.append(float(rendimento))
            except Exception:
                continue # Salta silenziosamente eventuali anomalie su singole date
        
        # 🚨 LA MODIFICA CRUCIALE (Risolve il ZeroDivisionError):
        # Calcoliamo la media SOLO se abbiamo registrato almeno un trade valido completato
        if len(rendimenti) > 0:
            media = sum(rendimenti) / len(rendimenti)
            if media > miglior_performance:
                miglior_performance = media
                miglior_giorno = giorni
        else:
            # Se per questo specifico numero di giorni non ci sono trade completabili, salta al prossimo
            continue

    # Se alla fine del ciclo non è stato possibile completare nessun trade in nessun giorno
    if miglior_giorno == 0 or miglior_performance == -999.0:
        return 0, 0.0

    return miglior_giorno, miglior_performance

def verifica_segnale_data(ticker, data_target):
  """
  Verifica se nella data specificata si sono attivate
  le condizioni di rimbalzo per il titolo inserito.
  Format data richiesto: 'YYYY-MM-DD'
  """
  import datetime

  target_dt = pd.to_datetime(data_target)

  # 1. Calcoliamo un buffer di 90 giorni prima della data richiesta
  # per permettere il calcolo corretto di indicatori, medie e volumi
  inizio_buffer = (target_dt - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
  fine_analisi = (target_dt + datetime.timedelta(days=5)).strftime('%Y-%m-%d') # Un piccolo margine successivo

  # 2. Scarichiamo lo storico mirato
  df = carica_dati(ticker=ticker, start_date=inizio_buffer, end_date=fine_analisi)

  if df is None or df.empty:
      print(f"[{ticker}] Impossibile recuperare i dati per il periodo richiesto.")
      return False

  # 3. Gestione della data (cerca la più vicina se la borsa era chiusa)
  if target_dt not in df.index:
      idx_pos = df.index.get_indexer([target_dt], method='nearest')[0]
      data_effettiva = df.index[idx_pos]
      nota_data = f"(Data richiesta: {data_target} | Borsa chiusa -> Analizzata data disponibile più vicina: {data_effettiva.strftime('%Y-%m-%d')})"
  else:
      data_effettiva = target_dt
      nota_data = f"(Data analizzata: {data_target})"

  # 4. Troviamo la posizione numerica (indice iloc) della data effettiva
  posizione_riga = df.index.get_loc(data_effettiva)

  # 5. Eseguiamo il controllo con la tua funzione is_rimbalzo
  segnale_attivo = is_rimbalzo(df, posizione_riga)

  # 6. Output a schermo
  print(f"\n--- Verifica Segnale per {ticker} ---")
  print(nota_data)
  print(f"Prezzo di Chiusura: ${df.iloc[posizione_riga]['Close']:.2f}")
  print(f"RSI: {df.iloc[posizione_riga]['RSI']:.2f}")

  if segnale_attivo:
      print(f"🚨 SEGNALE ATTIVO! Il titolo soddisfaceva i criteri di rimbalzo in questa data.")
  else:
      print(f"❌ Nessun segnale rilevato per questa data.")

  return segnale_attivo

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
