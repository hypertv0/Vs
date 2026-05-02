import re
import sys
import time
import os
from playwright.sync_api import sync_playwright

# --- Ayarlar ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"

def find_working_domain(context):
    print("\n🔍 Çalışan Varsports domaini aranıyor...")
    for num in range(104, 115):
        test_url = f"https://varsports{num}.shop/"
        page = context.new_page()
        try:
            print(f"Deneyiyor: {test_url}", end="\r")
            response = page.goto(test_url, timeout=8000, wait_until='domcontentloaded')
            if response and response.ok:
                final_url = page.url.rstrip('/')
                if not any(x in page.title().lower() for x in ["cloudflare", "just a moment", "bekleyin"]):
                    print(f"\n✅ Bulundu: {final_url}")
                    page.close()
                    return final_url
        except:
            pass
        finally:
            page.close()
    return None

def get_iframe_base(context, domain):
    print("🔍 Ana sayfadan güncel Iframe (Player) altyapısı çekiliyor...")
    page = context.new_page()
    iframe_base = None

    # 1. Yöntem: Ağ trafiğinden ana sayfada yüklenen iframe'i yakalama
    def intercept_iframe(request):
        nonlocal iframe_base
        if "/player/" in request.url and "?id=" in request.url:
            # ?id= kısmından öncesini alıyoruz ki diğer kanallara baz (base) olsun
            iframe_base = request.url.split("?id=")[0]

    page.on("request", intercept_iframe)
    try:
        # Sitenin ana sayfasına git ve arka planda ağ trafiğinin (ve player'ın) yüklenmesini bekle
        page.goto(domain, timeout=15000, wait_until="networkidle")
        page.wait_for_timeout(3000) 
    except:
        pass
    finally:
        page.remove_listener("request", intercept_iframe)

    # 2. Yöntem (Yedek): Eğer ağdan yakalayamazsa sayfa kaynağında iframe ara
    if not iframe_base:
        content = page.content()
        match = re.search(r'(https?://[^"\'\s<>]+?/player/[^"\'\s<>]+?\.php)\?id=\d+', content)
        if match:
            iframe_base = match.group(1)

    page.close()

    if iframe_base:
        print(f"✅ Iframe altyapısı bulundu: {iframe_base}")
    else:
        print("❌ Iframe altyapısı bulunamadı! Site yapısı değişmiş olabilir.")
        
    return iframe_base

def main():
    with sync_playwright() as p:
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
            print("\n❌ Çalışan ana domain bulunamadı.")
            return

        # Zeka kısmı: Ana site üzerinden player Iframe URL'sini dinamik buluyoruz
        iframe_base = get_iframe_base(context, domain)
        if not iframe_base:
            return

        # Kanal Listesi (Sitenin ID'leri)
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
        global_playlist = ["#EXTM3U"]
        
        page = context.new_page()

        for channel_id, (name, tvg_id) in channels.items():
            print(f"📡 Çekiliyor: {name} (ID: {channel_id})...", end=" ")
            try:
                # Dinamik bulduğumuz Iframe URL'sine o anki kanalın ID'sini ekliyoruz
                url = f"{iframe_base}?id={channel_id}"
                m3u8_links =[]

                def handle_req(request):
                    url_str = request.url
                    # Sadece .m3u8 uzantılı, içinde md5= ve expires= tokenları olan linkleri yakala
                    if ".m3u8" in url_str.lower() and "md5=" in url_str.lower() and "expires=" in url_str.lower():
                        m3u8_links.append(url_str)

                page.on("request", handle_req)
                
                # Cloudflare'a takılmamak için Referer (Gelinen Yer) olarak ana siteyi gösteriyoruz
                page.set_extra_http_headers({"Referer": f"{domain}/"})
                
                # Iframe'in (Yani Player'ın) içine direkt giriyoruz
                page.goto(url, timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000) # Linklerin ağ trafiğine düşmesi için bekle
                
                captured_url = None
                if m3u8_links:
                    # Gönderdiğin trafiği analiz ettim. Yayın iki parçadır. Biri ana (index), diğeri ses (mono/tracks). 
                    # Biz içinde 'index' olan ana listeyi istiyoruz.
                    for link in m3u8_links:
                        if "index.m3u8" in link.lower():
                            captured_url = link
                            break
                    # Eğer index yoksa, mecburen bulduğumuz ilk linki al
                    if not captured_url:
                        captured_url = m3u8_links[0]

                if captured_url:
                    content =[
                        "#EXTM3U",
                        f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}",{name}',
                        f"#EXTVLCOPT:http-user-agent={USER_AGENT}",
                        # Oynatıcılarda sıkıntı çıkmaması için Referer olarak Iframe'i veriyoruz
                        f"#EXTVLCOPT:http-referrer={iframe_base}/",
                        captured_url
                    ]

                    # Dosyaya kaydetme
                    clean_name = re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")
                    with open(os.path.join(output_dir, f"{clean_name}.m3u8"), "w", encoding="utf-8") as f:
                        f.write("\n".join(content))

                    # Genel listeye ekleme
                    global_playlist.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}",{name}')
                    global_playlist.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
                    global_playlist.append(f"#EXTVLCOPT:http-referrer={iframe_base}/")
                    global_playlist.append(captured_url)
                    
                    print("✅")
                else:
                    print("❌ Link yakalanamadı.")

            except Exception as e:
                print("⚠️ Zaman Aşımı / Hata")
            finally:
                page.remove_listener("request", handle_req)

        # Tüm m3u8 listesini tek dosya yap
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(global_playlist))

        browser.close()
        print("\n🎉 İşlem bitti. Dosyalar ExoPlayer / IPTV uyumlu hale getirildi.")

if __name__ == "__main__":
    main()
