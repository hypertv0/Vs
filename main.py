import re
import sys
import time
import os
from playwright.sync_api import sync_playwright

# --- Ayarlar ---
# Ağ trafiğinden aldığımız orijinal User-Agent (CDN'ler kısa ajanları engelleyebilir, bu daha güvenli)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"

def find_working_domain(context):
    print("\n🔍 Çalışan Varsports domaini aranıyor...")
    # Genelde 100'den başlar 120'ye kadar gider, sen bu aralığı kendine göre değiştirebilirsin
    for num in range(104, 115):
        test_url = f"https://varsports{num}.shop/"
        page = context.new_page()
        try:
            print(f"Denaniyor: {test_url}", end="\r")
            response = page.goto(test_url, timeout=8000, wait_until='domcontentloaded')
            if response and response.ok:
                final_url = page.url.rstrip('/')
                # Cloudflare kontrolü
                if not any(x in page.title().lower() for x in["cloudflare", "just a moment", "bekleyin"]):
                    print(f"\n✅ Bulundu: {final_url}")
                    page.close()
                    return final_url
        except:
            pass
        finally:
            page.close()
    return None

def main():
    with sync_playwright() as p:
        # Cloudflare'a takılmamak için bazı ekstra parametreler eklendi
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 720}
        )

        domain = find_working_domain(context)
        if not domain:
            print("\n❌ Çalışan domain bulunamadı.")
            return

        # Kanallar ve ID eşleşmeleri. 
        # Ağ trafiğinde id=602 gördüğümüz için örnek olarak Bein1'e 602 verdim.
        # Sitenin kaynak kodundan diğer kanalların ID'lerini bulup burayı DEĞİŞTİRMELİSİN.
        channels = {
            "602": ("Bein Sports 1 HD", "BeinSports1.tr"),
            "603": ("Bein Sports 2 HD", "BeinSports2.tr"),
            "604": ("Bein Sports 3 HD", "BeinSports3.tr"),
            "605": ("Bein Sports 4 HD", "BeinSports4.tr"),
            "700": ("S Sport 1 HD", "SSport1.tr"),
            "701": ("S Sport 2 HD", "SSport2.tr"),
            "710": ("Tivibu Spor 1 HD", "TivibuSpor1.tr"),
            "720": ("Smart Spor HD", "SmartSpor1.tr"),
            "730": ("TRT Spor HD", "TRTSpor.tr"),
            "740": ("A Spor HD", "ASpor.tr")
        }

        output_dir = "kanallar"
        os.makedirs(output_dir, exist_ok=True)
        global_playlist =["#EXTM3U"]
        
        page = context.new_page()

        for channel_id, (name, tvg_id) in channels.items():
            print(f"📡 Çekiliyor: {name} (ID: {channel_id})...", end=" ")
            try:
                # Site yapısına göre kanala gitme URL'si (Site değiştikçe burayı güncellemen gerekebilir)
                # Direkt iframe'e gitmek m3u8 yakalamayı kolaylaştırabilir:
                url = f"https://benunluyumaskim.betconnectiframecdn1000.shop/player/player2.php?id={channel_id}"
                
                captured_url = None

                def handle_req(request):
                    nonlocal captured_url
                    # Ağ trafiğindeki .m3u8 dosyalarını yakala
                    if ".m3u8" in request.url.lower():
                        # Alt kalite dosyaları (mono, tracks vb.) yerine ana listeyi almak için filtreleme
                        if "tracks" not in request.url.lower() and "mono" not in request.url.lower():
                            captured_url = request.url

                page.on("request", handle_req)
                
                # İlgili yayın sayfasına git
                page.goto(url, timeout=15000, wait_until="networkidle")
                page.wait_for_timeout(4000) # Linkin ağa düşmesi için bekleme süresi

                if captured_url:
                    # --- M3U8 Dosya İçeriği Oluşturma ---
                    content =[
                        "#EXTM3U",
                        f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}",{name}',
                        f"#EXTVLCOPT:http-user-agent={USER_AGENT}",
                        f"#EXTVLCOPT:http-referrer={domain}/",
                        captured_url
                    ]

                    # 1. Tekil Dosya Olarak Kaydet
                    clean_name = re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")
                    with open(os.path.join(output_dir, f"{clean_name}.m3u8"), "w", encoding="utf-8") as f:
                        f.write("\n".join(content))

                    # 2. Genel Listeye Ekle
                    global_playlist.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}",{name}')
                    global_playlist.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
                    global_playlist.append(f"#EXTVLCOPT:http-referrer={domain}/")
                    global_playlist.append(captured_url)
                    
                    print("✅")
                else:
                    print("❌ Link yakalanamadı.")

            except Exception as e:
                print("⚠️ Zaman Aşımı/Hata")
            finally:
                page.remove_listener("request", handle_req)

        # Tüm listeyi kaydet
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(global_playlist))

        browser.close()
        print("\n🎉 İşlem bitti. Yeni tokenli m3u8 dosyaları oluşturuldu.")

if __name__ == "__main__":
    main()
