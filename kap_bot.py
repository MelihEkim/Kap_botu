import time
import telegram
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


TELEGRAM_BOT_TOKEN = 'XXXXXXXXXXXXXXXXXXXXX'
TELEGRAM_CHAT_ID = 'XXXXXXXXXXXXXXXXX'

KONTROL_ARALIGI_SANIYE = 90
BİLDİRİM_ANAHTAR_KELİMESİ = "Yeni İş İlişkisi"
KAP_URL = 'https://www.kap.org.tr/tr/bildirim-sorgu'

YENİDEN_BASLATMA_DONGUSU = 40

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if 'BURAYA' in TELEGRAM_BOT_TOKEN or 'BURAYA' in TELEGRAM_CHAT_ID:
    logging.critical("LÜTFEN KODUN İÇİNDEKİ TOKEN VE CHAT_ID ALANLARINI DOLDURUN!")
    exit()

try:
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    logging.info("Telegram botu başarıyla başlatıldı.")
except Exception as e:
    logging.error(f"Telegram botu başlatılamadı! Token'ınızı kontrol edin. Hata: {e}")
    exit()

def setup_driver():
    """Selenium WebDriver'ı kurar ve döndürür."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

gonderilmis_bildirimler = set()

def ana_dongu():
    dongu_sayaci = 0
    driver = setup_driver()
    logging.info(f"Tarayıcı hazır. '{BİLDİRİM_ANAHTAR_KELİMESİ}' bildirimleri {KONTROL_ARALIGI_SANIYE} saniyede bir taranacak.")

    while True:
        dongu_sayaci += 1
        
        if dongu_sayaci > YENİDEN_BASLATMA_DONGUSU:
            logging.info(f"{YENİDEN_BASLATMA_DONGUSU} döngü tamamlandı. Tarayıcı stabilite için yeniden başlatılıyor...")
            driver.quit()
            driver = setup_driver()
            dongu_sayaci = 0 # Sayacı sıfırla
            logging.info("Yeni tarayıcı oturumu başlatıldı.")

        try:
            logging.info(f"Döngü {dongu_sayaci}/{YENİDEN_BASLATMA_DONGUSU}. KAP sitesi taranıyor...")
            driver.get(KAP_URL)
            
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.disclosure-list-item"))
            )
            
            bildirim_satirlari = driver.find_elements(By.CSS_SELECTOR, "div.disclosure-list-item")
            
            yeni_bildirimler = []
            for satir in bildirim_satirlari:
                satir_text = satir.text.lower()
                if BİLDİRİM_ANAHTAR_KELİMESİ.lower() in satir_text:
                    bildirim_id = satir.text 
                    if bildirim_id not in gonderilmis_bildirimler:
                        link_elementi = satir.find_element(By.TAG_NAME, "a")
                        link = link_elementi.get_attribute('href')
                        
                        mesaj = (
                            f"🚨 **Yeni İş İlişkisi Bildirimi** 🚨\n\n"
                            f"```{satir.text}```\n\n"
                            f"🔗 [KAP BİLDİRİM DETAYLARI]({link})"
                        )
                        yeni_bildirimler.append((mesaj, bildirim_id))

            for mesaj, bildirim_id in reversed(yeni_bildirimler):
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mesaj, parse_mode='Markdown')
                logging.info(f"Yeni bildirim gönderildi: {bildirim_id.splitlines()[0]}")
                gonderilmis_bildirimler.add(bildirim_id)
            
            time.sleep(KONTROL_ARALIGI_SANIYE)

        except Exception as e:
            logging.error(f"Ana döngüde bir hata oluştu (muhtemelen tarayıcı çöktü): {e}")
            logging.info("Tarayıcı yeniden başlatılacak ve 2 dakika beklenecek...")
            driver.quit()
            time.sleep(120)
            driver = setup_driver()
            dongu_sayaci = 0 

if __name__ == "__main__":
    ana_dongu()
