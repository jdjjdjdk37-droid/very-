import asyncio
from cloakbrowser import launch_async
import cloudscraper
import re
import random
import string

# ═══════════════════════════════════════════════════════════
# 🎯 الإعدادات
# ═══════════════════════════════════════════════════════════
TARGET_URL = "https://magmanode.com/register"
REGISTER_API = "https://magmanode.com/forms/registration/regcore2.php"

# ═══════════════════════════════════════════════════════════
# 🎲 توليد بيانات عشوائية
# ═══════════════════════════════════════════════════════════
def random_email():
    name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"{name}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com'])}"

def random_username():
    prefixes = ["worm", "user", "player", "gamer", "pro"]
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{random.choice(prefixes)}{suffix}"

def random_password():
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(random.choices(chars, k=random.randint(12, 16)))

# ═══════════════════════════════════════════════════════════
# 🚀 التسجيل باستخدام CloakBrowser (الحل الحقيقي)
# ═══════════════════════════════════════════════════════════
async def register_with_cloakbrowser():
    print("[*] تشغيل CloakBrowser (المتصفح الخفي)...")
    
    # 1. تشغيل المتصفح الخفي
    browser = await launch_async(
        headless=True,      # ضروري لـ VPS
        humanize=True,      # محاكاة حركة الإنسان
        # proxy="http://user:pass@ip:port" # اختياري: إذا كنت تستخدم بروكسي
    )
    
    page = await browser.new_page()
    
    try:
        # 2. زيارة صفحة التسجيل (هنا يتم حل Managed Challenge تلقائياً)
        print(f"[*] زيارة {TARGET_URL}...")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
        
        print("[*] في انتظار حل التحدي...")
        # ننتظر قليلاً حتى يكتمل حل التحدي في الخلفية
        await asyncio.sleep(8)
        
        # 3. استخراج الكوكيز (cf_clearance هو المفتاح)
        cookies = await page.context.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        
        if 'cf_clearance' not in cookie_dict:
            print("[-] لم يتم العثور على cf_clearance. قد يكون التحدي لم يُحل بعد.")
            await browser.close()
            return
        
        print(f"[+] تم الحصول على cf_clearance!")
        
        # 4. توليد بيانات الحساب
        email = random_email()
        username = random_username()
        password = random_password()
        
        print(f"\n📝 الحساب الجديد:")
        print(f"   📧 {email}")
        print(f"   👤 {username}")
        print(f"   🔑 {password}")
        
        # 5. استخدام cloudscraper مع الكوكيز المستخرجة لإتمام التسجيل
        print("\n[*] إرسال طلب التسجيل...")
        scraper = cloudscraper.create_scraper()
        
        # ضع الكوكيز (cf_clearance + أي كوكيز أخرى من الجلسة)
        for name, value in cookie_dict.items():
            scraper.cookies.set(name, value, domain=".magmanode.com")
        
        headers = {
            'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
            'Content-Type': "application/x-www-form-urlencoded",
            'Origin': "https://magmanode.com",
            'Referer': TARGET_URL,
        }
        
        payload = {
            'email': email,
            'username': username,
            'password': password,
            'terms': 'on',
            'cf-turnstile-response': '',  # لا نحتاج للتوكن هنا بعد الآن
            'registerForm': ""
        }
        
        r = scraper.post(REGISTER_API, data=payload, headers=headers, timeout=15, allow_redirects=True)
        
        print(f"\n📡 HTTP: {r.status_code} | 🌐 {r.url} | 📄 {len(r.text)}")
        
        # 6. النتيجة
        if "/login" in r.url and "/register" not in r.url:
            print("\n✅✅✅ نجح التسجيل!")
            print(f"   📧 {email}")
            print(f"   👤 {username}")
            print(f"   🔑 {password}")
        else:
            # استخراج رسالة الخطأ
            errors = re.findall(r'class="[^"]*red[^"]*"[^>]*>([^<]{5,200})', r.text, re.I)
            if errors:
                print(f"\n❌ فشل: {errors[0].strip()}")
            else:
                print(f"\n❌ فشل — سبب غير معروف")
    
    except Exception as e:
        print(f"[-] خطأ: {e}")
    
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(register_with_cloakbrowser())
