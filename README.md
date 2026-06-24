# 🤖 Бог БО Синн — Telegram бот с LLM

Грубый, токсичный, но смешной ИИ-ассистент для групповых чатов Telegram. Отвечает матом, оскорбляет, троллит, но не переходит черту.

## Возможности

- **Ответы на @упоминания** и фразу "Бо Синн"
- **Ответы на reply** к сообщениям бота
- **Реакции на эмодзи** — оскорбляет за поставленную реакцию (требуются права админа)
- **Комментирование пересланных сообщений** — грубо и смешно
- **Контекст чата** — помнит последние 50 сообщений
- **Rate-limit** — не спамит (1 ответ в 10 секунд)
- **Персональные подколы** для указанных пользователей (включается для конкретного чата)
- **Вежливый режим** для `@psyhO_Delic` — комплименты и ласка вместо мата
- **Защита от промпт-инъекций**
- **Proxy/SOCKS5** для обхода блокировок Telegram

## Быстрый старт

### 1. Создай бота в @BotFather

- `/newbot` → имя → username (запомни токен и username)

### 2. ОТКЛЮЧИ PRIVACY MODE (обязательно!)

В @BotFather: `/setprivacy` → выбери бота → **Disable**
> Иначе бот не будет видеть сообщения без @упоминания.

### 3. Настройка

```bash
# Скопируй .env.example в .env
cp .env.example .env

# Отредактируй .env под себя
```

Переменные в `.env`:

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен от BotFather |
| `LLM_API_KEY` | Ключ OpenAI-совместимого API |
| `LLM_BASE_URL` | URL API (по умолч. `https://api.openai.com/v1`) |
| `LLM_MODEL` | Модель (например `gpt-4o-mini`) |
| `BOT_USERNAME` | Username бота **без @** |
| `BOT_PROXY` | SOCKS5 прокси (опционально, для РФ) |
| `TAUNT_CHAT_ID` | ID чата для персональных подколов (опционально) |

### 4. Запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск
python bot.py
```

### 5. Или через Docker

```bash
docker compose up -d --build
```

### 6. Добавь бота в группу

Ссылка: `https://t.me/<BOT_USERNAME>?startgroup=true`

### 7. Реакции на эмодзи (опционально)

Сделай бота **администратором группы** с правами минимум "Отправка сообщений" и "Чтение сообщений".

## Тестирование

```bash
python -m pytest tests/ -v
```

## Бесплатные API для LLM

| Сервис | URL | Модель |
|---|---|---|
| **Groq** | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| **OpenRouter** | `https://openrouter.ai/api/v1` | `google/gemini-2.0-flash-exp` |
| **DeepSeek** | `https://api.deepseek.com/v1` | `deepseek-chat` |

## Команды

- `/start` — бот пошлёт вас
- `/say <текст>` — написать сообщение от лица бота

## Структура

```
├── bot.py              # Основной код бота
├── Dockerfile          # Docker-образ
├── docker-compose.yml  # Docker Compose
├── requirements.txt    # Зависимости
├── .env.example        # Пример настроек
├── .gitignore
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_bot.py     # 61 тест
```
