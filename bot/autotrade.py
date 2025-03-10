from modules import pd, np, os, optuna, json, requests, datetime, webdriver, Service, WebDriverWait, StaleElementReferenceException, ElementClickInterceptedException, TimeoutException, ThreadPoolExecutor, timedelta, logging, By, NoSuchElementException, sleep, EC, Keys
from utils import username, password, secret_key, totp, historical_data_file, csv_file, csv
from fetcher import fetcher
from indicators import calculate_ma, calculate_rsi, calculate_macd, calculate_momentum, calculate_roc, calculate_atr, calculate_bollinger_bands, calculate_parabolic_sar, calculate_williams_r, calculate_adx

class autotrade:
    def __init__(self, selected_indicators):
        self.selected_indicators = selected_indicators
        # Inisialisasi atribut untuk menyimpan hasil trade terakhir
        self.last_trade_result = None
        self.last_trade_indicators = {}  # Inisialisasi sebagai dictionary kosong
        self.last_trade_direction = None
        self.prev_data = None
        # Ambil data historis untuk inisialisasi indikator
        self.all_close_prices, self.all_high_prices, self.all_low_prices, self.all_open_prices = fetcher.fetch_historical_data(days=7)
  
    def log_trade(self, timestamp, direction, market_condition, compensation, profit_or_loss, entry_price, close_price):
        try:
            if not all([timestamp, direction, market_condition, compensation, entry_price, close_price]):
                raise ValueError("Satu atau lebih parameter perdagangan hilang.")
            with open(csv_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([timestamp, direction, market_condition, int(compensation), int(profit_or_loss), entry_price, close_price])
            logging.info(f"Trade dicatat: {timestamp, direction, market_condition, compensation, profit_or_loss, entry_price, close_price}")
            logging.info("-------------------------------------------------------------------------------------------------")
        except Exception as e:
            logging.error(f"Error mencatat trade: {e}")
    def log_historical_data(self, timestamp, indicators, high, low, open_price, close_price, direction, market_condition, correction):
        try:
            # Debugging: Log indikator dan harga
            logging.info(f"Logging data historis: Timestamp={timestamp}, Indicators={indicators}, High={high}, Low={low}, Open={open_price}, Close={close_price}")
            
            # Pastikan nilai indikator diambil dengan benar
            indicator_values = {name: values[-1] if values else 'N/A' for name, values in indicators.items()}
            
            # Buat baris data untuk ditulis ke file
            row = [timestamp]
            row.extend(indicator_values.values())
            row.extend([high, low, open_price, close_price, direction, market_condition, correction])

            # Tulis data ke file CSV
            with open(historical_data_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(row)
        except Exception as e:
            logging.error(f"Error mencatat data historis: {e}")

    def place_trade(self, direction):
        try:
            # Validasi arah perdagangan
            if direction not in ['buy', 'sell']:
                raise ValueError(f"Invalid trade direction: {direction}")
            # Validasi kompensasi
            if not hasattr(self, 'compensation') or not isinstance(self.compensation, (int, float)) or self.compensation <= 0:
                raise ValueError("Compensation amount is not properly set.")
            # Cari elemen input untuk bid
            bid_xpath = '/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/main/div/app-panel/ng-component/section/div/way-input-controls/div/input'
            bid_element = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, bid_xpath))
            )
            # Hilangkan simbol 'Rp' dan semua karakter non-numerik lainnya untuk input
            compensation_value = f"Rp{self.compensation}"
            
            bid_element.clear()
            sleep(0.5)
            bid_element.send_keys(compensation_value)
            sleep(0.5)
            # Validasi apakah nilai yang dimasukkan sesuai dengan kompensasi
            entered_bid = bid_element.get_attribute('value')
            if entered_bid != compensation_value:
                logging.warning(f"Entered bid amount {entered_bid} does not match the compensation {compensation_value}. Retrying...")
                return  # Keluar dan tunggu input yang benar
            # Tentukan tombol yang akan diklik berdasarkan arah perdagangan
            button_xpath = {
                'buy': '/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/main/div/app-panel/ng-component/section/binary-info/div[2]/div/trading-buttons/vui-button[1]/button',
                'sell': '/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/main/div/app-panel/ng-component/section/binary-info/div[2]/div/trading-buttons/vui-button[2]/button'
            }[direction]
            # Klik tombol perdagangan
            trade_button = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, button_xpath))
            )
            trade_button.click()
            logging.info(f"Placed trade for Direction: {direction}, Compensation: {compensation_value}")
        except ElementClickInterceptedException as e:
            logging.warning(f"Element click intercepted. Attempting to use JavaScript click: {e}")
            try:
                self.driver.execute_script("arguments[0].click();", trade_button)
            except Exception as js_error:
                logging.error(f"JavaScript click failed: {js_error}")
        except TimeoutException as e:
            logging.error(f"Timeout waiting for elements to place trade: {e}")
        except ValueError as e:
            logging.error(f"Validation error: {e}")
        except Exception as e:
            logging.error(f"Unexpected error while placing trade ({direction}): {e}")
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
            if isinstance(value, (pd.Series, np.ndarray, list)):
                filtered = [v for v in value if v is not None]
                return filtered[0] if filtered else default  # Ambil elemen pertama yang valid
            if isinstance(value, autotrade):
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
            ma_short = self.get_scalar_value(features.get('ma_short'))  # Tambahan untuk MA Short
            macd_signal = self.get_scalar_value(features.get('macd_signal'))
            williams_r = self.get_scalar_value(features.get('williams_r'))
            bollinger_upper = self.get_scalar_value(features.get('bollinger_upper'))
            bollinger_lower = self.get_scalar_value(features.get('bollinger_lower'))
            prev_close = self.get_scalar_value(features.get('prev_close'))
            atr = self.get_scalar_value(features.get('atr'))
            adx = self.get_scalar_value(features.get('adx'))

            # Hitung perubahan harga (delta)
            delta = (close - prev_close) / prev_close if close and prev_close else 0

            # Evaluasi berdasarkan indikator
            if indicator == 'ma_short':
                # MA Short lebih sensitif untuk sinyal perdagangan cepat
                if ma_short and ma_long:
                    return weight * (1 if ma_short > ma_long else -1)
                return 0

            elif indicator == 'momentum':
                # Momentum harus sangat responsif
                return weight * (1 if value > 0 else -1)

            elif indicator == 'rsi':
                # RSI untuk perdagangan cepat lebih responsif
                if value < 30:
                    return weight * (1 + 2 * abs(delta))  # Oversold dengan sensitivitas tinggi
                elif value > 70:
                    return weight * (-1 - 2 * abs(delta))  # Overbought dengan sensitivitas tinggi
                return weight * 0

            elif indicator == 'roc':
                # ROC lebih agresif untuk perdagangan cepat
                return weight * (1 if value > 0 else -1)

            elif indicator == 'williams_r' and value is not None:
                if value < -80:
                    return weight * (1 + 2 * abs(delta))  # Oversold
                elif value > -20:
                    return weight * (-1 - 2 * abs(delta))  # Overbought
                return weight * 0

            elif indicator == 'macd':
                # MACD lebih agresif
                return weight * (1 if value > macd_signal else -1)

            elif indicator == 'bollinger_mean' and close is not None:
                # Bollinger Bands lebih sensitif terhadap oversold/overbought
                if close < bollinger_lower:
                    return weight * (1 + 3 * abs(delta))  # Oversold dengan respon kuat
                elif close > bollinger_upper:
                    return weight * (-1 - 3 * abs(delta))  # Overbought dengan respon kuat
                return weight * 0

            elif indicator == 'adx' and adx is not None:
                # ADX digunakan untuk konfirmasi kekuatan tren
                return weight * (1 if adx > 25 else -1)  # 25 adalah ambang batas tren yang kuat

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
            elif market_condition == 'sideways' and direction == ['buy', 'sell', 'hold']:# Periksa kondisi sideways dengan baik
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
        
    def combined_decision(self, features, indicator_weights=None, indicator_threshold=0, combined_threshold=None):
        try:
            # Ambil nilai threshold dinamis jika tidak diberikan
            if combined_threshold is None:
                combined_threshold = self.optimized_combined_threshold if hasattr(self, 'optimized_combined_threshold') else 0.24
            
            # Check for missing indicators in the provided features
            missing_indicators = [i for i in self.selected_indicators if i not in features]
            if missing_indicators:
                logging.warning(f"Missing indicators in features: {missing_indicators}")
                return 'hold'
            
            # Gunakan bobot yang dioptimalkan jika tersedia
            if indicator_weights is None:
                indicator_weights = self.optimized_indicator_weights if hasattr(self, 'optimized_indicator_weights') else {indicator: 1 for indicator in self.selected_indicators}
            
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
                    max_indicator_score += abs(weight)
                    indicator_score += contribution
            
            # Normalize the indicator score to a range between 0 and 1
            normalized_indicator_score = (
                indicator_score / max(max_indicator_score, epsilon) if max_indicator_score > 0 else 0
            )
            
            # Combine the score based on the dynamic threshold
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
            
            # Log and store the last trade result for future reference
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
            market_condition = 'sideways'  # Default to 'sideways' if an invalid condition is passed

        try:
            # Define the columns that should be present in the DataFrame
            numeric_columns = [
                'ma_short', 'ma_long', 'rsi', 'macd', 'macd_signal', 
                'bollinger_upper', 'bollinger_lower', 'adx', 'atr', 'close', 'high', 'low'
            ]
            
            # Check if all required columns exist in the DataFrame
            missing_columns = [col for col in numeric_columns if col not in df.columns]
            if missing_columns:
                logging.warning(f"Missing columns in DataFrame: {missing_columns}. Skipping related calculations.")
            
            # Convert columns to numeric values where possible
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Check for NaN values after conversion
            if df[numeric_columns].isnull().any().any():
                logging.warning("Some numeric columns contain NaN. Ensure data preprocessing is correct.")
            
            # Add previous data if there's not enough data for analysis
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
            
            # Analyze the last two rows of data
            data = df.tail(2)
            ma_short = data['ma_short'].iloc[-1]
            ma_long = data['ma_long'].iloc[-1]
            macd = data['macd'].iloc[-1]
            macd_signal = data['macd_signal'].iloc[-1]
            rsi = data['rsi'].iloc[-1] if 'rsi' in data.columns else None
            adx = data['adx'].iloc[-1] if 'adx' in data.columns else None
            atr = data['atr'].iloc[-1] if 'atr' in data.columns else None
            bollinger_upper = data['bollinger_upper'].iloc[-1] if 'bollinger_upper' in data.columns else None
            bollinger_lower = data['bollinger_lower'].iloc[-1] if 'bollinger_lower' in data.columns else None
            close_price = data['close'].iloc[-1]
            prev_close_price = data['close'].iloc[-2]
            
            # Calculate price change and dynamic threshold
            price_change = abs(close_price - prev_close_price)
            dynamic_change_threshold = price_change * 0.15  # A smaller threshold for sideways detection
            
            if atr is not None:
                # Adjust ATR multiplier based on market condition
                if market_condition == 'bullish':
                    dynamic_change_threshold += atr * 1.5  # Increase weight for ATR in bullish market
                elif market_condition == 'bearish':
                    dynamic_change_threshold += atr * 1.3  # Slightly increase ATR in bearish market
                else:  # sideways market
                    dynamic_change_threshold += atr * 0.7  # Lower ATR impact in sideways market

            # Adjust threshold based on market conditions
            if market_condition == 'bullish':
                dynamic_change_threshold *= 1.3
            elif market_condition == 'bearish':
                dynamic_change_threshold *= 1.2
            elif market_condition == 'sideways':
                dynamic_change_threshold *= 0.9

            # Determine market condition based on indicators
            if ma_short > ma_long and macd > macd_signal and (rsi is None or rsi > 50):
                market_condition = 'bullish'
            elif ma_short < ma_long and macd < macd_signal and (rsi is None or rsi < 50):
                market_condition = 'bearish'
            elif adx is not None and adx < 20 and bollinger_lower is not None and bollinger_upper is not None and bollinger_lower < close_price < bollinger_upper:
                market_condition = 'sideways'

            # Filter trading signals based on market condition and thresholds
            if market_condition == 'bullish' and price_change > dynamic_change_threshold:
                filtered_signals = [{'action': 'buy', 'price': close_price}]
                logging.info(f"Signal generated: BUY at price {close_price}.")
            elif market_condition == 'bearish' and price_change > dynamic_change_threshold:
                filtered_signals = [{'action': 'sell', 'price': close_price}]
                logging.info(f"Signal generated: SELL at price {close_price}.")
            else:
                filtered_signals = [{'action': 'hold', 'price': close_price}]
                logging.info(f"Signal generated: HOLD. Conditions for 'buy' or 'sell' not fully met.")
            
            # Store the current data for future analysis
            self.prev_data = {
                'ma_short': ma_short,
                'ma_long': ma_long,
                'rsi': rsi,
                'macd': macd,
                'macd_signal': macd_signal,
                'bollinger_upper': bollinger_upper,
                'bollinger_lower': bollinger_lower,
                'adx': adx,
                'atr': atr,
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


    def preprocess_data(self, data):
        try:
            if data.empty or data.isnull().all().all():
                raise ValueError("Data pengujian kosong atau hanya berisi nilai NaN.")
            logging.info(f"Data sebelum preprocessing - Rows: {data.shape[0]}, Columns: {data.shape[1]}")
            data = data.fillna(data.mean())
            for col in data.select_dtypes(include=['object']).columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
            data = data.fillna(data.mean())
            logging.info(f"Data setelah preprocessing - Rows: {data.shape[0]}, Columns: {data.shape[1]}")
            if data.empty:
                logging.warning("Data kosong setelah preprocessing.")
            logging.info("Data preprocessing completed successfully.")
            return data
        except Exception as e:
            logging.error(f"Error in preprocess_data: {e}")
            raise
    def adjust_weights_based_on_last_outcome(self, indicator_weights):
        try:
            if not isinstance(self.last_trade_indicators, dict) or self.last_trade_result not in ["buy", "sell", "hold"]:
                logging.warning("Data perdagangan terakhir tidak valid, penyesuaian bobot dibatalkan.")
                return
            decay_factor = 0.99
            adjustment_factor = 0.1
            min_weight = 0.05
            max_weight = 2.0
            logging.info(f"Last trade result: {self.last_trade_result}")
            for indicator, data in self.last_trade_indicators.items():
                decision = data.get('decision')
                if decision is None or indicator not in indicator_weights:
                    continue
                if self.last_trade_result == decision:
                    indicator_weights[indicator] += adjustment_factor
                else:
                    indicator_weights[indicator] -= adjustment_factor
                indicator_weights[indicator] *= decay_factor
                indicator_weights[indicator] = max(min_weight, min(max_weight, indicator_weights[indicator]))
            total_weight = sum(indicator_weights.values())
            if not (0.9 <= total_weight <= 1.1):
                indicator_weights = {indicator: weight / total_weight for indicator, weight in indicator_weights.items()}
            logging.info(f"Adjusted weights: {indicator_weights}")
        except Exception as e:
            logging.error(f"Error while adjusting weights: {e}")
    def test_strategy(self, test_type='realtime', start_balance=5000000, test_data=None, test_data_file='test_data.csv', indicator_weights=None, indicator_threshold=0, combined_threshold=None, market_condition='sideways'):
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
    def objective(self, trial):
        try:
            # Rentang untuk parameter
            weight_range = (0.0, 1.0)
            threshold_range = (0.0, 0.3)
            # Optimasi bobot indikator
            indicator_weights = {
                'ma_short': trial.suggest_float('ma_short_weight', *weight_range),
                'ma_long': trial.suggest_float('ma_long_weight', *weight_range),
                'rsi': trial.suggest_float('rsi_weight', *weight_range),
                'roc': trial.suggest_float('roc_weight', *weight_range),
                'williams_r': trial.suggest_float('williams_r_weight', *weight_range),
                'momentum': trial.suggest_float('momentum_weight', *weight_range),
                'macd': trial.suggest_float('macd_weight', *weight_range),
                'macd_signal': trial.suggest_float('macd_signal_weight', *weight_range),
                'bollinger_mean': trial.suggest_float('bollinger_mean_weight', *weight_range),
                'bollinger_upper': trial.suggest_float('bollinger_upper_weight', *weight_range),
                'bollinger_lower': trial.suggest_float('bollinger_lower_weight', *weight_range),
                'atr': trial.suggest_float('atr_weight', *weight_range),
                'parabolic': trial.suggest_float('parabolic_weight', *weight_range),
                'adx': trial.suggest_float('adx_weight', *weight_range)
            }
            # Optimasi ambang batas
            indicator_threshold = trial.suggest_float('indicator_threshold', *threshold_range)
            combined_threshold = trial.suggest_float('combined_threshold', *threshold_range)
            # Validasi dan preprocessing data
            processed_data = self.preprocess_data(self.data)
            if processed_data.empty:
                logging.error("Data kosong setelah preprocessing.")
                return float('-inf')
            train_results = self.test_strategy(
                test_type='backtest',
                start_balance=5000000,
                test_data=processed_data,
                indicator_weights=indicator_weights,
                indicator_threshold=indicator_threshold,
                combined_threshold=combined_threshold
            )
            test_results = self.test_strategy(
                test_type='realtime',
                start_balance=5000000,
                test_data=processed_data,
                indicator_weights=indicator_weights,
                indicator_threshold=indicator_threshold,
                combined_threshold=combined_threshold
            )
            # Ambil hasil
            train_balance, train_win_rate, train_max_comp, train_comp_success_rate, train_highest_balance, train_positions_penalty = train_results
            test_balance, test_win_rate, test_max_comp, test_comp_success_rate, test_highest_balance, test_positions_penalty = test_results
            # Evaluasi dengan penalti posisi
            position_penalty = test_positions_penalty
            logging.info(f"Train results - Balance: {train_balance}, Win Rate: {train_win_rate:.2f}%, Max Comp: {train_max_comp}, Comp Success Rate: {train_comp_success_rate}")
            logging.info(f"Test results - Balance: {test_balance}, Win Rate: {test_win_rate:.2f}%, Max Comp: {test_max_comp}, Comp Success Rate: {test_comp_success_rate}")
            # Penalti dan reward
            if test_balance is None or test_highest_balance is None:
                logging.error("Test balance atau test highest balance adalah None.")
                drawdown_penalty = float('inf')
            else:
                drawdown_penalty = max(0, (test_highest_balance - test_balance) / test_balance) * 100
            wrong_penalty = 150 * (1 - test_win_rate / 100)
            compensation_penalty = max(0, test_max_comp - 400000) / 10000
            comp_success_reward = test_comp_success_rate * 10
            balance_reward = test_balance / 1000
            win_rate_reward = test_win_rate * 12
            profit_reward = test_highest_balance / 1000
            profit_stability_reward = 50 if drawdown_penalty < 10 else 0
            score = (
                balance_reward + win_rate_reward + profit_reward + comp_success_reward - 
                wrong_penalty - compensation_penalty - drawdown_penalty + profit_stability_reward - position_penalty
            )
            # Penalti untuk overfitting
            overfitting_penalty = max(0, (train_win_rate - test_win_rate) * 2)
            score -= overfitting_penalty
            logging.info(f"Calculated score: {score:.2f}")
            return score
        except Exception as e:
            logging.error(f"Error during objective function evaluation: {e}")
            return float('-inf')
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
            
            # Menyimpan parameter terbaik ke dalam atribut kelas
            self.optimized_indicator_weights = {
                'ma_short': best_params.get('ma_short_weight', 1),
                'ma_long': best_params.get('ma_long_weight', 1),
                'rsi': best_params.get('rsi_weight', 1),
                'roc': best_params.get('roc_weight', 1),
                'williams_r': best_params.get('williams_r_weight', 1),
                'momentum': best_params.get('momentum_weight', 1),
                'macd': best_params.get('macd_weight', 1),
                'macd_signal': best_params.get('macd_signal_weight', 1),
                'bollinger_mean': best_params.get('bollinger_mean_weight', 1),
                'bollinger_upper': best_params.get('bollinger_upper_weight', 1),
                'bollinger_lower': best_params.get('bollinger_lower_weight', 1),
                'atr': best_params.get('atr_weight', 1),
                'parabolic': best_params.get('parabolic_weight', 1),
                'adx': best_params.get('adx_weight', 1)
            }
            self.optimized_combined_threshold = best_params.get('combined_threshold', 0.24)
            
            return best_params
        except ValueError as e:
            logging.error(f"ValueError: {e}")
            raise
        except Exception as e:
            logging.error(f"Error in optimize_strategy: {e}")
            raise  # Lempar ulang agar kesalahan dapat dilacak lebih lanjut

    def get_prices_from_url(self):
        try:
            response = requests.get(fetcher.get_price_url())
            response.raise_for_status()
            data = response.json()
            if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                last_entry = data['data'][-1]
                close_price = last_entry['close']
                open_price = last_entry['open']
                high_price = last_entry['high']
                low_price = last_entry['low']
                return close_price, open_price, high_price, low_price
            else:
                logging.error("Format data tidak valid yang diterima.")
                return None, None, None, None
        except requests.RequestException as e:
            logging.error(f"Error mengambil harga dari URL: {e}")
            return None, None, None, None
    # Fungsi untuk update data ke Google Sheets publik menggunakan CSV URL
    def update_transaction_to_google_sheet(self, nama, timestamp, saldo_awal, saldo_sekarang, total_profit_loss):
        try:
            # URL Web App yang telah Anda deploy
            web_app_url = "https://script.google.com/macros/s/AKfycbyZzZsFpLduQdhgtBnwedpQm37WdfwlosQfKnNBzv60w_17GoqUafkkeRHheHlbqD1W/exec"  # Ganti dengan URL Web App Anda
            
            # Data yang akan dikirim dalam format JSON
            data = {
                "nama": nama,
                "timestamp": timestamp,
                "saldo_awal": saldo_awal,
                "saldo_sekarang": saldo_sekarang,
                "total_profit_loss": total_profit_loss,
            }
            
            # Mengirim permintaan POST ke Web App
            headers = {'Content-Type': 'application/json'}
            response = requests.post(web_app_url, data=json.dumps(data), headers=headers)
            
            # Memeriksa respons
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("status") == "success":
                    print("Data berhasil diupdate di Google Sheets!")
                    logging.info("Data berhasil diupdate di Google Sheets!")
                else:
                    print(f"Gagal mengupdate data di Google Sheets: {response_data.get('message')}")
                    logging.error(f"Gagal mengupdate data di Google Sheets: {response_data.get('message')}")
            else:
                print(f"Gagal mengupdate data di Google Sheets. Status Code: {response.status_code}")
                logging.error(f"Gagal mengupdate data di Google Sheets. Status Code: {response.status_code}")
        
        except Exception as e:
            print(f"Error: {e}")
            logging.error(f"Error saat mengupdate Google Sheets: {e}")