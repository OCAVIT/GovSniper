# 🚂 Railway Deploy Guide

Пошаговая инструкция по деплою GovSniper на Railway.

---

## 📋 Что нужно подготовить

### ✅ Checklist перед деплоем

- [ ] GitHub аккаунт
- [ ] Railway аккаунт (зарегистрироваться на [railway.app](https://railway.app))
- [ ] Supabase база данных (создать на [supabase.com](https://supabase.com))
- [ ] OpenAI API ключ (получить на [platform.openai.com](https://platform.openai.com))
- [ ] YooKassa аккаунт (зарегистрироваться на [yookassa.ru](https://yookassa.ru))
- [ ] Resend API ключ (получить на [resend.com](https://resend.com))
- [ ] Proxy для zakupki.gov.ru (купить на [proxy6.net](https://proxy6.net) или аналогах)

---

## 🎯 Шаг 1: Создание Supabase базы данных

### 1.1 Регистрация в Supabase
1. Перейдите на [supabase.com](https://supabase.com)
2. Нажмите "Start your project"
3. Войдите через GitHub

### 1.2 Создание проекта
1. New Project → введите название `govsniper`
2. Выберите регион: **Europe (Frankfurt)** или **Europe (London)**
3. Сгенерируйте сложный пароль (сохраните его!)
4. Нажмите "Create new project"

### 1.3 Получение DATABASE_URL
1. Дождитесь создания проекта (1-2 минуты)
2. Settings → Database → Connection string → URI
3. Скопируйте строку и замените `[YOUR-PASSWORD]` на ваш пароль
4. **ВАЖНО:** Измените порт с `5432` на `6543` (Transaction pooler)

**Пример:**
```
postgresql+asyncpg://postgres.dvwzywmmtiikwyezmhvx:YOUR-PASSWORD@aws-1-eu-central-1.pooler.supabase.com:6543/postgres
```

---

## 🔑 Шаг 2: Получение API ключей

### 2.1 OpenAI API Key
1. Зайдите на [platform.openai.com](https://platform.openai.com)
2. API keys → Create new secret key
3. Скопируйте ключ (начинается с `sk-proj-`)
4. Пополните баланс минимум на $5

### 2.2 YooKassa
1. Зарегистрируйтесь на [yookassa.ru](https://yookassa.ru)
2. Создайте магазин
3. Настройки → Получите:
   - `YOOKASSA_SHOP_ID` (6-7 цифр)
   - `YOOKASSA_SECRET_KEY` (Secret key)

### 2.3 Resend Email
1. Зарегистрируйтесь на [resend.com](https://resend.com)
2. API Keys → Create API Key
3. Скопируйте ключ (начинается с `re_`)
4. **Опционально:** Добавьте свой домен для отправки email

### 2.4 Proxy для zakupki.gov.ru
1. Купите HTTP proxy на [proxy6.net](https://proxy6.net) или аналогах
2. Страна: **Россия**
3. Тип: **HTTP/HTTPS**
4. Скопируйте данные в формате: `http://user:password@ip:port`

---

## 📦 Шаг 3: Загрузка на GitHub

### 3.1 Инициализация Git (если еще не сделано)
```bash
cd e:\VibeProjects\GovSniper
git init
git add .
git commit -m "Initial commit: GovSniper v1.0"
```

### 3.2 Создание репозитория на GitHub

**Вариант A: Через GitHub CLI (рекомендуется)**
```bash
# Установите GitHub CLI: https://cli.github.com/
gh repo create GovSniper --private --source=. --remote=origin --push
```

**Вариант B: Вручную**
1. Создайте репозиторий на [github.com/new](https://github.com/new)
   - Название: `GovSniper`
   - Visibility: **Private** (рекомендуется)
   - НЕ добавляйте README, .gitignore, license
2. Подключите remote:
```bash
git remote add origin https://github.com/YOUR-USERNAME/GovSniper.git
git branch -M main
git push -u origin main
```

---

## 🚂 Шаг 4: Деплой на Railway

### 4.1 Создание проекта Railway

1. Зайдите на [railway.app](https://railway.app)
2. Войдите через GitHub
3. Нажмите **"New Project"**
4. Выберите **"Deploy from GitHub repo"**
5. Найдите и выберите репозиторий `GovSniper`
6. Railway автоматически обнаружит `Dockerfile` и начнет сборку

### 4.2 Настройка переменных окружения

1. В Railway Dashboard откройте ваш проект
2. Перейдите на вкладку **Variables**
3. Нажмите **"RAW Editor"**
4. Вставьте следующие переменные (замените значения на свои):

```env
DATABASE_URL=postgresql+asyncpg://postgres.xxx:password@aws-1-eu-central-1.pooler.supabase.com:6543/postgres
OPENAI_API_KEY=sk-proj-your-key
YOOKASSA_SHOP_ID=your-shop-id
YOOKASSA_SECRET_KEY=your-secret-key
RESEND_API_KEY=re_your-key
EMAIL_FROM=noreply@govsniper.ru
APP_ENV=production
LOG_LEVEL=INFO
REPORT_PRICE=990
PROXY_URL=http://user:password@ip:port
MIN_TENDER_PRICE=100000
STOP_WORDS=["ремонт","уборка","питание","клининг","охрана","стирка"]
SCRAPER_INTERVAL_MINUTES=15
DOCUMENT_INTERVAL_MINUTES=3
ANALYZER_INTERVAL_MINUTES=5
NOTIFICATION_INTERVAL_MINUTES=10
CLEANUP_INTERVAL_HOURS=6
DATA_RETENTION_DAYS=3
RSS_FEED_URL=https://zakupki.gov.ru/epz/order/extendedsearch/rss.html
PORT=8080
```

5. Нажмите **"Save Config"**

### 4.3 Получение домена

1. Railway автоматически сгенерирует домен типа:
   ```
   govsniper-production.up.railway.app
   ```
2. Скопируйте его и вернитесь в **Variables**
3. Добавьте/обновите переменную:
   ```env
   APP_BASE_URL=https://govsniper-production.up.railway.app
   ```
4. Сохраните

### 4.4 Применение миграций

После успешного деплоя нужно применить миграции к БД:

**Вариант A: Через Railway CLI**
```bash
# Установите Railway CLI
npm i -g @railway/cli

# Залогиньтесь
railway login

# Подключитесь к проекту
railway link

# Запустите миграции
railway run alembic upgrade head
```

**Вариант B: Через Railway Dashboard**
1. Settings → Deploy → **Custom Start Command**
2. Добавьте временно:
   ```
   alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port $PORT
   ```
3. Дождитесь редеплоя
4. После успешного деплоя верните команду:
   ```
   uvicorn src.main:app --host 0.0.0.0 --port $PORT
   ```

---

## ✅ Шаг 5: Проверка деплоя

### 5.1 Health Check
```bash
curl https://govsniper-production.up.railway.app/health
```

**Ожидаемый ответ:**
```json
{
  "status": "healthy",
  "timestamp": "2024-02-04T12:00:00.000000",
  "service": "govsniper"
}
```

### 5.2 Database Check
```bash
curl https://govsniper-production.up.railway.app/health/ready
```

**Ожидаемый ответ:**
```json
{
  "status": "ready",
  "timestamp": "2024-02-04T12:00:00.000000",
  "checks": {
    "database": "connected"
  }
}
```

### 5.3 Scheduler Status
```bash
curl https://govsniper-production.up.railway.app/scheduler/status
```

### 5.4 Просмотр логов
```bash
railway logs --tail
```

---

## 🔔 Шаг 6: Настройка YooKassa Webhook

### 6.1 Регистрация webhook URL

1. Зайдите в личный кабинет [YooKassa](https://yookassa.ru)
2. Выберите ваш магазин
3. Настройки → **Уведомления (HTTP notifications)**
4. Добавьте URL:
   ```
   https://govsniper-production.up.railway.app/webhooks/yookassa
   ```
5. Выберите события:
   - ✅ `payment.succeeded` - Успешная оплата
   - ✅ `payment.canceled` - Отмена оплаты
   - ✅ `refund.succeeded` - Успешный возврат (опционально)

6. Сохраните

### 6.2 Проверка webhook

Railway автоматически запишет все входящие запросы в логи:
```bash
railway logs | grep -i "yookassa"
```

---

## 🎉 Шаг 7: Тестирование

### 7.1 Создание тестового клиента
```bash
curl -X POST https://govsniper-production.up.railway.app/admin/clients \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "keywords": ["строительство", "дороги"],
    "min_price": 500000
  }'
```

### 7.2 Проверка статистики
```bash
curl https://govsniper-production.up.railway.app/admin/stats?days=7
```

### 7.3 Дождитесь парсинга
Первый парсинг произойдет через 15 минут (настраивается в `SCRAPER_INTERVAL_MINUTES`)

### 7.4 Проверьте логи
```bash
railway logs | grep -i "scraper"
railway logs | grep -i "tender"
```

---

## 🔧 Дополнительные настройки

### Кастомный домен

1. Railway Settings → **Domains**
2. Нажмите **"Custom Domain"**
3. Введите ваш домен: `api.govsniper.ru`
4. Добавьте CNAME запись у вашего DNS провайдера:
   ```
   CNAME api pointing to your-app.up.railway.app
   ```
5. Обновите `APP_BASE_URL`:
   ```env
   APP_BASE_URL=https://api.govsniper.ru
   ```
6. Обновите webhook URL в YooKassa

### Автоматический редеплой

Railway автоматически редеплоит при каждом push в `main`:
```bash
git add .
git commit -m "Update feature"
git push
```

### Просмотр метрик

Railway Dashboard → **Metrics**:
- CPU usage
- Memory usage
- Network traffic
- Deployment history

---

## 🆘 Troubleshooting

### ❌ Build Failed

**Проблема:** Ошибка при сборке Docker образа

**Решение:**
```bash
# Проверьте локальную сборку
docker build -t govsniper .

# Посмотрите логи Railway
railway logs --deployment
```

### ❌ Database Connection Error

**Проблема:** Приложение не может подключиться к БД

**Решение:**
1. Проверьте `DATABASE_URL` в Railway Variables
2. Убедитесь, что используете порт `6543` (не `5432`)
3. Проверьте, что в Supabase БД запущена:
   ```bash
   curl https://your-app.up.railway.app/health/ready
   ```

### ❌ Migrations Not Applied

**Проблема:** Таблицы не созданы в БД

**Решение:**
```bash
railway run alembic upgrade head
```

### ❌ Webhook не работает

**Проблема:** YooKassa не может отправить webhook

**Решение:**
1. Проверьте URL в YooKassa Dashboard
2. Проверьте логи Railway:
   ```bash
   railway logs | grep -i "webhook"
   ```
3. Используйте тестовый endpoint для отладки:
   ```bash
   curl -X POST https://your-app.up.railway.app/webhooks/yookassa/test \
     -H "Content-Type: application/json" \
     -d '{...}'
   ```

### ❌ Парсинг не работает

**Проблема:** Тендеры не парсятся с zakupki.gov.ru

**Решение:**
1. Убедитесь, что `PROXY_URL` настроен (обязательно для Railway!)
2. Проверьте логи scraper:
   ```bash
   railway logs | grep -i "scraper"
   ```
3. Протестируйте proxy вручную:
   ```bash
   railway run python -c "import httpx; print(httpx.get('https://zakupki.gov.ru', proxies={'https://': 'http://user:pass@ip:port'}))"
   ```

---

## 📊 Мониторинг Production

### Логи в реальном времени
```bash
railway logs --tail
```

### Проверка здоровья каждые 5 минут
```bash
watch -n 300 'curl -s https://your-app.up.railway.app/health/ready | jq'
```

### Статистика
```bash
curl https://your-app.up.railway.app/admin/stats?days=30 | jq
```

---

## 🎯 Чеклист после деплоя

- [ ] Health check работает
- [ ] Database подключена
- [ ] Scheduler запущен
- [ ] Webhook YooKassa зарегистрирован
- [ ] Создан тестовый клиент
- [ ] Парсинг тендеров работает
- [ ] Email отправка работает
- [ ] Логи чистые (без ошибок)

---

## 🚀 Готово!

Ваше приложение GovSniper успешно задеплоено на Railway! 🎉

**Полезные ссылки:**
- Railway Dashboard: https://railway.app/dashboard
- Логи: `railway logs`
- Документация: [README.md](README.md)
- API примеры: [API_EXAMPLES.md](API_EXAMPLES.md)
