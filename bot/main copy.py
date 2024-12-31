from modules import timedelta, logging, sleep, time, np, tabulate
from autotrade import autotrade
from fetcher import fetcher
from session import session
from interactions import interactions
from utils import max_loss, max_positions, target_profit

def main(account_type='Demo'):
    # Menampilkan pilihan indikator
    indicators_list = [
        'ma_short', 'ma_long', 'rsi', 'roc', 'williams_r', 'momentum',
        'macd', 'macd_signal', 'bollinger_mean', 'bollinger_upper',
        'bollinger_lower', 'atr', 'parabolic', 'adx'
    ]

    selected_indicators = indicators_list

    bot = autotrade(selected_indicators=selected_indicators)
    interact = interactions()
    
    # Log in ke platform
    interact.login()
    print(f"Login Berhasil")
    initial_balance = interact.checkbalance()

    # Mendapatkan parameter terbaik dari optimasi
    best_params = bot.optimize_strategy(data=None, test_type='realtime')
    indicator_weights = {indicator: best_params.get(f'{indicator}_weight', 1) for indicator in selected_indicators}
    indicator_threshold = best_params.get('indicator_threshold', 0.1)
    combined_threshold = best_params.get('combined_threshold', 0.2)
    
    bot.test_strategy()
    
    try:
        # Mencoba memilih tipe akun dan memeriksa saldo
        interact.select_account_type(account_type)
        initial_balance = interact.checkbalance()
        print(f"Initial Balance: Rp{initial_balance}")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
        interact.close_ad_if_exists()  # Menutup iklan jika ada
        try:
            interact.select_account_type(account_type)
            initial_balance = interact.checkbalance()
            print(f"Initial Balance: Rp{initial_balance}")
        except Exception as retry_error:
            print(f"Kesalahan tetap terjadi setelah mencoba menutup iklan: {retry_error}")

    # Pengaturan waktu dan batasan runtime
    start_time = fetcher.get_ntp_time(url='https://binomo1.com/trading')
    max_runtime = timedelta(hours=1)

    previous_balance = initial_balance
    first_trade = True
    last_trade_minute = None

    while True:
        current_time = fetcher.get_ntp_time(url='https://binomo1.com/trading')
        runtime = current_time - start_time

        if runtime >= max_runtime and interact.compensation == interact.initial_compensation:
            if len(bot.all_close_prices) >= 14:
                print("Runtime sudah melebihi batas waktu. Memperpanjang runtime dan mengulang optimasi strategi.")
                
                # Ulang optimasi strategi
                best_params = bot.optimize_strategy(data=None, test_type='realtime')
                indicator_weights = {indicator: best_params.get(f'{indicator}_weight', 1) for indicator in selected_indicators}
                indicator_threshold = best_params.get('indicator_threshold', 0.1)
                combined_threshold = best_params.get('combined_threshold', 0.2)

                # Tambahkan 1 jam ke runtime maksimum
                max_runtime += timedelta(hours=1)

                # Logging tambahan
                print(f"Max runtime diperpanjang menjadi: {max_runtime}")
                print(f"Parameter strategi terbaru: {best_params}")
                
                continue  # Lanjutkan loop
            else:
                print("Data belum cukup untuk mengulang optimasi. Melewati pengulangan.")

        # Lakukan trading jika syarat lainnya terpenuhi
        if interact.total_positions < max_positions and interact.total_profit > max_loss and interact.total_profit < target_profit:
            current_minute = current_time.minute
            current_second = current_time.second

            if last_trade_minute is None or current_minute != last_trade_minute:  # Pastikan last_trade_minute diperiksa
                last_trade_minute = current_minute
                if current_second > 10:
                    print("Menunggu hingga pergantian menit berikutnya...")
                    time.sleep(60 - current_second)

                if interact.is_position_closed():
                    current_coin = interact.get_current_coin()
                    if current_coin != "Crypto IDX":
                        logging.info(f"Coin yang dipilih saat ini adalah {current_coin}. Melewati trading.")
                        if not interact.select_crypto_idx():
                            logging.warning("Gagal mengubah ke 'Crypto IDX'. Melewati trading.")
                            continue

                    close_price, open_price, high_price, low_price = bot.get_prices_from_url()
                    if close_price is not None:
                        bot.all_close_prices.append(close_price)
                        bot.all_high_prices.append(high_price)
                        bot.all_low_prices.append(low_price)
                        bot.all_open_prices.append(open_price)

                        bot.all_close_prices, bot.all_high_prices, bot.all_low_prices, bot.all_open_prices = (
                            bot.all_close_prices[-60:], bot.all_high_prices[-60:], bot.all_low_prices[-60:], bot.all_open_prices[-60:]
                        )
                        
                        current_balance = interact.checkbalance()
                        profit_or_loss = current_balance - previous_balance if not first_trade else 0
                        interact.total_profit = current_balance - initial_balance

                        timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')

                        market_condition = 'sideways'
                        if len(bot.all_close_prices) >= 14:
                            direction, indicators, market_condition = bot.analyze_chart(
                                bot.all_close_prices, bot.all_high_prices, bot.all_low_prices, bot.all_open_prices,
                                indicator_weights, indicator_threshold, combined_threshold, market_condition, filtered_signals=None
                            )
                        else:
                            direction = np.random.choice(['buy', 'sell'])
                            indicators = {key: [] for key in indicators_list}

                        correction = (
                            'netral' if profit_or_loss == 0
                            else 'correct' if profit_or_loss > 0
                            else 'wrong'
                        )

                        if not first_trade:
                            bot.log_trade(timestamp, direction, market_condition, interact.compensation, profit_or_loss, open_price, close_price)
                            bot.log_historical_data(timestamp, indicators, high_price, low_price, open_price, close_price, direction, market_condition, correction)
                            if profit_or_loss > 0:
                                interact.winning_positions += 1
                                if interact.compensation > interact.initial_compensation:
                                    interact.successful_compensation_positions += 1
                                interact.compensation = interact.initial_compensation
                            elif profit_or_loss < 0:
                                interact.compensation_positions += 1
                                if interact.compensation * interact.compensation_factor < interact.manual_trade_compensation_limit:
                                    interact.compensation = round(interact.compensation * interact.compensation_factor)
                                else:
                                    logging.warning("Batas kompensasi tercapai.")

                        if direction != 'hold' and market_condition != 'sideways' and interact.compensation < interact.manual_trade_compensation_limit:
                            interact.place_trade(direction)
                            interact.total_positions += 1

                        # Log transaksi ke Google Sheet
                        nama = 'Andi Arif R.'
                        saldo_awal = 5000000
                        saldo_sekarang = current_balance
                        total_profit_loss = saldo_sekarang - saldo_awal

                        bot.update_transaction_to_google_sheet(
                            nama,
                            timestamp,
                            saldo_awal,
                            saldo_sekarang,
                            total_profit_loss,
                        )

                        previous_balance = current_balance
                        first_trade = False

                        win_rate = (interact.winning_positions / interact.total_positions) * 100 if interact.total_positions > 0 else 0
                        compensation_success_rate = (
                            (interact.successful_compensation_positions / interact.compensation_positions) * 100
                            if interact.compensation_positions > 0 else 0
                        )
                        
                        minutes, _ = divmod(int(runtime.total_seconds()), 60)
                        hours, minutes = divmod(minutes, 60)
                        formatted_runtime = f"{hours:02}:{minutes:02}"

                        metrics = [
                            ["Signal", direction],
                            ["Market Condition", market_condition],
                            ["Total Positions", interact.total_positions],
                            ["Winning Positions", interact.winning_positions],
                            ["Win Rate", f"{win_rate:.2f}%"],
                            ["Total Profit", f"Rp{interact.total_profit}"],
                            ["Compensation Positions", interact.compensation_positions],
                            ["Successful Compensation Positions", interact.successful_compensation_positions],
                            ["Compensation Success Rate", f"{compensation_success_rate:.2f}%"],
                            ["Duration", formatted_runtime]
                        ]
                        print(tabulate(metrics, headers=["Metric", "Value"], tablefmt="grid"))

if __name__ == "__main__":
    bot = None
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram dihentikan oleh pengguna.")
        session(bot)
