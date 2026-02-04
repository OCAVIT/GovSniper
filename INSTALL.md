# 🔧 Installation Guide - GovSniper

Пошаговая инструкция по установке зависимостей и решению возможных проблем.

---

## ✅ Требования

- **Python 3.11+** (рекомендуется 3.11 или 3.12)
- **pip** последней версии
- **Git** (для клонирования репозитория)

---

## 📦 Установка зависимостей

### Шаг 1: Обновите pip

```bash
python -m pip install --upgrade pip
```

### Шаг 2: Установите зависимости

```bash
pip install -r requirements.txt
```

### Возможные проблемы и решения

#### ❌ Проблема: Конфликт зависимостей pytest

**Ошибка:**
```
ERROR: Cannot install pytest==8.0.0 and pytest-asyncio because these package versions have conflicting dependencies.
```

**Решение:**
Файл `requirements.txt` уже исправлен. Если проблема осталась:

```bash
# Удалите старые зависимости
pip uninstall pytest pytest-asyncio -y

# Установите заново
pip install pytest==7.4.4 pytest-asyncio==0.23.5
```

#### ❌ Проблема: WeasyPrint не устанавливается (Windows)

**Ошибка:**
```
error: Microsoft Visual C++ 14.0 or greater is required
```

**Решение для Windows:**

1. **Установите GTK3 Runtime:**
   - Скачайте: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
   - Установите GTK3-Runtime Win64

2. **Установите WeasyPrint:**
   ```bash
   pip install weasyprint
   ```

**Альтернатива (если не помогло):**
```bash
# Используйте pre-compiled wheels
pip install --only-binary :all: weasyprint
```

#### ❌ Проблема: python-magic не устанавливается (Windows)

**Ошибка:**
```
failed to find libmagic
```

**Решение для Windows:**
```bash
# Установите python-magic-bin вместо python-magic
pip uninstall python-magic -y
pip install python-magic-bin==0.4.14
```

Или обновите `requirements.txt`:
```diff
# Document Processing
python-docx==1.1.0
PyPDF2==3.0.1
- python-magic==0.4.27
+ python-magic-bin==0.4.14  # For Windows
```

#### ❌ Проблема: lxml не устанавливается

**Ошибка:**
```
error: command 'gcc' failed
```

**Решение:**
```bash
# Установите pre-compiled wheel
pip install --only-binary lxml lxml
```

---

## 🐍 Создание виртуального окружения (рекомендуется)

### Windows

```bash
# Создайте виртуальное окружение
python -m venv venv

# Активируйте
venv\Scripts\activate

# Обновите pip
python -m pip install --upgrade pip

# Установите зависимости
pip install -r requirements.txt
```

### Linux/Mac

```bash
# Создайте виртуальное окружение
python3 -m venv venv

# Активируйте
source venv/bin/activate

# Обновите pip
python -m pip install --upgrade pip

# Установите зависимости
pip install -r requirements.txt
```

---

## 🗄️ Настройка базы данных

### Вариант 1: Supabase (рекомендуется для production)

