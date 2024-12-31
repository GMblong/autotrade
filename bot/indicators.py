from modules import pd, np, requests, logging, retry, stop_after_attempt, wait_exponential, timedelta, ThreadPoolExecutor
from fetcher import fetcher

def validate_input(*args):
    for data in args:
        if not isinstance(data, (list, pd.Series)):
            raise ValueError("Data harus berupa list atau pd.Series")
        if len(data) == 0:
            raise ValueError("Data tidak boleh kosong")
        if any(x is None or np.isnan(x) for x in data):  # Cek jika ada data tidak valid
            raise ValueError("Data mengandung nilai None atau NaN")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_data_for_day(end_time, day_offset):
    try:
        current_time = fetcher.get_ntp_time(url='https://binomo1.com/trading') - timedelta(days=day_offset)
        formatted_time = current_time.strftime('%Y-%m-%dT00:00:00')
        url = fetcher.get_price_url(formatted_time=formatted_time)
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Log data yang diterima
        logging.debug(f"Data diterima dari API: {data}")

        if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
            logging.info(f"Data berhasil diambil untuk {formatted_time}.")
            return data['data']
        else:
            logging.error(f"Data kosong atau format tidak valid untuk {formatted_time}: {data}")
            return []
    except requests.RequestException as e:
        logging.error(f"Error mengambil data harga untuk {formatted_time}: {e}")
        raise


def fetch_historical_data(days=7):
    end_time = fetcher.get_ntp_time(url='https://binomo1.com/trading')
    all_close_prices, all_high_prices, all_low_prices, all_open_prices = [], [], [], []

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(lambda day: safe_execute(fetch_data_for_day, end_time, day), range(days)))

    for day_data in results:
        if day_data:
            for entry in day_data:
                high = entry.get('high')
                low = entry.get('low')
                close = entry.get('close')
                open_price = entry.get('open')

                # Validasi setiap atribut harga
                if high is None or low is None or close is None or open_price is None:
                    logging.warning(f"Data tidak valid ditemukan: {entry}")
                    continue

                # Tambahkan ke list jika valid
                all_high_prices.append(high)
                all_low_prices.append(low)
                all_close_prices.append(close)
                all_open_prices.append(open_price)

    return all_close_prices, all_high_prices, all_low_prices, all_open_prices

def safe_execute(func, *args, **kwargs):
    try:
        logging.info(f"Menjalankan fungsi {func.__name__} dengan argumen: {args}, {kwargs}")
        result = func(*args, **kwargs)
        if result is None or len(result) == 0:
            logging.warning(f"Fungsi {func.__name__} mengembalikan hasil kosong atau None.")
        return result
    except Exception as e:
        logging.error(f"Error di fungsi {func.__name__}: {e}")
        return None  # Pengembalian default yang lebih aman

def calculate_ma(prices, window=3):
    validate_input(prices)
    prices = pd.Series(prices)
    if len(prices) < window:
        logging.warning(f"Not enough data points to calculate MA with window={window}. Returning None.")
        return [None] * len(prices)
    return prices.rolling(window=window).mean().tolist()

def calculate_rsi(prices, window=14):
    validate_input(prices)
    prices = pd.Series(prices)
    if len(prices) < window:
        logging.warning(f"Not enough data points to calculate RSI with window={window}. Returning None.")
        return [None] * len(prices)
    delta = prices.diff(1)
    gain = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.clip(0, 100).tolist()

def calculate_roc(prices, window=3):
    validate_input(prices)
    prices = pd.Series(prices)
    if len(prices) < window:
        logging.warning(f"Not enough data points to calculate ROC with window={window}. Returning None.")
        return [None] * len(prices)
    roc = prices.pct_change(periods=window) * 100
    return roc.tolist()

def calculate_williams_r(prices, high_prices, low_prices, window=7):
    validate_input(prices, high_prices, low_prices)
    prices = pd.Series(prices)
    if len(prices) < window or len(high_prices) < window or len(low_prices) < window:
        logging.warning(f"Not enough data points to calculate Williams %R with window={window}. Returning None.")
        return [None] * len(prices)
    high = pd.Series(high_prices).rolling(window=window).max()
    low = pd.Series(low_prices).rolling(window=window).min()
    williams_r = -100 * (high - prices) / (high - low)
    return williams_r.tolist()

def calculate_momentum(prices, window=3):
    validate_input(prices)
    prices = pd.Series(prices)
    if len(prices) < window:
        logging.warning(f"Not enough data points to calculate Momentum with window={window}. Returning None.")
        return [None] * len(prices)
    momentum = prices.diff(window)
    return momentum.tolist()

