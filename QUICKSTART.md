# 🚀 Quick Start - GovSniper

Быстрый старт для локальной разработки и тестирования.

---

## ⚡ За 5 минут

### 1. Установка
```bash
pip install -r requirements.txt
```

### 2. Настройка .env
```bash
cp .env.example .env
```

Минимальные настройки для локального запуска:
```env
DATABASE_URL=postgresql+asyncpg://postgres.xxx:password@aws-1-eu-central-1.pooler.supabase.com:6543/postgres
OPENAI_API_KEY=sk-proj-your-key
APP_BASE_URL=http://localhost:8080
APP_ENV=development
```

### 3. Миграции
```bash
alembic upgrade head
```

### 4. Запуск
```bash
python -m src.main
```

### 5. Тест
Откройте: [http://localhost:8080/docs](http://localhost:8080/docs)

---

## 🧪 Первый тест

### Создайте клиента
```bash
curl -X POST http://localhost:8080/admin/clients \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "keywords": ["строительство", "дороги"],
    "min_price": 500000
  }'
```

### Проверьте статистику
```bash
curl http://localhost:8080/admin/stats?days=7
```

### Симулируйте платёж
```bash
curl -X POST http://localhost:8080/webhooks/yookassa/test \
  -H "Content-Type: application/json" \
  -d '{
    "type": "notification",
    "event": "payment.succeeded",
    "object": {
      "id": "test-123",
      "status": "succeeded",
      "metadata": {
        "tender_id": "1",
        "client_id": "1",
        "client_email": "test@example.com"
      }
    }
  }'
```

---

## 📦 Деплой на Railway

### Шаг 1: Подготовка
```bash
# Инициализация Git
git init
git add .
git commit -m "Initial commit"

# Создание репозитория на GitHub
gh repo create GovSniper --private --source=. --push
```

### Шаг 2: Railway
1. Зайдите на [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Выберите репозиторий `GovSniper`

### Шаг 3: Переменные окружения
Добавьте в Railway → Variables:
```env
DATABASE_URL=postgresql+asyncpg://...
OPENAI_API_KEY=sk-proj-...
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
RESEND_API_KEY=re_...
EMAIL_FROM=noreply@yourdomain.com
APP_ENV=production
PROXY_URL=http://user:pass@ip:port
```

### Шаг 4: Получите домен
После деплоя Railway даст домен:
```
https://govsniper-production.up.railway.app
```

### Шаг 5: Обновите APP_BASE_URL
В Railway → Variables:
```env
APP_BASE_URL=https://govsniper-production.up.railway.app
```

### Шаг 6: Webhook YooKassa
Зарегистрируйте в YooKassa Dashboard:
```
https://govsniper-production.up.railway.app/webhooks/yookassa
```

---

## ✅ Проверка деплоя

```bash
# Health check
curl https://your-app.up.railway.app/health

# Создать клиента
curl -X POST https://your-app.up.railway.app/admin/clients \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "keywords": ["строительство"]}'

# Логи
railway logs
```

---

## 🎯 Основные эндпоинты

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI (dev) |
| `/admin/clients` | GET/POST | Управление клиентами |
| `/admin/tenders` | GET | Просмотр тендеров |
| `/admin/stats` | GET | Статистика |
| `/webhooks/yookassa` | POST | YooKassa webhook |
| `/scheduler/status` | GET | Статус задач |

---

## 📚 Дополнительная документация

- [README.md](README.md) - Полная документация
- [API_EXAMPLES.md](API_EXAMPLES.md) - Примеры API запросов

---

## 🆘 Помощь

**Проблемы с БД?**
```bash
curl http://localhost:8080/health/ready
```

**Не работает парсинг?**
Добавьте `PROXY_URL` в `.env`

**Не приходят email?**
Проверьте `RESEND_API_KEY` и логи

**Логи Railway:**
```bash
railway logs
```
