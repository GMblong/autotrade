from modules import logging, tabulate, datetime

class session:
    def save_session_data(bot):
        if bot is None:
            print("Tidak ada sesi aktif untuk disimpan.")
            logging.warning("Tidak ada sesi aktif untuk disimpan.")
            return
        print("\nMenyimpan data sesi sebelum keluar...")
        logging.info("Menyimpan data sesi sebelum keluar...")
        # Simpan metrik terakhir
        win_rate = (bot.winning_positions / bot.total_positions) * 100 if bot.total_positions > 0 else 0
        compensation_success_rate = (
            (bot.successful_compensation_positions / bot.compensation_positions) * 100
            if bot.compensation_positions > 0 else 0
        )
        metrics = [
            ["Total Positions", bot.total_positions],
            ["Winning Positions", bot.winning_positions],
            ["Win Rate", f"{win_rate:.2f}%"],
            ["Total Profit", f"Rp{bot.total_profit}"],
            ["Compensation Positions", bot.compensation_positions],
            ["Successful Compensation Positions", bot.successful_compensation_positions],
            ["Compensation Success Rate", f"{compensation_success_rate:.2f}%"]
        ]
        print(tabulate(metrics, headers=["Metric", "Value"], tablefmt="grid"))
        # Simpan ke Google Sheets atau sistem log
        nama = 'Andi Arif R.'
        saldo_awal = 5000000
        saldo_sekarang = bot.checkbalance()
        total_profit_loss = saldo_sekarang - saldo_awal
        bot.update_transaction_to_google_sheet(
            nama,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            saldo_awal,
            saldo_sekarang,
            total_profit_loss,
        )
        print("Data sesi berhasil disimpan.")
        logging.info("Data sesi berhasil disimpan.")
    def signal_handler(sig, frame):
        global bot  # Pastikan `bot` dapat diakses
        session.save_session_data(bot)
        print("Keluar dari program. Sampai jumpa!")
        exit(0)
