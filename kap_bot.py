# Gerekli kütüphaneleri içeri aktarıyoruz.
import os
import requests
import time
import telegram
import logging

# --- GÜVENLİK ve KONFİGÜRASYON ---
# Token ve ID gibi hassas bilgileri doğrudan koda yazmıyoruz.
# Bunun yerine Render.com'un "Environment Variables" (Ortam Değişkenleri) özelliğini kullanacağız.
# Bu sayede kodumuz güvende kalır.
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# --- AYARLAR ---
# KAP API'sinin sorgu adresi
KAP_API_URL = 'https://www.kap.org.tr/tr/api/kapt-data-collector/search'

# Her kontrol arasında kaç saniye bekleneceği.
# Engellenme riski olmadan güvenli ve hızlı takip için 30-60 saniye arası idealdir.
KONTROL_ARALIGI_SANIYE = 45

# Takip edilecek bildirimin başlığında geçmesi gereken anahtar kelime
BİLDİRİM_ANAHTAR_KELİMESİ = "Yeni İş İlişkisi"

# --- PROGRAM BAŞLANGICI ---

# Programın çalışması sırasında oluşacak olayları ve hataları kaydetmek için loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Daha önce gönderilen bildirimlerin ID'lerini saklayarak tekrar gönderilmesini önleyen set
gonderilmis_bildirimler = set()

# Programın başında tokenların alınıp alınmadığını kontrol edelim
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logging.critical("HATA: TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID ortam değişkenleri ayarlanmamış!")
    logging.critical("Render.com'da Environment sekmesinden bu değişkenleri eklediğinizden emin olun.")
    exit()

def telegram_bot_baslat():
    """Telegram botunu başlatır ve bir sorun varsa programı durdurur."""
    try:
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        logging.info("Telegram botu başarıyla başlatıldı.")
        return bot
    except Exception as e:
        logging.critical(f"Telegram botu başlatılamadı: {e}")
        return None

def kap_verilerini_cek():
    """KAP API'sinden en güncel bildirimleri çeker."""
    # API'ye gönderilecek arama kriterleri
    payload = {
        "page": 0,          # Her zaman en güncel sayfa olan 0. sayfayı getir
        "size": 25,         # Son 25 bildirimi kontrol et (yeterli bir sayıdır)
        "sort": "date,desc",# Bildirimleri en yeniden eskiye doğru sırala
        "q": BİLDİRİM_ANAHTAR_KELİMESİ # Sadece başlığında "Yeni İş İlişkisi" geçenleri ara
    }
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(KAP_API_URL, json=payload, headers=headers, timeout=25)
        response.raise_for_status() # HTTP 4xx veya 5xx hata kodlarında hata fırlat
        return response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        logging.error(f"KAP API'sine erişirken bir ağ hatası oluştu: {e}")
        return None

def ana_dongu(bot):
    """Programın ana çalışma döngüsü. Sürekli olarak KAP'ı kontrol eder."""
    logging.info(f"Sistem başlatıldı. '{BİLDİRİM_ANAHTAR_KELİMESİ}' bildirimleri {KONTROL_ARALIGI_SANIYE} saniyede bir taranacak.")

    while True:
        try:
            bildirimler = kap_verilerini_cek()

            if bildirimler is None:
                logging.warning("Veri çekilemedi, bir sonraki deneme bekleniyor.")
                time.sleep(KONTROL_ARALIGI_SANIYE)
                continue

            # Bildirimleri en eskiden en yeniye doğru işlemek için listeyi ters çeviriyoruz.
            # Bu sayede bildirimler kronolojik sırada gelir.
            for bildirim in reversed(bildirimler):
                disclosure_id = bildirim.get('disclosureId')

                # Eğer bildirim ID'si geçerliyse ve daha önce gönderilmemişse işle
                if disclosure_id and disclosure_id not in gonderilmis_bildirimler:
                    title = bildirim.get('title', 'Başlık Yok')

                    # Başlığın anahtar kelimeyi içerdiğinden emin olalım (büyük/küçük harf duyarsız)
                    if BİLDİRİM_ANAHTAR_KELİMESİ.lower() in title.lower():
                        company_name = bildirim.get('companyName', 'Şirket Adı Yok')
                        stock_codes = bildirim.get('stockCodes', '-')
                        publish_date = bildirim.get('publishDate', 'Tarih Yok')

                        # KAP bildirimine direkt tıklanabilir link oluştur
                        kap_link = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_id}"

                        # Telegram'a gönderilecek mesajı HTML formatında hazırla
                        mesaj = (
                            f"🚨 <b>Yeni İş İlişkisi Bildirimi</b> 🚨\n\n"
                            f"🏢 <b>Şirket:</b> {company_name}\n"
                            f"ℹ️ <b>Hisse Kodu:</b> {stock_codes}\n"
                            f"🗓️ <b>Tarih:</b> {publish_date}\n\n"
                            f"📋 <b>Başlık:</b> {title}\n\n"
                            f"🔗 <a href='{kap_link}'><b>KAP BİLDİRİM DETAYLARI</b></a>"
                        )

                        # Mesajı gönder ve gönderildi olarak işaretle
                        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mesaj, parse_mode='HTML')
                        logging.info(f"Yeni bildirim gönderildi: {company_name} - {title}")
                        gonderilmis_bildirimler.add(disclosure_id)

            # Bir sonraki kontrol döngüsüne kadar bekle
            time.sleep(KONTROL_ARALIGI_SANIYE)

        except Exception as e:
            logging.critical(f"Ana döngüde beklenmedik bir hata oluştu: {e}")
            logging.critical("Program 120 saniye bekleyip yeniden deneyecek.")
            time.sleep(120) # Ciddi bir hatada daha uzun bekle

# --- Programı Çalıştır ---
if __name__ == "__main__":
    telegram_bot = telegram_bot_baslat()
    if telegram_bot:
        ana_dongu(telegram_bot)
    else:
        logging.critical("Bot başlatılamadığı için program sonlandırılıyor.")