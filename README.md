# GovSniper

**Government Procurement Analytics Platform** - автоматический парсинг, анализ и монетизация тендеров с zakupki.gov.ru.

## 🎯 Возможности

- **Автоматический парсинг** тендеров из RSS zakupki.gov.ru
- **AI-анализ** рисков и маржинальности тендеров (OpenAI GPT-4)
- **Персональные уведомления** клиентам по ключевым словам
- **Монетизация** через платные детальные отчёты (YooKassa)
- **Email рассылка** с PDF отчётами (Resend)
- **Админ панель** для управления клиентами и статистикой

---

## 📋 Требования

- Python 3.11+
- PostgreSQL (Supabase)
- API ключи:
  - OpenAI (GPT-4)
  - YooKassa (платежи)
  - Resend (email)
  - Proxy для zakupki.gov.ru (при деплое за границей)

---

## 🚀 Локальный запуск

### 1. Клонирование и установка зависимостей

```bash
# Установите зависимости
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Заполните `.env` реальными данными:

```env
# Database (получите из Supabase Dashboard)
DATABASE_URL=postgresql+asyncpg://postgres.xxx:password@aws-1-eu-central-1.pooler.supabase.com:6543/postgres

# OpenAI
OPENAI_API_KEY=sk-proj-...

# YooKassa
YOOKASSA_SHOP_ID=your-shop-id
YOOKASSA_SECRET_KEY=your-secret-key

# Resend Email
RESEND_API_KEY=re_...
EMAIL_FROM=noreply@yourdomain.com

# Application
APP_BASE_URL=http://localhost:8080
APP_ENV=development

# Proxy (если запускаете за границей)
PROXY_URL=http://user:pass@ip:port
```

### 3. Инициализация базы данных

```bash
# Применить миграции
alembic upgrade head
```

### 4. Запуск приложения

**Вариант A: Напрямую через Python**
```bash
python -m src.main
```

**Вариант B: Через uvicorn с hot-reload**
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
```

**Вариант C: Через Docker Compose**
```bash
docker-compose up --build
```

Приложение будет доступно на `http://localhost:8080`

---

## 🔧 Тестирование Админ панели

### Swagger UI (рекомендуется)

