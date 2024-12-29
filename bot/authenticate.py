from modules import WebDriverWait, StaleElementReferenceException, TimeoutException, logging, By, NoSuchElementException, sleep, EC, Keys, Service, webdriver
from utils import username, password, secret_key, totp
from fetcher import fetcher
from autotrade import autotrade

class authenticate:
    def __init__(self):
        service = Service('./drivers/chromedriver.exe')  # Sesuaikan path chromedriver
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-extensions")
        options.add_argument('--headless')
        options.add_argument("--no-sandbox")
        options.add_argument("--disk-cache-size=0")
        options.add_argument("--disable-application-cache")
        options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(service=service, options=options)
        
    def close_ad_if_exists(driver):
        try:
            # Cari elemen berdasarkan XPath
            ad_element = driver.find_element(By.XPATH, '/html/body/ng-component/vui-modal/div/button')
            if ad_element.is_displayed():  # Pastikan elemen terlihat
                ad_element.click()  # Klik untuk menutup
                print("Iklan ditemukan dan berhasil ditutup.")
            else:
                print("Elemen iklan ditemukan, tapi tidak terlihat.")
        except Exception:
            # Jika elemen tidak ditemukan, lanjutkan tanpa error
            print("Tidak ada iklan yang perlu ditutup.")
    def login(self):
        TWO_FACTOR_INPUT_XPATH = '/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/ng-component/div/div/auth-form/sa-auth-form/div[2]/div/app-two-factor-auth-validation/app-otp-validation-form/form/platform-forms-input/way-input/div/div/way-input-text/input'
        
        try:
            self.driver.get('https://binomo1.com/auth?a=5b9215a90cb8')
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/ng-component/div/div/auth-form/sa-auth-form/div[2]/div/app-sign-in/div/form/div[1]/platform-forms-input/way-input/div/div[1]/way-input-text/input'))
            )
            self.enter_credentials()
            try:
                two_factor_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, TWO_FACTOR_INPUT_XPATH))
                )
                if two_factor_input is not None:
                    self.enter_two_factor_code()
                    logging.info("2FA code entered successfully.")
            except TimeoutException:
                logging.info("2FA not required.")
            sleep(2)
        except TimeoutException as e:
            logging.error(f"Timeout while loading login page or waiting for elements: {e}")
            self.screenshot()
            raise
        except NoSuchElementException as e:
            logging.error(f"Element not found during login: {e}")
            self.screenshot()
            raise
        except Exception as e:
            logging.error(f"Unexpected error during login: {e}")
            self.screenshot()
            raise
    def enter_credentials(self):
        max_attempts = 3  # Number of attempts to retry
        for attempt in range(max_attempts):
            try:
                email_xpath = '/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/ng-component/div/div/auth-form/sa-auth-form/div[2]/div/app-sign-in/div/form/div[1]/platform-forms-input/way-input/div/div[1]/way-input-text/input'
                passcode_xpath = '/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/ng-component/div/div/auth-form/sa-auth-form/div[2]/div/app-sign-in/div/form/div[2]/platform-forms-input/way-input/div/div/way-input-password/input'
                
                email = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, email_xpath)))
                passcode = self.driver.find_element(By.XPATH, passcode_xpath)
                
                email.send_keys(username)
                passcode.send_keys(password)
                passcode.send_keys(Keys.ENTER)
                return  # Exit the loop if successful
                
            except (StaleElementReferenceException, NoSuchElementException) as e:
                logging.warning(f"Attempt {attempt + 1} failed with error: {e}. Retrying...")
                sleep(2)  # Wait before retrying
        # If all attempts fail, raise the exception
        logging.error("All attempts to enter credentials failed.")
        self.screenshot()
        raise Exception("Failed to enter credentials after multiple attempts")
    def enter_two_factor_code(self):
        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/ng-component/div/div/auth-form/sa-auth-form/div[2]/div/app-two-factor-auth-validation/app-otp-validation-form/form/platform-forms-input/way-input/div/div/way-input-text/input'))
            )
            two_fa_code = totp.now()
            two_fa_input = self.driver.find_element(By.XPATH, '/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/ng-component/div/div/auth-form/sa-auth-form/div[2]/div/app-two-factor-auth-validation/app-otp-validation-form/form/platform-forms-input/way-input/div/div/way-input-text/input')
            two_fa_input.send_keys(two_fa_code)
            two_fa_input.send_keys(Keys.ENTER)
        except NoSuchElementException as e:
            logging.error(f"2FA elements not found: {e}")
            self.screenshot()
            raise
    def get_current_coin(self):
        try:
            coin_xpath = '/html/body/binomo-root/platform-ui-scroll/div/div/platform-layout-header/header/div[2]/ng-component/div/div/div/multi-asset-tab/section/button/div/div/span[1]'
            coin_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, coin_xpath))
            )
            coin_name = coin_element.text
            return coin_name
        except NoSuchElementException as e:
            logging.error(f"Coin element not found: {e}")
            self.screenshot()
            return None
        except Exception as e:
            logging.error(f"Unexpected error while getting current coin: {e}")
            self.screenshot()
            return None
        
    def select_crypto_idx(self):
        for id_value in range(1, 6):
            try:
                crypto_idx_xpath = f'/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/main/div/div/div[{id_value}]/ng-component/div/div/canvas'
                crypto_idx_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, crypto_idx_xpath))
                )
                crypto_idx_element.click()
                logging.info(f"Koin berhasil diubah ke Crypto IDX dengan ID {id_value}.")
                return True
            except (TimeoutException, NoSuchElementException) as e:
                logging.warning(f"Percobaan dengan ID {id_value} gagal menemukan Crypto IDX: {e}")
        logging.error("Tidak dapat menemukan Crypto IDX dengan ID dari 1 hingga 5. Melewatkan trading.")
        return False
    def select_account_type(self, account_type):
        def attempt_select_account_type():
            try:
                account_switcher = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="account"]'))
                )
                account_switcher.click()
                sleep(1)
                account_types = {
                    'Real': '/html/body/vui-popover/div[2]/account-list/div[1]',
                    'Demo': '/html/body/vui-popover/div[2]/account-list/div[2]',
                    'Tournament': '/html/body/vui-popover/div[2]/account-list/div[3]'
                }
                if account_type in account_types:
                    account_element = self.driver.find_element(By.XPATH, account_types[account_type])
                    account_element.click()
                    logging.info(f"Switched to {account_type} account.")
                    sleep(1)
                else:
                    logging.error(f"Account type '{account_type}' not recognized.")
            except TimeoutException as e:
                logging.error(f"Timeout while switching account type: {e}")
                self.screenshot()
                raise
            except NoSuchElementException as e:
                logging.error(f"Element not found while switching account type: {e}")
                self.screenshot()
                raise
            except Exception as e:
                logging.error(f"Unexpected error while switching account type: {e}")
                self.screenshot()
                raise
        return self.retry(attempt_select_account_type)
    def retry(self, func, retries=3, delay=2):
        for attempt in range(1, retries + 1):
            try:
                result = func()
                return result
            except (NoSuchElementException, TimeoutException) as e:
                logging.error(f"Percobaan {attempt}/{retries} gagal untuk {func.__name__}: {e}")
                sleep(delay)
        logging.error(f"Semua {retries} percobaan gagal untuk {func.__name__}")
        return None
    def checkbalance(self):
        def fetch_balance():
            try:
                balance_xpath = '//*[@id="qa_trading_balance"]'
                balance_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, balance_xpath))
                )
                balance_text = balance_element.text
                logging.debug(f"Raw balance text: {balance_text}")
                
                # Hapus simbol mata uang, spasi, dan format angka lainnya
                balance_text = balance_text.replace('Rp', '').replace('₮', '').replace(',', '').strip()
                
                # Validasi bahwa teks saldo hanya mengandung angka
                if not balance_text.replace('.', '', 1).isdigit():
                    raise ValueError(f"Invalid balance format: {balance_text}")
                
                balance = float(balance_text)
                logging.info(f"Balance retrieved successfully: Rp{balance}")
                return balance
            except NoSuchElementException as e:
                logging.error(f"Balance element not found: {e}")
                self.screenshot()
                return None
            except TimeoutException as e:
                logging.error(f"Timeout waiting for balance element: {e}")
                self.screenshot()
                return None
            except ValueError as e:
                logging.error(f"Error parsing balance text: {e}")
                self.screenshot()
                return None
            except Exception as e:
                logging.error(f"Unexpected error fetching balance: {e}")
                self.screenshot()
                return None
        # Coba mengambil saldo beberapa kali menggunakan metode retry
        return self.retry(fetch_balance)

    # Fungsi untuk mengecek apakah posisi tertutup
    def is_position_closed(self):
        try:
            # XPath elemen timer yang lebih tepat
            timer_xpath = '/html/body/binomo-root/platform-ui-scroll/div/div/ng-component/main/div/div/div[1]/trading-clock/p'
            
            # Tunggu hingga elemen muncul dengan lebih fleksibel
            remaining_time_element = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, timer_xpath))
            )
            
            # Ambil teks dari elemen timer dan hapus spasi ekstra
            remaining_time = remaining_time_element.text.strip()
            
            # Pisahkan waktu dari zona waktu (misalnya "15:43:28 GMT+7" -> "15:43:28")
            time_only = remaining_time.split(" ")[0]  # Ambil hanya jam:menit:detik (misal "15:43:28")
            time_parts = time_only.split(":")  # Pisahkan waktu ke bagian jam, menit, detik
            
            # Pastikan format waktu valid
            if len(time_parts) != 3:
                return True
            
            # Ambil detik dan cek apakah lebih besar atau sama dengan 02
            remaining_seconds = int(time_parts[2])
            
            # Ambil waktu dari server NTP untuk membandingkan dengan waktu yang ada di halaman
            current_time = fetcher.get_ntp_time(url = 'https://binomo1.com/trading')
            
            # Cek jika detik lebih dari 2 atau waktu NTP lebih dari 2 detik
            if remaining_seconds >= 2 or current_time.second > 2:
                return True
            
            return False
        
        except (NoSuchElementException, TimeoutException) as e:
            # Jika elemen tidak ditemukan atau timeout, anggap posisi tertutup
            logging.warning("Element not found or timeout occurred, assuming position is closed.")
            return True
        except Exception as e:
            # Jika ada error lain, anggap posisi tertutup
            logging.error(f"An unexpected error occurred: {e}")
            return True