def calculate_macd(prices, slow=13, fast=6, signal=9):
    validate_input(prices)
    prices = pd.Series(prices)
    if len(prices) < slow:
        logging.warning(f"Not enough data points to calculate MACD with slow={slow}. Returning None.")
        return [None] * len(prices), [None] * len(prices)
    exp1 = prices.ewm(span=fast, adjust=False).mean()
    exp2 = prices.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd.tolist(), signal_line.tolist()

def calculate_bollinger_bands(prices, window=10, num_std=2):
    validate_input(prices)
    prices = pd.Series(prices)
    if len(prices) < window:
        logging.warning(f"Not enough data points to calculate Bollinger Bands with window={window}. Returning None.")
        return [None] * len(prices), [None] * len(prices), [None] * len(prices)
    rolling_mean = prices.rolling(window=window).mean()
    rolling_std = prices.rolling(window=window).std()
    upper_band = rolling_mean + (rolling_std * num_std)
    lower_band = rolling_mean - (rolling_std * num_std)
    return rolling_mean.tolist(), upper_band.tolist(), lower_band.tolist()

def calculate_atr(high_prices, low_prices, close_prices, window=5):  # Window 5 untuk 5 menit
    validate_input(high_prices, low_prices, close_prices)
    if len(high_prices) < window or len(low_prices) < window or len(close_prices) < window:
        logging.warning(f"Not enough data points to calculate ATR with window={window}. Returning None.")
        return [None] * len(close_prices)
    high = pd.Series(high_prices)
    low = pd.Series(low_prices)
    close = pd.Series(close_prices)
    high_low = high - low
    high_close = abs(high - close.shift())
    low_close = abs(low - close.shift())
    true_range = np.maximum(np.maximum(high_low, high_close), low_close)
    atr = true_range.rolling(window=window).mean()
    return atr.tolist()


def calculate_parabolic_sar(high_prices, low_prices, close_prices, af=0.02, max_af=0.2, initial_trend='up'):
    validate_input(high_prices, low_prices, close_prices)
    high = pd.Series(high_prices)
    low = pd.Series(low_prices)
    close = pd.Series(close_prices)
    if len(high) == 0 or len(low) == 0 or len(close) == 0:
        logging.warning("Insufficient data to calculate Parabolic SAR. Returning None.")
        return [None] * len(close)
    psar = [low[0] if initial_trend == 'up' else high[0]]
    uptrend = (initial_trend == 'up')
    ep = high[0] if uptrend else low[0]
    af = af
    for i in range(1, len(close)):
        prev_psar = psar[-1]
        new_psar = prev_psar + af * (ep - prev_psar)
        if uptrend:
            new_psar = min(new_psar, low[i - 1], low[i])
            if low[i] < new_psar:
                uptrend = False
                ep = low[i]
                af = 0.02
        else:
            new_psar = max(new_psar, high[i - 1], high[i])
            if high[i] > new_psar:
                uptrend = True
                ep = high[i]
                af = 0.02
        if uptrend and high[i] > ep:
            ep = high[i]
            af = min(af + 0.02, max_af)
        elif not uptrend and low[i] < ep:
            ep = low[i]
            af = min(af + 0.02, max_af)
        psar.append(new_psar)
    return psar

def calculate_adx(high_prices, low_prices, close_prices, window=7):
    validate_input(high_prices, low_prices, close_prices)
    if len(high_prices) < window or len(low_prices) < window or len(close_prices) < window:
        logging.warning(f"Not enough data points to calculate ADX with window={window}. Returning None.")
        return [None] * len(close_prices)
    high = pd.Series(high_prices)
    low = pd.Series(low_prices)
    close = pd.Series(close_prices)
    tr = np.maximum(high - low, np.maximum(abs(high - close.shift()), abs(low - close.shift())))
    dm_plus = np.where((high - high.shift()) > (low.shift() - low), np.maximum(high - high.shift(), 0), 0)
    dm_minus = np.where((low.shift() - low) > (high - high.shift()), np.maximum(low.shift() - low, 0), 0)
    tr_smooth = pd.Series(tr).rolling(window).sum()
    dm_plus_smooth = pd.Series(dm_plus).rolling(window).sum()
    dm_minus_smooth = pd.Series(dm_minus).rolling(window).sum()
    di_plus = 100 * dm_plus_smooth / tr_smooth
    di_minus = 100 * dm_minus_smooth / tr_smooth
    dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
    adx = dx.rolling(window).mean()
    return adx.tolist()