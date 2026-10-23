# راهنمای استقرار (Production)

این راهنما برای یک سرور لینوکسی (Ubuntu 22.04/24.04) با **Nginx + gunicorn + PostgreSQL** نوشته شده است.
فایل‌های نمونه در پوشه‌ی `deploy/` هستند. مسیر فرضی پروژه `/srv/nutrition_clinic` و کاربر اجرا `clinic` است.

## ۱. پیش‌نیازها
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv postgresql nginx certbot python3-certbot-nginx git
sudo adduser --system --group --home /srv/nutrition_clinic clinic
sudo mkdir -p /var/log/nutrition_clinic /var/backups/nutrition_clinic
sudo chown clinic: /var/log/nutrition_clinic /var/backups/nutrition_clinic
```
Python 3.11 تا 3.13 پشتیبانی می‌شود (روی 3.12+ بسته‌ی `setuptools` از requirements نصب می‌شود).

## ۲. کد و محیط مجازی
```bash
sudo -u clinic -H bash
cd /srv/nutrition_clinic
git clone <آدرس مخزن> .
python3.11 -m venv venv
venv/bin/pip install -r requirements.txt
```
فایل CSS نهایی (`clinic.build.css`) داخل مخزن است؛ روی سرور به Node نیازی نیست.

## ۳. دیتابیس PostgreSQL
```bash
sudo -u postgres psql
CREATE USER nutrition_clinic WITH PASSWORD '<رمز قوی>';
CREATE DATABASE nutrition_clinic OWNER nutrition_clinic ENCODING 'UTF8';
\q
```

## ۴. فایل `.env`
از `.env.example` کپی کنید و مقادیر را تکمیل کنید. حداقل موارد لازم:
```env
DEBUG=False
SECRET_KEY=<خروجی: python -c "import secrets; print(secrets.token_urlsafe(50))">
ALLOWED_HOSTS=example.com,www.example.com
CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com

DB_ENGINE=postgres
DB_NAME=nutrition_clinic
DB_USER=nutrition_clinic
DB_PASSWORD=<رمز>
DB_HOST=127.0.0.1
DB_PORT=5432

CACHE_BACKEND=database
RATELIMIT_IP_HEADER=HTTP_X_REAL_IP
SECURE_HSTS_SECONDS=3600

PAYMENT_GATEWAY=zarinpal
ZARINPAL_MERCHANT_ID=<مرچنت‌کد>
ZARINPAL_SANDBOX=False

SMS_BACKEND=apps.accounts.sms.KavenegarSMSBackend
SMS_API_KEY=<کلید کاوه‌نگار>
SMS_TEMPLATE=<نام قالب verify در پنل کاوه‌نگار>

ADMINS=admin@example.com
```
```bash
chmod 600 .env
```

## ۵. آماده‌سازی برنامه
```bash
venv/bin/python manage.py migrate
venv/bin/python manage.py createcachetable      # برای CACHE_BACKEND=database
venv/bin/python manage.py collectstatic --noinput
venv/bin/python manage.py createsuperuser
venv/bin/python manage.py check --deploy        # فقط دو هشدار HSTS (زیردامنه/preload) عادی است
# اختیاری: محتوای نمونه (فقط فیلدهای خالی را پر می‌کند)
venv/bin/python manage.py seed_demo_content
```

## ۶. gunicorn (systemd)
```bash
sudo cp deploy/gunicorn.service.example /etc/systemd/system/nutrition_clinic.service
sudo systemctl daemon-reload
sudo systemctl enable --now nutrition_clinic
sudo systemctl status nutrition_clinic
```

## ۷. Nginx و HTTPS
```bash
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/nutrition_clinic
# example.com را عوض کنید
sudo ln -s /etc/nginx/sites-available/nutrition_clinic /etc/nginx/sites-enabled/
sudo certbot --nginx -d example.com -d www.example.com
sudo nginx -t && sudo systemctl reload nginx
```
پس از اطمینان از کارکرد HTTPS روی همه‌ی آدرس‌ها، `SECURE_HSTS_SECONDS` را به `31536000` برسانید.

## ۸. cron
```bash
sudo -u clinic crontab deploy/crontab.example
```
شامل: انقضای نوبت‌ها و سفارش‌های پرداخت‌نشده (هر ۵ دقیقه)، پاک‌سازی sessionها و پشتیبان‌گیری روزانه.

## ۹. بررسی نهایی
- `https://example.com/health/` ⇒ `{"status": "ok", "database": true}`
- `https://example.com/robots.txt` و `https://example.com/sitemap.xml`
- یک نوبت و یک سفارش آزمایشی با **زرین‌پال sandbox** (`ZARINPAL_SANDBOX=True` و یک UUID دلخواه به‌عنوان مرچنت) تا انتها؛ بعد از تأیید callback، مرچنت واقعی و `ZARINPAL_SANDBOX=False`.
- بازیابی رمز با شماره‌ی خودتان (ارسال پیامک واقعی).
- آدرس sitemap را در Google Search Console ثبت کنید.

## به‌روزرسانی نسخه
```bash
cd /srv/nutrition_clinic
sudo -u clinic git pull
sudo -u clinic venv/bin/pip install -r requirements.txt
sudo -u clinic venv/bin/python manage.py migrate
sudo -u clinic venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart nutrition_clinic
```

## پشتیبان و بازیابی
اسکریپت `deploy/backup.sh` هر روز از دیتابیس (`pg_dump -Fc`) و پوشه‌ی `media` نسخه می‌گیرد و ۱۴ روز نگه می‌دارد.
پیشنهاد می‌شود پوشه‌ی پشتیبان به فضای دیگری (سرور دوم یا فضای ابری) هم کپی شود.

بازیابی:
```bash
sudo systemctl stop nutrition_clinic
pg_restore -h 127.0.0.1 -U nutrition_clinic -d nutrition_clinic --clean --if-exists /var/backups/nutrition_clinic/db-YYYYMMDD-HHMM.dump
tar -xzf /var/backups/nutrition_clinic/media-YYYYMMDD-HHMM.tar.gz -C /srv/nutrition_clinic
sudo systemctl start nutrition_clinic
```

## لاگ‌ها
```bash
journalctl -u nutrition_clinic -f          # برنامه (شامل خطاها و هشدارهای امنیتی)
tail -f /var/log/nutrition_clinic/cron.log # کارهای زمان‌بندی‌شده
tail -f /var/log/nginx/error.log
```
