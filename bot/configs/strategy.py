from modules import pd, np, optuna, os, ThreadPoolExecutor, logging, datetime, ThreadPoolExecutor, timedelta, requests
from fetcher import fetcher
from indicators import calculate_ma, calculate_rsi, calculate_macd, calculate_momentum, calculate_roc, calculate_atr, calculate_bollinger_bands, calculate_parabolic_sar, calculate_williams_r, calculate_adx


class strategy():

    def __init__(self, selected_indicators):
        self.selected_indicators = selected_indicators
        self.all_close_prices, self.all_high_prices, self.all_low_prices, self.all_open_prices = fetcher.fetch_historical_data(days=7)

    def fetch_last_hour_data(self):
        try:
            all_data = []
            current_time = fetcher.get_ntp_time(url = 'https://binomo1.com/trading')  # Menggunakan waktu NTP untuk keakuratan waktu
            retry_count = 0  # Hitung percakapan ulang jika gagal
            while len(all_data) < 60:
                formatted_time = current_time.strftime('%Y-%m-%dT00:00:00')  # Format waktu untuk request API
                url = f'https://api.binomo1.com/candles/v1/Z-CRY%2FIDX/{formatted_time}/60?locale=en'
                try:
                    response = requests.get(url)
                    response.raise_for_status()  # Memeriksa apakah ada error dalam request
                    data = response.json()
                    # Log response data untuk memastikan format yang diterima
                    # logging.debug(f"Response from API: {data}")
                    if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                        # Mengonversi 'created_at' menjadi datetime dan memastikan data valid
                        for entry in data['data']:
                            entry['created_at'] = datetime.strptime(entry['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
                        all_data.extend(data['data'])
                        current_time -= timedelta(minutes=1)  # Mundur satu menit
                        retry_count = 0  # Reset retry jika berhasil
                    else:
                        logging.error(f"Format data tidak valid dari URL: {data}")
                        retry_count += 1
                except requests.RequestException as e:
                    logging.error(f"Error fetching data: {e}")
                    retry_count += 1
                # Jika gagal terus menerus, lakukan retry atau berhenti
                if retry_count >= 5:
                    logging.error("Gagal mengambil data setelah beberapa percakapan. Menghentikan proses.")
                    break
                # Cek jika sudah cukup data
                # logging.debug(f"Jumlah data yang terkumpul: {len(all_data)}")
                if len(all_data) >= 60:
                    break
            # Ambil data terakhir 60 entri dan buat DataFrame
            all_data = all_data[-60:]
            # Log jumlah data yang diterima sebelum membuat DataFrame
            logging.debug(f"Jumlah data setelah diambil: {len(all_data)}")
            if len(all_data) < 60:
                logging.warning(f"Data yang diterima kurang dari 60 entri: {len(all_data)}")
            # Membuat DataFrame hanya jika ada cukup data
            if len(all_data) >= 60:
                df = pd.DataFrame(all_data)
                logging.debug(f"DataFrame dengan 60 entri berhasil dibuat.")
                return df
            else:
                logging.error("Tidak cukup data untuk membentuk DataFrame dengan 60 entri.")
                return pd.DataFrame()  # Kembalikan DataFrame kosong jika data tidak cukup
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return pd.DataFrame()  # Kembalikan DataFrame kosong jika terjadi error
        
    def get_scalar_value(self, value, default=0):
        try:
            if isinstance(value, (pd.Series, np.ndarray)):
                return value.item() if value.size > 0 else default
            if isinstance(value, strategy):
                logging.warning(f"Unexpected OptionBot object: {value}. Returning default.")
                return default
            return value if isinstance(value, (int, float)) else default
        except Exception as e:
            logging.warning(f"Error converting value {value}: {e}")
            return default
    def evaluate_indicator(self, indicator, value, weight, features):
        try:
            # Ambil data harga dan indikator yang relevan
            close = self.get_scalar_value(features.get('close'))
            ma_long = self.get_scalar_value(features.get('ma_long'))
            macd_signal = self.get_scalar_value(features.get('macd_signal'))
            bollinger_upper = self.get_scalar_value(features.get('bollinger_upper'))
            bollinger_lower = self.get_scalar_value(features.get('bollinger_lower'))
            atr_median = self.get_scalar_value(features.get('atr_median'))
            prev_close = self.get_scalar_value(features.get('prev_close'))
            # Hitung perubahan harga (delta)
            delta = (close - prev_close) / prev_close if close and prev_close else 0
            # Evaluasi berdasarkan indikator
            if indicator == 'ma_short':
                return weight * (1 if value > ma_long else -1)
            elif indicator == 'momentum':
                return weight * (1 if value > 0 else -1)
            elif indicator == 'rsi':
                if value < 25:
                    return weight * 1
                elif value > 75:
                    return weight * -1
                return weight * 0
            elif indicator == 'roc':
                return weight * (1 if value > 0 else -1)
            elif indicator == 'williams_r':
                if value < -85:
                    return weight * (1 + abs(delta))  # Tambahkan sensitivitas berbasis delta
                elif value > -15:
                    return weight * (-1 - abs(delta))
                return weight * 0
            elif indicator == 'macd':
                return weight * (1 if value > macd_signal else -1)
            elif indicator == 'bollinger_mean' and close is not None:
                if close < bollinger_lower:
                    return weight * (1 + abs(delta))  # Respon lebih kuat jika harga menyentuh band bawah
                elif close > bollinger_upper:
                    return weight * (-1 - abs(delta))
                return weight * 0
            elif indicator == 'adx' and atr_median is not None:
                return weight * (1 if value > atr_median else -1)
            return 0
        except Exception as e:
            logging.error(f"Error evaluating {indicator}: {e}")
            return 0
    def calculate_indicators(self, close_prices, high_prices, low_prices, open_prices):
        indicators = {}
        try:
            with ThreadPoolExecutor() as executor:
                futures = {
                    'ma_short': executor.submit(calculate_ma, close_prices, 3),
                    'ma_long': executor.submit(calculate_ma, close_prices, 7),
                    'rsi': executor.submit(calculate_rsi, close_prices, 3),
                    'roc': executor.submit(calculate_roc, close_prices, 3),
                    'williams_r': executor.submit(calculate_williams_r, close_prices, high_prices, low_prices, 7),
                    'momentum': executor.submit(calculate_momentum, close_prices, 3),
                    'macd': executor.submit(calculate_macd, close_prices, 13, 6, 3),
                    'bollinger_bands': executor.submit(calculate_bollinger_bands, close_prices, 10, 2),
                    'atr': executor.submit(calculate_atr, high_prices, low_prices, close_prices, 7),
                    'parabolic': executor.submit(calculate_parabolic_sar, high_prices, low_prices, close_prices, 0.05, 0.2),
                    'adx': executor.submit(calculate_adx, high_prices, low_prices, close_prices, 7),
                }
                for name, future in futures.items():
                    try:
                        result = future.result()
                        if result is not None:
                            if name == 'macd' and len(result) == 2:
                                indicators['macd'], indicators['macd_signal'] = result
                            elif name == 'bollinger_bands' and len(result) == 3:
                                indicators['bollinger_mean'], indicators['bollinger_upper'], indicators['bollinger_lower'] = result
                            else:
                                indicators[name] = result
                        else:
                            logging.warning(f"{name} returned None.")
                            indicators[name] = None
                    except Exception as e:
                        logging.error(f"Error calculating {name}: {e}")
                        indicators[name] = None
            for key in futures.keys():
                indicators.setdefault(key, None)
        except Exception as e:
            logging.error(f"Overall indicator calculation error: {e}")
            indicators = {key: None for key in futures.keys()}
        return indicators
    def analyze_chart(self, close_prices, high_prices, low_prices, open_prices, indicator_weights, indicator_threshold, combined_threshold, market_condition, filtered_signals):
        try:
            # Validasi panjang input harga
            if not all(len(lst) == len(close_prices) for lst in [high_prices, low_prices, open_prices]):
                logging.error("Input price arrays have inconsistent lengths. Returning 'hold'.")
                return 'hold', {}
            # Hitung indikator teknikal
            indicators = self.calculate_indicators(close_prices, high_prices, low_prices, open_prices)
            # Ambil nilai fitur terakhir untuk semua indikator yang dipilih
            features = {
                indicator: indicators.get(indicator, [None])[-1] for indicator in self.selected_indicators
            }
            features.update({
                'open': open_prices[-1],
                'high': high_prices[-1],
                'low': low_prices[-1],
                'close': close_prices[-1],
            })
            # Validasi nilai fitur
            if any(value is None for value in features.values()):
                logging.error("Not all indicators have valid values. Returning 'hold'.")
                return 'hold', indicators
            # Konversi ke DataFrame untuk kompatibilitas dengan fungsi filter
            features_df = pd.DataFrame([features])
            # logging.debug(f"Features DataFrame:\n{features_df}")
            # Filter sinyal berdasarkan kondisi pasar
            filtered_signals, market_condition = self.filter_trading_signals_based_on_market_conditions(
                features_df, filtered_signals, market_condition
            )
            if not filtered_signals:
                logging.warning(f"No signals match market condition {market_condition}. Returning 'hold'.")
                return 'hold', indicators
            # Keputusan akhir berdasarkan indikator dan kondisi pasar
            direction = self.combined_decision(
                features, indicator_weights, indicator_threshold, combined_threshold
            )
            if market_condition == 'bullish' and direction == 'buy':
                final_decision = 'buy'
            elif market_condition == 'bearish' and direction == 'sell':
                final_decision = 'sell'
            elif market_condition == 'sideways' and direction == 'buy' and direction == 'sell' and direction == 'hold':  # Periksa kondisi sideways dengan baik
                final_decision = 'hold'
            else:
                # Jika keputusan tidak cocok dengan kondisi pasar, maka hold
                final_decision = 'hold'
            logging.info(f"Market Condition: {market_condition}")
            logging.info(f"Final trading decision: {direction}")
            logging.info(f"Final decision after filtering: {final_decision}")
            return final_decision, indicators, market_condition
        except Exception as e:
            logging.error(f"Error analyzing chart: {e}")
            return 'hold', {}
    def combined_decision(self, features, indicator_weights=None, indicator_threshold=0, combined_threshold=0.24):
        try:
            # Check for missing indicators in the provided features
            missing_indicators = [i for i in self.selected_indicators if i not in features]
            if missing_indicators:
                logging.warning(f"Missing indicators in features: {missing_indicators}")
                return 'hold'
            # Set default indicator weights if not provided
            if indicator_weights is None:
                indicator_weights = {indicator: 1 for indicator in self.selected_indicators}
            indicator_score = 0
            max_indicator_score = 0
            epsilon = 1e-6  # Small epsilon to avoid division by zero in normalization
            # Calculate feature values for each indicator
            feature_values = {
                indicator: self.get_scalar_value(features.get(indicator)) 
                for indicator in self.selected_indicators
            }
            # Iterate through each selected indicator to compute its contribution to the score
            for indicator in self.selected_indicators:
                value = feature_values.get(indicator)
                if value is not None:
                    weight = indicator_weights.get(indicator, 1)
                    contribution = self.evaluate_indicator(indicator, value, weight, features)
                    # logging.info(f"Indicator: {indicator}, Value: {value}, Weight: {weight}, Contribution: {contribution}")
                    max_indicator_score += abs(weight)
                    indicator_score += contribution
            # Normalize the indicator score to a range between 0 and 1
            normalized_indicator_score = (
                indicator_score / max(max_indicator_score, epsilon) if max_indicator_score > 0 else 0
            )
            
            # Combine the score based on the threshold
            combined_score = normalized_indicator_score
            # Determine the final decision based on the combined score
            if combined_score > combined_threshold:
                final_decision = 'buy'
                logging.info(f"Decision: buy (combined score: {combined_score} > {combined_threshold})")
            elif combined_score < -combined_threshold:
                final_decision = 'sell'
                logging.info(f"Decision: sell (combined score: {combined_score} < {-combined_threshold})")
            else:
                final_decision = 'hold'
                logging.info(f"Decision: hold (combined score: {combined_score} within threshold)")
            # Log the final decision and feature values for debugging
            # logging.info(f"Final decision: {final_decision}, Combined Score: {combined_score}")
            # logging.debug(f"Feature values: {feature_values}")
            # Store the last trade result and indicators used for future reference
            self.last_trade_result = final_decision
            self.last_trade_indicators = {
                indicator: {'decision': final_decision, 'score': combined_score}
                for indicator in self.selected_indicators
            }
            return final_decision
        except Exception as e:
            logging.error(f"Error in combined_decision: {e}")
            return 'hold'
    def filter_trading_signals_based_on_market_conditions(self, df, signals, market_condition='sideways'):
        filtered_signals = [{'action': 'hold', 'price': None}]
        valid_conditions = ['bullish', 'bearish', 'sideways']
        if market_condition not in valid_conditions:
            market_condition = 'sideways'
        try:
            # Kolom yang diharapkan
            numeric_columns = [
                'ma_short', 'ma_long', 'rsi', 'macd', 'macd_signal', 
                'bollinger_upper', 'bollinger_lower', 'adx', 'close', 'high', 'low'
            ]
            # Validasi kolom dalam DataFrame
            missing_columns = [col for col in numeric_columns if col not in df.columns]
            if missing_columns:
                logging.warning(f"Missing columns in DataFrame: {missing_columns}. Skipping related calculations.")
            # Konversi kolom menjadi numerik
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            # Periksa NaN setelah konversi
            if df[numeric_columns].isnull().any().any():
                logging.warning("Some numeric columns contain NaN. Ensure data preprocessing is correct.")
                logging.info(f"NaN values found in columns: {df[numeric_columns].isnull().sum()}")
            # Tambahkan data sebelumnya jika hanya ada satu baris
            if len(df) < 2:
                if self.prev_data:
                    prev_data_row = pd.DataFrame([self.prev_data])
                    df = pd.concat([prev_data_row, df], ignore_index=True)
                    logging.info("Using previous data to supplement insufficient rows.")
                else:
                    if len(df) == 1:
                        self.prev_data = df.iloc[0].to_dict()
                        logging.info(f"Stored data for future use: {self.prev_data}")
                    return [{'action': 'hold', 'price': None}], market_condition
            # Ambil dua baris terakhir untuk analisis
            data = df.tail(2)
            ma_short = data['ma_short'].iloc[-1]
            ma_long = data['ma_long'].iloc[-1]
            macd = data['macd'].iloc[-1]
            macd_signal = data['macd_signal'].iloc[-1]
            rsi = data['rsi'].iloc[-1] if 'rsi' in data.columns else None
            adx = data['adx'].iloc[-1] if 'adx' in data.columns else None
            bollinger_upper = data['bollinger_upper'].iloc[-1] if 'bollinger_upper' in data.columns else None
            bollinger_lower = data['bollinger_lower'].iloc[-1] if 'bollinger_lower' in data.columns else None
            close_price = data['close'].iloc[-1]
            prev_close_price = data['close'].iloc[-2]
            # Hitung perubahan harga
            price_change = abs(close_price - prev_close_price)
            dynamic_change_threshold = price_change * 0.2  # Threshold lebih kecil untuk deteksi sideways
            # Modifikasi threshold berdasarkan kondisi pasar
            if market_condition == 'bullish':
                dynamic_change_threshold *= 1.3
            elif market_condition == 'bearish':
                dynamic_change_threshold *= 1.2
            elif market_condition == 'sideways':
                # Mengurangi ambang batas deteksi perubahan harga pada kondisi sideways
                dynamic_change_threshold *= 0.9  # Menurunkan faktor agar lebih sensitif terhadap perubahan kecil
            # Tentukan kondisi pasar
            if ma_short > ma_long and macd > macd_signal and (rsi is None or rsi > 50):
                market_condition = 'bullish'
            elif ma_short < ma_long and macd < macd_signal and (rsi is None or rsi < 50):
                market_condition = 'bearish'
            elif (
                adx is not None and adx < 20 and
                bollinger_lower is not None and bollinger_upper is not None and
                bollinger_lower < close_price < bollinger_upper
            ):
                market_condition = 'sideways'
            # Filter sinyal berdasarkan kondisi pasar
            if market_condition == 'bullish' and price_change > dynamic_change_threshold:
                filtered_signals = [{'action': 'buy', 'price': close_price}]
                logging.info(f"Signal generated: BUY at price {close_price}.")
            elif market_condition == 'bearish' and price_change > dynamic_change_threshold:
                filtered_signals = [{'action': 'sell', 'price': close_price}]
                logging.info(f"Signal generated: SELL at price {close_price}.")
            else:
                filtered_signals = [{'action': 'hold', 'price': close_price}]
                logging.info(f"Signal generated: HOLD. Conditions for 'buy' or 'sell' not fully met.")
            # Simpan data sebelumnya
            self.prev_data = {
                'ma_short': ma_short,
                'ma_long': ma_long,
                'rsi': rsi,
                'macd': macd,
                'macd_signal': macd_signal,
                'bollinger_upper': bollinger_upper,
                'bollinger_lower': bollinger_lower,
                'adx': adx,
                'close': close_price,
                'high': data['high'].iloc[-1],
                'low': data['low'].iloc[-1]
            }
            logging.info(f"Market condition determined as: {market_condition}")
            logging.info(f"Updated prev_data: {self.prev_data}")
        except Exception as e:
            logging.error(f"Unexpected error filtering signals: {e}. Returning all signals.")
            return signals, market_condition
        logging.debug(f"Filtered signals: {filtered_signals}")
        return filtered_signals, market_condition
    
    def test_strategy(self, test_type='realtime', start_balance=5000000, test_data=None, test_data_file='test_data.csv', indicator_weights=None, indicator_threshold=0, combined_threshold=0.24, market_condition='sideways'):
        try:
            # Persiapan data
            if test_type == 'backtest':
                if test_data is None:
                    if not os.path.exists(test_data_file):
                        logging.error(f"File {test_data_file} not found.")
                        return None, 0, 0, 0, 0, 0  # Tambahkan nilai untuk total positions
                    logging.info(f"Loading backtest data from file: {test_data_file}")
                    data = pd.read_csv(test_data_file)
                else:
                    data = test_data
            else:
                logging.info("Fetching realtime data from the URL...")
                data = self.fetch_last_hour_data()
            # Validasi data yang hilang
            if data.isnull().values.any():
                logging.warning("There are missing values in the data.")
                data = data.dropna()
            # Hitung indikator secara paralel
            with ThreadPoolExecutor() as executor:
                futures = {
                    'ma_short': executor.submit(calculate_ma, data['close'], 3),
                    'ma_long': executor.submit(calculate_ma, data['close'], 7),
                    'rsi': executor.submit(calculate_rsi, data['close'], 3),
                    'roc': executor.submit(calculate_roc, data['close'], 3),
                    'williams_r': executor.submit(calculate_williams_r, data['close'], data['high'], data['low'], 7),
                    'momentum': executor.submit(calculate_momentum, data['close'], 3),
                    'macd': executor.submit(calculate_macd, data['close'], 13, 6, 3),
                    'bollinger_bands': executor.submit(calculate_bollinger_bands, data['close'], 10, 2),
                    'atr': executor.submit(calculate_atr, data['high'], data['low'], data['close'], 7),
                    'parabolic': executor.submit(calculate_parabolic_sar, data['high'], data['low'], data['close'], 0.05, 0.2),
                    'adx': executor.submit(calculate_adx, data['high'], data['low'], data['close'], 7),
                }
            # Retrieve results from futures
            data['ma_short'] = futures['ma_short'].result()
            data['ma_long'] = futures['ma_long'].result()
            data['rsi'] = futures['rsi'].result()
            data['roc'] = futures['roc'].result()
            data['williams_r'] = futures['williams_r'].result()
            data['momentum'] = futures['momentum'].result()
            data['macd'], data['macd_signal'] = futures['macd'].result()
            data['bollinger_mean'], data['bollinger_upper'], data['bollinger_lower'] = futures['bollinger_bands'].result()
            data['atr'] = futures['atr'].result()
            data['parabolic'] = futures['parabolic'].result()
            data['adx'] = futures['adx'].result()
            # Tambahkan kolom arah harga
            data['direction'] = data['close'].shift(-1) - data['close']
            data['direction'] = data['direction'].apply(lambda x: 'buy' if x > 0 else ('sell' if x < 0 else 'hold'))
            data = data.dropna()
            # Variabel simulasi
            balance = start_balance
            highest_balance = start_balance
            win_count, loss_count = 0, 0
            total_positions = 0  # Menambahkan variabel total posisi
            initial_compensation = 20000
            compensation_factor = 2.2
            compensation = initial_compensation
            max_compensation = compensation
            successful_compensation_count = 0
            total_compensation_trades = 0
            for index, row in data.iterrows():
                # Validasi kolom yang diperlukan
                required_columns = [
                    'ma_short', 'ma_long', 'rsi', 'high', 'low', 'open', 'close',
                    'bollinger_mean', 'bollinger_upper', 'bollinger_lower', 'williams_r',
                    'momentum', 'macd', 'macd_signal', 'atr', 'parabolic', 'adx', 'roc', 'direction'
                ]
                if not all(col in row for col in required_columns):
                    missing_columns = [col for col in required_columns if col not in row]
                    logging.warning(f"Missing columns {missing_columns} in row {index}. Skipping this row.")
                    continue
                # Persiapkan fitur untuk keputusan trading
                features = pd.DataFrame([row[required_columns].values], columns=required_columns)
                # Gunakan keputusan dari combined_decision tanpa filter kondisi pasar
                direction = self.combined_decision(features, indicator_weights, indicator_threshold, combined_threshold)
                stake = compensation
                payout = stake * 0.8
                if direction in ['buy', 'sell']:
                    total_positions += 1  # Menambahkan penghitung posisi
                    if direction == row['direction']:
                        balance += payout
                        win_count += 1
                        if compensation > initial_compensation:
                            successful_compensation_count += 1
                        compensation = initial_compensation
                        self.last_trade_result = "win"
                    else:
                        balance -= stake
                        loss_count += 1
                        total_compensation_trades += 1
                        compensation = round(compensation * compensation_factor)
                        if compensation > balance:
                            compensation = balance
                            logging.warning(f"Adjusted compensation to {compensation} due to insufficient balance.")
                        if compensation > max_compensation:
                            max_compensation = compensation
                        self.last_trade_result = "loss"
                highest_balance = max(highest_balance, balance)
                self.last_trade_indicators = self.selected_indicators
                logging.debug(f"Balance after trade {index}: {balance}")
            # Hitung statistik
            win_rate = (win_count / (win_count + loss_count) * 100) if (win_count + loss_count) > 0 else 0
            compensation_success_rate = (successful_compensation_count / total_compensation_trades * 100) if total_compensation_trades > 0 else 0
            logging.info(f"{test_type.capitalize()} Results: Correct: {win_count}, Wrong: {loss_count}")
            logging.info(f"Final Balance: {balance}, Win Rate: {win_rate:.2f}%")
            logging.info(f"Max Compensation: {max_compensation}, Compensation Success Rate: {compensation_success_rate:.2f}%")
            logging.info(f"Highest Balance: {highest_balance}")
            # Evaluasi berdasarkan jumlah posisi
            positions_penalty = 0
            if total_positions < 20:  # Jika jumlah posisi kurang dari 20, beri penalti
                positions_penalty = (20 - total_positions) * 10
            return balance, win_rate, max_compensation, compensation_success_rate, highest_balance, positions_penalty
        except Exception as e:
            logging.error(f"Error during strategy testing: {e}")
            return None, 0, 0, 0, 0, 0
        
    def optimize_strategy(self, data=None, test_type='realtime', n_trials=100, use_parallel=False):
        try:
            # Validasi input test_type
            valid_test_types = ['realtime', 'backtest']
            if test_type not in valid_test_types:
                raise ValueError(f"Invalid test_type '{test_type}'. Valid options are {valid_test_types}.")
            # Ambil data jika tidak disediakan
            if data is None:
                logging.info("Fetching data from API...")
                data = self.fetch_last_hour_data()
            # Validasi format dan isi data
            if not isinstance(data, pd.DataFrame):
                raise ValueError("Data harus berupa DataFrame Pandas.")
            if data.empty or data.isnull().all().all():
                raise ValueError("Data yang diterima kosong atau hanya berisi nilai NaN. Harap periksa sumber data Anda.")
            
            if 'created_at' not in data.columns or 'close' not in data.columns:
                raise ValueError("Data tidak memiliki kolom yang diperlukan (created_at, close).")
            logging.info(f"Starting strategy optimization with test_type='{test_type}'")
            # Inisialisasi atribut
            self.data = data
            self.test_type = test_type
            # Bungkus fungsi objective untuk logging dan penanganan kesalahan
            def wrapped_objective(trial):
                try:
                    logging.debug("Evaluating trial with params: %s", trial.params)
                    score = self.objective(trial)
                    if score == float('-inf'):
                        logging.warning(f"Trial failed with parameters: {trial.params}")
                    return score
                except Exception as e:
                    logging.error(f"Error during objective function evaluation: {e}")
                    return float('-inf')  # Indikasikan bahwa trial gagal
            # Inisialisasi Optuna Study dengan parameter untuk sampling
            logging.info("Initializing Optuna study...")
            study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler())
            # Menjalankan optimasi dengan parallelism jika diminta
            if use_parallel:
                logging.info("Starting optimization with parallel execution...")
                study.optimize(wrapped_objective, n_trials=n_trials, gc_after_trial=True, n_jobs=-1)
            else:
                logging.info(f"Starting optimization with {n_trials} trials...")
                study.optimize(wrapped_objective, n_trials=n_trials, gc_after_trial=True)
            # Dapatkan parameter terbaik
            best_params = study.best_params
            best_value = study.best_value
            # Log hasil optimasi
            logging.info("Optimization completed successfully.")
            logging.info(f"Best parameters: {best_params}")
            logging.info(f"Best objective value: {best_value:.4f}")
            print("Optimization completed.")
            print("Best parameters:", best_params)
            print(f"Best objective value: {best_value:.4f}")
            return best_params
        except ValueError as e:
            logging.error(f"ValueError: {e}")
            raise
        except Exception as e:
            logging.error(f"Error in optimize_strategy: {e}")
            raise  # Lempar ulang agar kesalahan dapat dilacak lebih lanjut