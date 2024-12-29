from modules import requests, datetime, logging, pytz, time, ThreadPoolExecutor, retry, stop_after_attempt, wait_exponential, timedelta


class fetcher:
    def get_time_from_url(url, timeout=10):
        """Mendapatkan waktu dari header respons server pada URL tertentu."""
        try:
            # Kirim permintaan GET ke URL dengan timeout
            response = requests.get(url, timeout=timeout)
            
            # Periksa apakah permintaan berhasil
            if response.status_code == 200:
                # Ambil header 'Date' yang berisi waktu server
                server_time_str = response.headers.get('Date')
                if server_time_str:
                    # Mengonversi string waktu ke objek datetime
                    server_time = datetime.strptime(server_time_str, "%a, %d %b %Y %H:%M:%S GMT")
                    server_time = pytz.utc.localize(server_time)  # Pastikan waktu berada di UTC
                    logging.info(f"Waktu server dari URL {url}: {server_time}")
                    return server_time
                else:
                    logging.error("Header 'Date' tidak ditemukan.")
                    return None
            else:
                logging.error(f"Permintaan gagal dengan status code: {response.status_code}")
                return None
        
        except requests.Timeout:
            logging.error("Permintaan timeout.")
            return None
        except requests.RequestException as e:
            logging.error(f"Terjadi kesalahan dalam permintaan HTTP: {e}")
            return None

    def get_server_time_from_url(url):
        """Mengambil waktu dari server menggunakan URL dan mengembalikan waktu tersebut."""
        server_time = fetcher.get_time_from_url(url)
        if server_time:
            return server_time
        else:
            # Jika gagal mengambil waktu dari URL, fallback ke waktu sistem (UTC)
            logging.warning("Fallback ke waktu sistem karena gagal mendapatkan waktu dari server.")
            return datetime.now(pytz.utc)

    def get_ntp_time(url, retries=10, delay=1, timeout=10):
        """Mencoba untuk mendapatkan waktu dari server dengan beberapa kali percakapan ulang."""
        attempt = 0
        while attempt < retries:
            try:
                # Ambil waktu server dari URL
                ntp_time = fetcher.get_server_time_from_url(url)  
                if ntp_time is not None:
                    logging.info(f"Waktu berhasil diambil dari server: {ntp_time}")
                    return ntp_time
                else:
                    logging.error("Gagal mendapatkan waktu yang valid dari server.")
                    raise ValueError("Failed to get valid time from server.")
            except Exception as e:
                logging.error(f"Error getting time from server: {e}")
                attempt += 1
                if attempt < retries:
                    logging.info(f"Mencoba lagi dalam {delay} detik...")
                    time.sleep(delay)  # Tunggu beberapa detik sebelum mencoba lagi
                else:
                    logging.error("Gagal mendapatkan waktu setelah beberapa kali percakapan ulang.")
                    raise ValueError("Failed to get time after multiple retries")


    def get_price_url(base_url="https://api.binomo1.com/candles/v1", symbol="Z-CRY%2FIDX", formatted_time=None, interval="60", locale="en"):
        try:
            if not formatted_time:
                # Ambil waktu dari server NTP
                current_time = fetcher.get_ntp_time(url = 'https://binomo1.com/trading')
                # Format waktu sesuai dengan kebutuhan (misalnya, hanya hari tanpa waktu)
                formatted_time = current_time.strftime('%Y-%m-%dT00:00:00') 
            url = f"{base_url}/{symbol}/{formatted_time}/{interval}?locale={locale}"
            return url
        except Exception as e:
            logging.error(f"Error generating price URL: {e}")
            raise ValueError("Failed to generate price URL")
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_data_for_day(end_time, day_offset):
        try:
            # Tentukan waktu saat ini dengan offset hari menggunakan NTP
            current_time = fetcher.get_ntp_time(url = 'https://binomo1.com/trading') - timedelta(days=day_offset)
            formatted_time = current_time.strftime('%Y-%m-%dT00:00:00')  # Format waktu hari

            # Tentukan URL yang sesuai untuk data harga
            url = fetcher.get_price_url(formatted_time=formatted_time)

            # Ambil data dari URL
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Akan melempar exception jika status code bukan 200

            # Mengambil JSON dari response
            data = response.json()

            # Validasi data yang diterima
            if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                logging.info(f"Data berhasil diambil untuk {formatted_time}.")
                return data['data']
            else:
                logging.error(f"Format data tidak valid atau kosong untuk {formatted_time}: {data}")
                return []
        except requests.RequestException as e:
            logging.error(f"Error mengambil data harga untuk {formatted_time}: {e}")
            raise  # Supaya retry bekerja sesuai dengan logika retry
        
    def fetch_historical_data(days=7):
        end_time = fetcher.get_ntp_time(url = 'https://binomo1.com/trading')  # Ambil waktu dari NTP
        all_close_prices, all_high_prices, all_low_prices, all_open_prices = [], [], [], []

        with ThreadPoolExecutor() as executor:
            # Melakukan eksekusi paralel untuk mengambil data
            results = list(executor.map(lambda day: fetcher.safe_execute(fetcher.fetch_data_for_day, end_time, day), range(days)))

        # Memproses hasil dari setiap hari
        for day_data in results:
            if day_data:
                all_close_prices.extend([entry.get('close') for entry in day_data])
                all_high_prices.extend([entry.get('high') for entry in day_data])
                all_low_prices.extend([entry.get('low') for entry in day_data])
                all_open_prices.extend([entry.get('open') for entry in day_data])

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