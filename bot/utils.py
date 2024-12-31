from modules import pyotp, csv, os, load_dotenv, logging

# Konfigurasi logging
# logging.basicConfig(filename='trading_bot.log', level=logging.INFO,
#                     format='%(asctime)s - %(levelname)s - %(message)s')

secret_key = 'GB2NQ7ABZFKCAM4RWYQFP76Y6LTQ7J2V'
username = 'andiarifrahmatullah@gmail.com'
password = '@Rahmatullah07'
bot = None

# Inisialisasi TOTP
totp = pyotp.TOTP(secret_key)

logs_dir = 'Opt-Trade/bot/logs'
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)
    
csv_file = os.getenv('CSV_FILE', 'Opt-Trade/bot/logs/trading_log.csv')
historical_data_file = os.getenv('HISTORICAL_DATA_FILE', 'Opt-Trade/bot/logs/historical_data.csv')

# Cek apakah file ada, jika tidak, buat file kosong
if not os.path.exists(csv_file):
    with open(csv_file, 'w') as file:
        writer = csv.writer(file)
        writer.writerow([
            'timestamp', 'direction', 'market_condition', 'int(compensation)', 'int(profit_or_loss)', 'entry_price', 'close_price'
        ])
if not os.path.exists(historical_data_file):
    with open(historical_data_file, 'w') as file:
        writer = csv.writer(file)
        writer.writerow([
            'timestamp', 'ma_short', 'ma_long', 'rsi', 'roc', 'williams_r',
            'momentum', 'macd', 'macd_signal', 'bollinger_mean',
            'bollinger_upper', 'bollinger_lower', 'atr', 'parabolic',
            'adx', 'high', 'low', 'open', 'close', 'direction', 'market_condition', 'correction'
        ])

Iterate = int(os.getenv('ITERATE', 1))
max_positions = int(os.getenv('MAX_POSITIONS', 1620))
max_loss = int(os.getenv('MAX_LOSS', -30000000))
target_profit = int(os.getenv('TARGET_PROFIT', 100000000))
url = "https://binomo1.com/trading"