1. Зарегистрируйтесь на [supabase.com](https://supabase.com)
2. Создайте новый проект
3. Скопируйте CONNECTION STRING (URI) из Settings → Database
4. **Важно:** Используйте порт `6543` (Transaction pooler), не `5432`

**Пример DATABASE_URL:**
```env
DATABASE_URL=postgresql+asyncpg://postgres.xxx:password@aws-1-eu-central-1.pooler.supabase.com:6543/postgres
```

### Вариант 2: Локальный PostgreSQL (для разработки)

1. Установите PostgreSQL 15+
2. Создайте базу данных:
   ```sql
   CREATE DATABASE govsniper;
   ```
3. Обновите `.env`:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/govsniper
   ```

---

## 🔧 Применение миграций

После настройки базы данных:

```bash
# Проверьте, что alembic установлен
alembic --version

# Примените миграции
alembic upgrade head
```

### Возможные проблемы

#### ❌ "alembic" не является внутренней командой

**Решение:**
```bash
# Убедитесь, что зависимости установлены
pip install alembic

# Или запускайте через python
python -m alembic upgrade head
```

#### ❌ Ошибка подключения к БД

**Решение:**
```bash
# Проверьте DATABASE_URL в .env
# Проверьте, что PostgreSQL запущен
# Проверьте доступность порта

# Тест подключения:
python -c "from sqlalchemy import create_engine; engine = create_engine('your-database-url'); print('Connected!')"
```

---

## ⚙️ Настройка переменных окружения

### 1. Создайте .env файл

```bash
cp .env.example .env
```

### 2. Минимальные настройки для локального запуска

```env
# Database
DATABASE_URL=postgresql+asyncpg://localhost/govsniper

# OpenAI (обязательно для AI анализа)
OPENAI_API_KEY=sk-proj-your-key

# Application
APP_BASE_URL=http://localhost:8080
APP_ENV=development
LOG_LEVEL=DEBUG

# Остальные можно оставить по умолчанию для тестирования
```

### 3. Опциональные настройки для полного функционала

```env
# YooKassa (для платежей)
YOOKASSA_SHOP_ID=your-shop-id
YOOKASSA_SECRET_KEY=your-secret-key

# Resend (для email)
RESEND_API_KEY=re_your-key
EMAIL_FROM=test@example.com

# Proxy (для zakupki.gov.ru за границей)
PROXY_URL=http://user:pass@ip:port
```

---

## 🚀 Запуск приложения

### Вариант 1: Через Python (рекомендуется для разработки)

```bash
# С hot-reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
```

### Вариант 2: Напрямую

```bash
python -m src.main
```

### Вариант 3: Через Docker

```bash
# Сборка
docker build -t govsniper .

# Запуск
docker run -p 8080:8080 --env-file .env govsniper
```

### Вариант 4: Docker Compose

```bash
docker-compose up --build
```

---

## ✅ Проверка установки

### 1. Проверьте health endpoint

```bash
curl http://localhost:8080/health
```

**Ожидаемый ответ:**
```json
{
  "status": "healthy",
  "timestamp": "2024-02-04T12:00:00.000000",
  "service": "govsniper"
}
```

### 2. Проверьте подключение к БД

```bash
curl http://localhost:8080/health/ready
```

**Ожидаемый ответ:**
```json
{
  "status": "ready",
  "checks": {
    "database": "connected"
  }
}
```

### 3. Откройте Swagger UI

Перейдите в браузере: [http://localhost:8080/docs](http://localhost:8080/docs)

### 4. Проверьте scheduler

```bash
curl http://localhost:8080/scheduler/status
```

---

## 🧪 Запуск тестов

```bash
# Установите тестовые зависимости (уже в requirements.txt)
pip install pytest pytest-asyncio

# Запустите тесты
pytest tests/ -v

# С покрытием кода
pytest tests/ --cov=src --cov-report=html

# Откройте отчет
# htmlcov/index.html
```

---

## 🔍 Проверка установленных пакетов

```bash
# Список всех установленных пакетов
pip list

# Проверка конкретных пакетов
pip show fastapi uvicorn sqlalchemy alembic

# Проверка зависимостей
pip check
```

---

## 🐛 Общие проблемы

### ModuleNotFoundError

**Проблема:**
```
ModuleNotFoundError: No module named 'apscheduler'
```

**Решение:**
```bash
# Переустановите зависимости
pip install -r requirements.txt --force-reinstall

# Или установите конкретный пакет
pip install apscheduler
```

### ImportError в Windows

**Проблема:**
```
ImportError: DLL load failed while importing _sqlite3
```

**Решение:**
Переустановите Python с официального сайта python.org с опцией "Add Python to PATH"

### Ошибки кодировки (Windows)

**Проблема:**
```
UnicodeDecodeError: 'charmap' codec can't decode
```

**Решение:**
Установите переменную окружения:
```bash
set PYTHONIOENCODING=utf-8
```

Или добавьте в начало скрипта:
```python
import sys
sys.stdout.reconfigure(encoding='utf-8')
```

---

## 📚 Дополнительные ресурсы

- [README.md](README.md) - Основная документация
- [QUICKSTART.md](QUICKSTART.md) - Быстрый старт
- [API_EXAMPLES.md](API_EXAMPLES.md) - Примеры API
- [RAILWAY_DEPLOY.md](RAILWAY_DEPLOY.md) - Деплой на Railway

---

## 🆘 Нужна помощь?

Если проблема не решилась:

1. Проверьте версию Python:
   ```bash
   python --version
   ```
   Должно быть 3.11+

2. Проверьте, активно ли виртуальное окружение:
   ```bash
   which python  # Linux/Mac
   where python  # Windows
   ```

3. Очистите кеш pip:
   ```bash
   pip cache purge
   ```

4. Переустановите с нуля:
   ```bash
   pip uninstall -r requirements.txt -y
   pip install -r requirements.txt
   ```
