# API Examples - GovSniper

Примеры запросов к API для тестирования функционала.

---

## 🏥 Health Checks

### Базовая проверка
```bash
curl http://localhost:8080/health
```

### Проверка готовности (с БД)
```bash
curl http://localhost:8080/health/ready
```

### Проверка работоспособности
```bash
curl http://localhost:8080/health/live
```

---

## 👥 Управление клиентами

### Создать клиента
```bash
curl -X POST http://localhost:8080/admin/clients \
  -H "Content-Type: application/json" \
  -d '{
    "email": "ivanov@example.com",
    "name": "Иван Иванов",
    "company": "ООО Строитель",
    "phone": "+79991234567",
    "keywords": ["строительство", "ремонт дорог", "благоустройство"],
    "min_price": 500000,
    "max_price": 10000000
  }'
```

### Получить список клиентов
```bash
# Все клиенты
curl http://localhost:8080/admin/clients

# С пагинацией
curl "http://localhost:8080/admin/clients?skip=0&limit=10"

# Только активные
curl "http://localhost:8080/admin/clients?active_only=true"
```

### Получить клиента по ID
```bash
curl http://localhost:8080/admin/clients/1
```

### Обновить клиента
```bash
curl -X PATCH http://localhost:8080/admin/clients/1 \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["строительство", "дороги", "мосты"],
    "is_active": true,
    "min_price": 1000000
  }'
```

### Удалить клиента
```bash
curl -X DELETE http://localhost:8080/admin/clients/1
```

---

## 📊 Тендеры

### Получить список тендеров
```bash
# Все тендеры
curl http://localhost:8080/admin/tenders

# С фильтром по статусу
curl "http://localhost:8080/admin/tenders?status=pending"

# Доступные статусы: pending, analyzed, notified, sold
```

### Получить тендер по ID
```bash
curl http://localhost:8080/admin/tenders/1
```

---

## 📈 Статистика

### Общая статистика за 30 дней
```bash
curl "http://localhost:8080/admin/stats?days=30"
```

**Ответ:**
```json
{
  "total_tenders": 150,
  "tenders_by_status": {
    "pending": 20,
    "analyzed": 50,
    "notified": 60,
    "sold": 20
  },
  "total_clients": 25,
  "active_clients": 20,
  "total_revenue": 19800.0,
  "successful_payments": 20,
  "notifications_sent": 120,
  "period_days": 30
}
```

### Ежедневная статистика за 7 дней
```bash
curl "http://localhost:8080/admin/stats/daily?days=7"
```

**Ответ:**
```json
{
  "daily_stats": [
    {
      "date": "2024-02-04",
      "tenders": 12,
      "payments": 2,
      "revenue": 1980.0
    },
    {
      "date": "2024-02-03",
      "tenders": 8,
      "payments": 1,
      "revenue": 990.0
    }
  ]
}
```

---

## 💳 Webhook YooKassa (тестовый)

### Симуляция успешного платежа
```bash
curl -X POST http://localhost:8080/webhooks/yookassa/test \
  -H "Content-Type: application/json" \
  -d '{
    "type": "notification",
    "event": "payment.succeeded",
    "object": {
      "id": "test-payment-123",
      "status": "succeeded",
      "amount": {
        "value": "990.00",
        "currency": "RUB"
      },
      "metadata": {
        "tender_id": "1",
        "client_id": "1",
        "client_email": "test@example.com"
      }
    }
  }'
```

**Что произойдет:**
1. ✅ Статус платежа обновится на `succeeded`
2. 🤖 Запустится глубокий AI-анализ тендера
3. 📄 Сгенерируется PDF отчёт
4. 📧 Отправится email с PDF клиенту
5. 🧹 Очистятся временные данные тендера

### Симуляция отмены платежа
```bash
curl -X POST http://localhost:8080/webhooks/yookassa/test \
  -H "Content-Type: application/json" \
  -d '{
    "type": "notification",
    "event": "payment.canceled",
    "object": {
      "id": "test-payment-456",
      "status": "canceled"
    }
  }'
```

---

## 🔄 Scheduler (статус задач)

### Проверить статус планировщика
```bash
curl http://localhost:8080/scheduler/status
```

**Ответ:**
```json
{
  "jobs": [
    {
      "id": "scrape_rss",
      "name": "Scrape RSS Feed",
      "next_run": "2024-02-04T15:30:00",
      "trigger": "interval[0:15:00]"
    },
    {
      "id": "analyze_tenders",
      "name": "Analyze Tenders",
      "next_run": "2024-02-04T15:25:00",
      "trigger": "interval[0:05:00]"
    },
    {
      "id": "send_notifications",
      "name": "Send Notifications",
      "next_run": "2024-02-04T15:35:00",
      "trigger": "interval[0:10:00]"
    }
  ],
  "running": true
}
```

---

## 🧪 Python примеры (httpx)

### Установка
```bash
pip install httpx
```

### Создание клиента
```python
import httpx
import asyncio

async def create_client():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8080/admin/clients",
            json={
                "email": "test@example.com",
                "name": "Test User",
                "keywords": ["строительство", "дороги"],
                "min_price": 500000,
                "max_price": 5000000
            }
        )
        print(response.json())

asyncio.run(create_client())
```

### Получение статистики
```python
import httpx
import asyncio

async def get_stats():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8080/admin/stats",
            params={"days": 30}
        )
        stats = response.json()

        print(f"Всего тендеров: {stats['total_tenders']}")
        print(f"Активных клиентов: {stats['active_clients']}")
        print(f"Выручка: {stats['total_revenue']} ₽")

asyncio.run(get_stats())
```

---

## 📝 Полезные команды

### Просмотр логов (Railway)
```bash
railway logs
```

### Подключение к БД (Supabase)
```bash
psql "postgresql://postgres.xxx:password@aws-1-eu-central-1.pooler.supabase.com:6543/postgres"
```

### Применение миграций
```bash
alembic upgrade head
```

### Создание новой миграции
```bash
alembic revision --autogenerate -m "Add new field"
```

---

## 🚀 Быстрый старт для новых клиентов

1. **Создайте клиента через API**
2. **Дождитесь парсинга тендеров** (каждые 15 минут)
3. **Проверьте уведомления** в логах или БД
4. **Протестируйте платёж** через test webhook
5. **Проверьте email** с PDF отчётом

---

## 🐛 Troubleshooting

### Проблема: База данных недоступна
```bash
# Проверьте подключение
curl http://localhost:8080/health/ready

# Проверьте DATABASE_URL в .env
echo $DATABASE_URL
```

### Проблема: Не приходят email
```bash
# Проверьте RESEND_API_KEY
# Проверьте логи
railway logs | grep -i "email"
```

### Проблема: Не работает парсинг zakupki.gov.ru
```bash
# За границей обязателен PROXY_URL
# Проверьте логи scraper
railway logs | grep -i "scraper"
```
