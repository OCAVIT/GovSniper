# GovSniper

**Government Procurement Analytics Platform** — автоматический парсинг, AI-анализ и монетизация тендеров с zakupki.gov.ru.

## Возможности

- **Автоматический парсинг** тендеров из RSS zakupki.gov.ru (44-ФЗ)
- **AI-анализ** рисков и маржинальности (OpenAI GPT-4o-mini)
- **Персональные уведомления** клиентам по ключевым словам
- **Платные детальные отчёты** с глубоким AI-аудитом (YooKassa)
- **Lead Generation** — автоматическое создание клиентов из проигравших участников тендеров
- **Email рассылка** с PDF отчётами (Resend)
- **Админ панель** для управления клиентами и мониторинга

---

## Технологии

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, AsyncIO
- **Database:** PostgreSQL (Supabase)
- **AI:** OpenAI GPT-4o-mini (анализ тендеров)
- **Payments:** YooKassa (tiered pricing)
- **Email:** Resend + PDF генерация
- **Data Enrichment:** DaData API (контакты компаний по ИНН)
- **Scheduler:** APScheduler (фоновые задачи)
- **Deploy:** Docker, Railway

---

## Архитектура

```
src/
├── api/              # FastAPI endpoints
│   ├── admin.py      # Админ панель (клиенты, тендеры, статистика, leadgen)
│   ├── webhooks.py   # YooKassa webhook
│   └── health.py     # Health check
├── models/           # SQLAlchemy модели
│   ├── tender.py     # Тендеры
│   ├── client.py     # Клиенты
│   ├── participant.py # Участники тендеров (для leadgen)
│   └── payment.py    # Платежи
├── services/         # Бизнес-логика
│   ├── scraper_service.py    # Парсинг RSS zakupki.gov.ru
│   ├── document_service.py   # Загрузка документов тендеров
│   ├── ai_service.py         # OpenAI анализ (teaser + deep audit)
│   ├── losers_service.py     # Lead Generation из проигравших
│   ├── dadata_service.py     # DaData API (контакты по ИНН)
│   ├── payment_service.py    # YooKassa платежи
│   ├── email_service.py      # Resend email
│   └── pdf_generator.py      # PDF отчёты
├── scheduler/        # APScheduler задачи
│   ├── jobs.py       # Определение задач
│   └── job_stats.py  # Статистика выполнения
├── templates/        # Email шаблоны (Jinja2)
├── static/           # Frontend (Alpine.js + Tailwind)
└── main.py           # Точка входа
```

---

## Бизнес-логика

### Основной Workflow

1. **Scheduler** каждые 15 минут парсит RSS zakupki.gov.ru
2. **Document Service** скачивает документы тендеров
3. **AI Service** анализирует тендеры (риск-скор, маржа, краткое описание)
4. **Matcher** подбирает релевантные тендеры клиентам по keywords
5. **Notification Service** отправляет email-тизеры с кнопкой "Купить полный отчёт"
6. **Клиент оплачивает** через YooKassa (tiered pricing: 990/1990/4990 ₽)
7. **Webhook** получает уведомление об успешной оплате
8. **Deep Analysis** генерирует полный AI-аудит тендера
9. **PDF Generator** создаёт детальный отчёт
10. **Email Service** отправляет PDF клиенту

### Lead Generation (уникальная фича)

Автоматическое создание клиентов из проигравших участников тендеров:

1. **Extract Losers** — парсинг протоколов завершённых тендеров, извлечение проигравших (ИНН, название, сумма заявки)
2. **Fetch Contacts** — получение email/телефона компании через DaData API по ИНН
3. **Create Clients** — автоматическое создание клиентов с keywords из категории тендера

Проигравшие компании — идеальные клиенты: они активно участвуют в тендерах и заинтересованы в победе.

---

## API Endpoints

### Клиенты
- `POST /api/v1/admin/clients` — Создать клиента
- `GET /api/v1/admin/clients` — Список клиентов
- `PATCH /api/v1/admin/clients/{id}` — Обновить клиента
- `DELETE /api/v1/admin/clients/{id}` — Удалить клиента

### Тендеры
- `GET /api/v1/admin/tenders` — Список тендеров (с фильтрацией по статусу)
- `GET /api/v1/admin/tenders/{id}` — Детали тендера

### Статистика
- `GET /api/v1/admin/stats` — Общая статистика
- `GET /api/v1/admin/stats/daily` — Ежедневная статистика

### Lead Generation
- `GET /api/v1/admin/leadgen/stats` — Статистика лидгена
- `GET /api/v1/admin/leadgen/participants` — Список участников тендеров
- `GET /api/v1/admin/leadgen/auto-clients` — Авто-созданные клиенты
- `POST /api/v1/admin/leadgen/trigger/extract` — Запустить парсинг проигравших
- `POST /api/v1/admin/leadgen/trigger/fetch-contacts` — Запустить получение контактов
- `POST /api/v1/admin/leadgen/trigger/create-clients` — Запустить создание клиентов

### Scheduler
- `GET /api/v1/admin/scheduler/status` — Статус планировщика
- `POST /api/v1/admin/scheduler/pause` — Пауза
- `POST /api/v1/admin/scheduler/resume` — Возобновить

### Webhooks
- `POST /webhooks/yookassa` — Webhook для YooKassa

---

## Конфигурация

### Переменные окружения (.env)

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:6543/postgres

# OpenAI
OPENAI_API_KEY=sk-proj-...

# YooKassa
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...

# Email (Resend)
RESEND_API_KEY=re_...
EMAIL_FROM=noreply@yourdomain.com

# DaData (для Lead Generation)
DADATA_API_KEY=...

# Application
APP_BASE_URL=https://yourdomain.com
APP_ENV=production

# Pricing (tiered)
REPORT_PRICE_TIER1=990    # тендеры < 1M
REPORT_PRICE_TIER2=1990   # тендеры 1M-10M
REPORT_PRICE_TIER3=4990   # тендеры > 10M

# Lead Generation
LEADGEN_ENABLED=true
LEADGEN_INTERVAL_HOURS=6
LEADGEN_MIN_TENDER_AGE_DAYS=7
LEADGEN_MAX_TENDER_AGE_DAYS=30

# Proxy (если сервер за границей)
PROXY_URL=http://user:pass@ip:port
```

---

## Локальный запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Применение миграций
alembic upgrade head

# Запуск
python -m src.main
# или
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
```

Приложение доступно на `http://localhost:8080`

---

## Deploy (Railway)

1. Подключите GitHub репозиторий к Railway
2. Добавьте переменные окружения в Railway Dashboard
3. Railway автоматически соберёт Docker образ и запустит приложение
4. Зарегистрируйте webhook в YooKassa: `https://your-app.up.railway.app/webhooks/yookassa`

---

## Безопасность

- Webhook проверяет IP YooKassa в production
- Database использует connection pooling
- Docker запускается от non-root пользователя
- Secrets хранятся в переменных окружения

---

## Лицензия

MIT License
