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

    def intercept_iframe(request):
        nonlocal iframe_base
        if "/player/" in request.url and "?id=" in request.url:
            iframe_base = request.url.split("?id=")[0]

    page.on("request", intercept_iframe)
    try:
        page.goto(domain, timeout=15000, wait_until="networkidle")
        page.wait_for_timeout(3000) 
    except:
        pass
    finally:
        page.remove_listener("request", intercept_iframe)

    if not iframe_base:
        content = page.content()
        match = re.search(r'(https?://[^"\'\s<>]+?/player/[^"\'\s<>]+?\.php)\?id=', content)
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

        iframe_base = get_iframe_base(context, domain)
        if not iframe_base:
            return

        # Sitenin kaynak kodundan (HTML'den) alınan BÜTÜN güncel ID'ler:
        channels = {
            "601": ("Bein Sports 1 HD", "BeinSports1.tr"),
            "602": ("Bein Sports 2 HD", "BeinSports2.tr"),
            "603": ("Bein Sports 3 HD", "BeinSports3.tr"),
            "604": ("Bein Sports 4 HD", "BeinSports4.tr"),
            "605": ("Bein Sports 5 HD", "BeinSports5.tr"),
            "607": ("S Sport 1 HD", "SSport1.tr"),
            "608": ("S Sport 2 HD", "SSport2.tr"),
            "609": ("Smart Spor HD", "SmartSpor1.tr"),
            "610": ("Smart Spor 2 HD", "SmartSpor2.tr"),
            "700": ("Tivibu Spor HD", "TivibuSpor.tr"),
            "701": ("Tivibu Spor 1 HD", "TivibuSpor1.tr"),
            "702": ("Tivibu Spor 2 HD", "TivibuSpor2.tr"),
            "703": ("Tivibu Spor 3 HD", "TivibuSpor3.tr"),
            "704": ("Tivibu Spor 4 HD", "TivibuSpor4.tr"),
            "htspor": ("HT Spor HD", "HTSpor.tr"),
            "cosmosport": ("Cosmo Sports HD", "CosmoSports.tr"),
            "eurosport1": ("Eurosport 1 HD", "Eurosport1.tr"),
            "eurosport2": ("Eurosport 2 HD", "Eurosport2.tr"),
            "trtspor": ("TRT Spor HD", "TRTSpor.tr"),
            "trtspor2": ("TRT Spor Yıldız HD", "TRTSporYildiz.tr"),
            "aspor": ("A Spor HD", "ASpor.tr"),
            "beinsportshaber": ("Bein Sports Haber HD", "BeinSportsHaber.tr"),
            "tabii": ("Tabii Spor HD", "TabiiSpor.tr"),
            "tabii1": ("Tabii Spor 1 HD", "TabiiSpor1.tr"),
            "tabii2": ("Tabii Spor 2 HD", "TabiiSpor2.tr"),
            "tabii3": ("Tabii Spor 3 HD", "TabiiSpor3.tr"),
            "tabii4": ("Tabii Spor 4 HD", "TabiiSpor4.tr"),
            "tabii5": ("Tabii Spor 5 HD", "TabiiSpor5.tr"),
            "tabii6": ("Tabii Spor 6 HD", "TabiiSpor6.tr")
        }

        output_dir = "kanallar"
        os.makedirs(output_dir, exist_ok=True)
        global_playlist =["#EXTM3U"]
        
        page = context.new_page()

        for channel_id, (name, tvg_id) in channels.items():
            print(f"📡 Çekiliyor: {name} (ID: {channel_id})...", end=" ")
            try:
                url = f"{iframe_base}?id={channel_id}"
                m3u8_links =[]

                def handle_req(request):
                    url_str = request.url
                    if ".m3u8" in url_str.lower() and "md5=" in url_str.lower() and "expires=" in url_str.lower():
                        m3u8_links.append(url_str)

                page.on("request", handle_req)
                page.set_extra_http_headers({"Referer": f"{domain}/"})
                
                page.goto(url, timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
                
                captured_url = None
                if m3u8_links:
                    for link in m3u8_links:
                        if "index.m3u8" in link.lower():
                            captured_url = link
                            break
                    if not captured_url:
                        captured_url = m3u8_links[0]

                if captured_url:
                    content =[
                        "#EXTM3U",
                        f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}",{name}',
                        f"#EXTVLCOPT:http-user-agent={USER_AGENT}",
                        f"#EXTVLCOPT:http-referrer={iframe_base}/",
                        captured_url
                    ]

                    clean_name = re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")
                    with open(os.path.join(output_dir, f"{clean_name}.m3u8"), "w", encoding="utf-8") as f:
                        f.write("\n".join(content))

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

        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(global_playlist))

        browser.close()
        print("\n🎉 İşlem bitti. Dosyalar ExoPlayer / IPTV uyumlu hale getirildi.")

if __name__ == "__main__":
    main()