Откройте в браузере: [http://localhost:8080/docs](http://localhost:8080/docs)

Доступные эндпоинты:

#### **Управление клиентами**
- `POST /admin/clients` - Создать клиента
- `GET /admin/clients` - Список клиентов
- `GET /admin/clients/{id}` - Получить клиента
- `PATCH /admin/clients/{id}` - Обновить клиента
- `DELETE /admin/clients/{id}` - Удалить клиента

#### **Просмотр тендеров**
- `GET /admin/tenders` - Список тендеров
- `GET /admin/tenders/{id}` - Получить тендер

#### **Статистика**
- `GET /admin/stats?days=30` - Общая статистика
- `GET /admin/stats/daily?days=7` - Ежедневная статистика

### Пример: Создание тестового клиента

**Через Swagger UI:**
1. Откройте `/docs`
2. Найдите `POST /admin/clients`
3. Нажмите "Try it out"
4. Вставьте JSON:

```json
{
  "email": "test@example.com",
  "name": "Иван Петров",
  "company": "ООО Тест",
  "phone": "+79991234567",
  "keywords": ["строительство", "ремонт дорог", "благоустройство"],
  "min_price": 500000,
  "max_price": 10000000
}
```

**Через curl:**
```bash
curl -X POST http://localhost:8080/admin/clients \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "keywords": ["строительство", "дороги"],
    "min_price": 500000
  }'
```

### Тестирование webhook YooKassa

```bash
curl -X POST http://localhost:8080/webhooks/yookassa/test \
  -H "Content-Type: application/json" \
  -d '{
    "type": "notification",
    "event": "payment.succeeded",
    "object": {
      "id": "test-payment-123",
      "status": "succeeded",
      "amount": {"value": "990.00", "currency": "RUB"},
      "metadata": {
        "tender_id": "1",
        "client_id": "1",
        "client_email": "test@example.com"
      }
    }
  }'
```

---

## 📦 Выгрузка на Git

### 1. Инициализация репозитория

```bash
cd e:\VibeProjects\GovSniper
git init
git add .
git commit -m "Initial commit: GovSniper v1.0"
```

### 2. Создание репозитория на GitHub

**Через GitHub CLI:**
```bash
gh repo create GovSniper --private --source=. --remote=origin --push
```

**Или вручную:**
1. Создайте репозиторий на GitHub.com
2. Подключите remote:
```bash
git remote add origin https://github.com/yourusername/GovSniper.git
git branch -M main
git push -u origin main
```

---

## 🚂 Деплой на Railway

### Вариант 1: Деплой через GitHub (рекомендуется)

1. **Залогиньтесь в Railway**
   - Перейдите на [railway.app](https://railway.app)
   - Войдите через GitHub

2. **Создайте новый проект**
   - New Project → Deploy from GitHub repo
   - Выберите репозиторий `GovSniper`

3. **Настройте переменные окружения**

   В Railway Dashboard → Variables добавьте:

   ```env
   DATABASE_URL=postgresql+asyncpg://...
   OPENAI_API_KEY=sk-proj-...
   YOOKASSA_SHOP_ID=...
   YOOKASSA_SECRET_KEY=...
   RESEND_API_KEY=re_...
   EMAIL_FROM=noreply@yourdomain.com
   APP_ENV=production
   LOG_LEVEL=INFO
   REPORT_PRICE=990
   PROXY_URL=http://user:pass@ip:port
   PORT=8080
   ```

4. **Настройте APP_BASE_URL**

   После первого деплоя Railway предоставит домен типа:
   ```
   govsniper-production.up.railway.app
   ```

   Добавьте переменную:
   ```env
   APP_BASE_URL=https://govsniper-production.up.railway.app
   ```

5. **Зарегистрируйте webhook в YooKassa**

   В личном кабинете YooKassa → Настройки → Уведомления:
   ```
   https://govsniper-production.up.railway.app/webhooks/yookassa
   ```

   События: `payment.succeeded`, `payment.canceled`

6. **Railway автоматически:**
   - Обнаружит `Dockerfile`
   - Соберёт образ
   - Запустит приложение
   - Настроит HTTPS

### Вариант 2: Деплой через Railway CLI

```bash
# Установите Railway CLI
npm i -g @railway/cli

# Залогиньтесь
railway login

# Инициализируйте проект
railway init

# Добавьте переменные окружения
railway variables set DATABASE_URL="postgresql+asyncpg://..."
railway variables set OPENAI_API_KEY="sk-proj-..."
# ... остальные переменные

# Задеплойте
railway up
```

### Проверка деплоя

1. **Откройте логи:**
   ```bash
   railway logs
   ```

2. **Проверьте health endpoint:**
   ```bash
   curl https://your-app.up.railway.app/health
   ```

3. **Откройте Swagger:**
   ```
   https://your-app.up.railway.app/docs
   ```
   (в production отключен, удалите условие в `src/main.py:121`)

---

## 📊 Архитектура

```
src/
├── api/              # FastAPI endpoints
│   ├── admin.py     # Админ панель (клиенты, тендеры, статистика)
│   ├── webhooks.py  # YooKassa webhook
│   └── health.py    # Health check
├── models/          # SQLAlchemy модели
├── services/        # Бизнес-логика
│   ├── scraper_service.py    # Парсинг RSS
│   ├── ai_service.py         # OpenAI анализ
│   ├── payment_service.py    # YooKassa платежи
│   ├── email_service.py      # Resend email
│   └── pdf_generator.py      # WeasyPrint PDF
├── scheduler/       # APScheduler задачи
└── main.py          # Точка входа
```

### Workflow

1. **Scheduler** каждые 15 минут парсит RSS
2. **AI анализирует** тендеры (риск, маржа)
3. **Matcher** подбирает релевантные тендеры клиентам
4. **Notification Service** отправляет краткие уведомления
5. **Клиент платит** за детальный отчёт (YooKassa)
6. **Webhook** получает уведомление об оплате
7. **Deep Analysis** генерирует полный AI-аудит
8. **PDF Generator** создаёт красивый отчёт
9. **Email Service** отправляет PDF клиенту

---

## 🔒 Безопасность

- **Webhook** проверяет IP YooKassa в production
- **Database** использует connection pooling (port 6543)
- **Docker** запускается от non-root пользователя
- **Secrets** хранятся в переменных окружения
- **CORS** настроен только для production домена

---

## 🧪 Тестирование

```bash
# Запустите тесты
pytest tests/ -v

# С покрытием кода
pytest tests/ --cov=src --cov-report=html
```

---

## 📝 TODO

- [ ] Добавить authentication для админ панели (FastAPI OAuth2)
- [ ] Реализовать rate limiting для API
- [ ] Добавить Redis для кеширования
- [ ] Телеграм бот для уведомлений
- [ ] Мониторинг (Sentry, DataDog)
- [ ] CI/CD (GitHub Actions)

---

## 📄 Лицензия

Proprietary - All rights reserved

---

## 👤 Контакты

Вопросы и поддержка: info@govsniper.ru
