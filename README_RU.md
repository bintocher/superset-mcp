# mcp-superset

[![PyPI version](https://img.shields.io/pypi/v/mcp-superset.svg)](https://pypi.org/project/mcp-superset/)
[![PyPI downloads](https://img.shields.io/pypi/dm/mcp-superset.svg)](https://pypi.org/project/mcp-superset/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/bintocher/mcp-superset/actions/workflows/ci.yml/badge.svg)](https://github.com/bintocher/mcp-superset/actions/workflows/ci.yml)
[![CodeQL](https://github.com/bintocher/mcp-superset/actions/workflows/codeql.yml/badge.svg)](https://github.com/bintocher/mcp-superset/actions/workflows/codeql.yml)

[![Superset 6.0.1](https://img.shields.io/badge/Superset-6.0.1-orange.svg)](https://superset.apache.org/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Typed](https://img.shields.io/badge/typed-py.typed-blue.svg)](https://peps.python.org/pep-0561/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Tools: 137](https://img.shields.io/badge/MCP_tools-128%2B-brightgreen.svg)](#available-tools-128)
[![GitHub stars](https://img.shields.io/github/stars/bintocher/mcp-superset.svg?style=social)](https://github.com/bintocher/mcp-superset)

[English](README.md) | **Русский**

Полнофункциональный [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) сервер для [Apache Superset](https://superset.apache.org/). Предоставляет AI-ассистентам (Claude, GPT и др.) полный контроль над инстансом Superset — дашборды, графики, датасеты, SQL Lab, пользователи, роли, RLS и многое другое — через 137 инструментов.

## Сравнение с другими MCP-серверами для Superset

| Возможность | **mcp-superset** | [superset-mcp](https://github.com/aptro/superset-mcp) | [superset-mcp (Winding2020)](https://github.com/Winding2020/superset-mcp) | [superset-mcp-server](https://github.com/LiusCraft/superset-mcp-server) |
|-------------|:-:|:-:|:-:|:-:|
| **Всего инструментов** | **137** | 60 | 31 | 4 |
| Язык | Python | Python | TypeScript | TypeScript |
| Дашборды CRUD | 15 | 5 | 8 | - |
| Нативные фильтры | **5** | - | - | - |
| Графики CRUD | 11 | 5 | 7 | - |
| Базы данных | 18 | 14 | 1 | 1 |
| Датасеты | 11 | 3 | 7 | - |
| SQL Lab | 5 | 7 | 1 | 1 |
| **Безопасность (пользователи/роли)** | **26** | 2 | - | - |
| **Row Level Security** | **5** | - | - | - |
| **Группы** | **9** | - | - | - |
| **Аудит прав** | **да** | - | - | - |
| **Grant/revoke доступа** | **да** | - | - | - |
| **Авто-синхр. datasource_access** | **да** | - | - | - |
| Отчёты и аннотации | 10 | - | - | - |
| Теги | 7 | 7 | - | - |
| Экспорт/импорт ассетов | да | - | - | - |
| **Защита: флаги подтверждения** | **14 типов** | - | - | - |
| **Защита: блокировка DDL/DML** | **да** | - | - | - |
| **Защита: системные роли** | **да** | - | - | - |
| Транспорт | HTTP, SSE, stdio | stdio | stdio | stdio |
| Аутентификация | JWT + авто-refresh + CSRF | Username/password + файл токена | Username/password или токен | LDAP |
| Версии Superset | 6.0.1 | 4.1.1 | не указано | не указано |
| CLI с параметрами | `--host --port --transport` | - | - | - |
| PyPI | `mcp-superset` | `superset-mcp` | `superset-mcp` (npm) | - |
| uvx | **да** | - | - | - |
| Лицензия | MIT | MIT | - | Apache 2.0 |

**Ключевые отличия:**
- Единственный MCP-сервер с **полным управлением безопасностью** (пользователи, роли, RLS, группы, аудит прав)
- Единственный с **встроенной защитой** (флаги подтверждения, блокировка DDL/DML)
- Единственный с **управлением нативными фильтрами дашбордов**
- Единственный с **автоматической синхронизацией datasource_access**
- Единственный с **несколькими транспортами** (HTTP, SSE, stdio)
- Единственный с **настраиваемым CLI** (`--host`, `--port`, `--transport`, `--env-file`)

## Возможности

- **137 MCP-инструментов**, покрывающих полный REST API Superset
- **Управление дашбордами** — CRUD, копирование, публикация, экспорт/импорт, встраивание, нативные фильтры
- **Управление графиками** — CRUD, копирование, получение данных, экспорт/импорт, прогрев кэша
- **Управление базами данных** — CRUD, проверка подключения, интроспекция схем/таблиц, валидация SQL
- **Управление датасетами** — CRUD, дублирование, обновление схемы, экспорт/импорт
- **SQL Lab** — выполнение запросов, форматирование, оценка стоимости, экспорт результатов
- **Безопасность** — пользователи, роли, права, Row Level Security (RLS), группы
- **Автоматизация доступа** — grant/revoke с автоматической синхронизацией datasource_access
- **Аудит** — матрица прав доступа (пользователь x дашборды x датасеты x RLS)
- **Теги, отчёты, аннотации, сохранённые запросы** — полный CRUD
- **Экспорт/импорт ассетов** — полный бэкап и восстановление инстанса
- **Встроенная защита** — подтверждения для деструктивных операций, блокировка DDL/DML в SQL Lab
- **JWT-аутентификация** с автоматическим обновлением токенов и CSRF
- **Транспорты**: Streamable HTTP, SSE, stdio

## Быстрый старт

### Установка

```bash
# Из PyPI
pip install mcp-superset

# Через uv (рекомендуется)
uv pip install mcp-superset

# Запуск без установки (uvx)
uvx mcp-superset
```

### Конфигурация

Создайте файл `.env` в текущей директории или установите переменные окружения:

```env
# Обязательные
SUPERSET_BASE_URL=https://superset.example.com
SUPERSET_USERNAME=admin
SUPERSET_PASSWORD=your_password

# Необязательные
SUPERSET_AUTH_PROVIDER=db          # db (по умолчанию) или ldap
SUPERSET_MCP_HOST=127.0.0.1       # Адрес сервера (по умолчанию: 127.0.0.1)
SUPERSET_MCP_PORT=8001             # Порт сервера (по умолчанию: 8001)
SUPERSET_MCP_TRANSPORT=streamable-http  # streamable-http (по умолчанию), sse или stdio
```

#### Аутентификация через session cookie (SSO/OAuth)

Если Superset работает за SSO (OAuth/OIDC/SAML), вход по логину и паролю
через REST API недоступен. Вместо этого укажите **session cookie** из браузера:

| Переменная | Описание |
| --- | --- |
| `SUPERSET_SESSION_COOKIE` | Значение session cookie из браузера. Если задано, используется вместо логина и пароля. |
| `SUPERSET_SESSION_COOKIE_NAME` | Имя cookie. По умолчанию `session`. |

Скопируйте cookie из инструментов разработчика браузера (Application →
Cookies → домен Superset → `session`). MCP-сервер отправляет её с каждым
запросом и получает с ней CSRF-токены. Сессию нельзя продлить на стороне
сервера, поэтому после истечения вставьте новое значение и перезапустите сервер.

Что стоит проверить перед использованием режима:

- **Имя cookie не всегда `session`.** Если в `superset_config.py` задан
  `SESSION_COOKIE_NAME`, имя будет другим (например, `s`). Возьмите имя из
  инструментов разработчика и укажите его в `SUPERSET_SESSION_COOKIE_NAME`.
- **Инстанс должен принимать сессионную аутентификацию на `/api/v1/`.** Там, где
  REST API настроен только на JWT, запрос с рабочей cookie всё равно вернёт
  `401 {"msg": "Missing Authorization Header"}` - обновление cookie не поможет,
  подходит только режим JWT.

Относитесь к cookie как к учётным данным: она даёт полный доступ к вашей учётной
записи Superset на всё время жизни сессии. Храните её в `.env` (файл в
gitignore), а не в истории команд и не в закоммиченных конфигах.

### Запуск

```bash
# Через CLI (после pip install)
mcp-superset

# Запуск без установки
uvx mcp-superset

# Через Python-модуль
python -m mcp_superset

# Через uv из исходников
uv run mcp-superset

# С пользовательскими параметрами
mcp-superset --host 0.0.0.0 --port 9000 --transport sse

# С указанием .env файла
mcp-superset --env-file /path/to/.env

# Через stdio (для Claude Desktop, Cursor и др.)
mcp-superset --transport stdio
```

### Параметры CLI

| Параметр | По умолчанию | Переменная окружения | Описание |
|----------|-------------|---------------------|----------|
| `--host` | `127.0.0.1` | `SUPERSET_MCP_HOST` | Адрес привязки сервера |
| `--port` | `8001` | `SUPERSET_MCP_PORT` | Порт сервера |
| `--transport` | `streamable-http` | `SUPERSET_MCP_TRANSPORT` | Транспорт: `streamable-http`, `sse`, `stdio` |
| `--env-file` | авто | — | Путь к `.env` файлу |
| `--version` | — | — | Показать версию и выйти |

### Подключение к MCP-клиентам

#### Claude Code

Добавьте в `.mcp.json` проекта:

```json
{
  "mcpServers": {
    "superset": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

Затем запустите сервер: `mcp-superset` или `uvx mcp-superset`.

#### Claude Desktop

Добавьте в `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "superset": {
      "command": "uvx",
      "args": ["mcp-superset", "--transport", "stdio"],
      "env": {
        "SUPERSET_BASE_URL": "https://superset.example.com",
        "SUPERSET_USERNAME": "admin",
        "SUPERSET_PASSWORD": "your_password"
      }
    }
  }
}
```

#### Cursor / Windsurf

```json
{
  "mcpServers": {
    "superset": {
      "command": "uvx",
      "args": ["mcp-superset", "--transport", "stdio"],
      "env": {
        "SUPERSET_BASE_URL": "https://superset.example.com",
        "SUPERSET_USERNAME": "admin",
        "SUPERSET_PASSWORD": "your_password"
      }
    }
  }
}
```

#### Другие MCP-клиенты

Любой MCP-совместимый клиент может подключиться через:
- **Streamable HTTP**: `http://<host>:<port>/mcp`
- **SSE**: `http://<host>:<port>/sse`
- **stdio**: пайп к `mcp-superset --transport stdio`

## Доступные инструменты (137)

Полный список инструментов — см. [README.md](README.md#available-tools-128) (English).

## Механизмы защиты

Сервер включает обширную встроенную защиту от случайной потери данных.

### Флаги подтверждения

Деструктивные операции требуют явного подтверждения:

| Операция | Требуемый флаг | Что показывает |
|----------|---------------|----------------|
| Удаление дашборда | `confirm_delete=True` | Название, slug, количество графиков |
| Удаление графика | `confirm_delete=True` | Привязанные дашборды |
| Удаление датасета | `confirm_delete=True` | Затронутые графики и дашборды |
| Удаление БД | `confirm_delete=True` | Затронутые датасеты, графики |
| Удаление RLS | `confirm_delete=True` | Clause, роли, датасеты |
| Удаление роли | `confirm_delete=True` | Блокирует системные роли |
| Удаление пользователя | `confirm_delete=True` | Блокирует удаление сервисного аккаунта |
| Обновление params графика | `confirm_params_replace=True` | — |
| Обновление columns датасета | `confirm_columns_replace=True` | — |
| Изменение URI БД | `confirm_uri_change=True` | Затронутые графики/дашборды |
| Обновление ролей пользователя | `confirm_roles_replace=True` | Текущие роли |
| Установка прав роли | `confirm_full_replace=True` | — |
| Выдача доступа к дашборду | `confirm_grant=True` | Результат dry-run |
| Отзыв доступа к дашборду | `confirm_revoke=True` | Результат dry-run |

### Автоматическая защита

- **Блокировка DDL/DML** — SQL Lab отклоняет `DROP`, `DELETE`, `UPDATE`, `INSERT`, `TRUNCATE`, `ALTER`, `CREATE`, `GRANT`, `REVOKE`
- **Защита системных ролей** — нельзя удалить Admin, Alpha, Gamma, Public
- **Защита сервисного аккаунта** — нельзя удалить MCP-пользователя
- **Безопасность RLS** — `rls_update` требует одновременно `roles` и `tables`
- **ID нативных фильтров** — автоматически генерируются в формате `NATIVE_FILTER-<uuid>`
- **Валидация графиков** — отклоняет графики без `granularity_sqla`
- **Авто-синхронизация** — права `datasource_access` автоматически синхронизируются при изменении ролей дашборда

## Архитектура

```
superset-mcp/
├── pyproject.toml              # Конфигурация пакета
├── .env.example                # Шаблон переменных окружения
├── LICENSE                     # Лицензия MIT
├── README.md                   # Документация (English)
├── README_RU.md                # Документация (Русский)
├── CHANGELOG.md                # История версий
└── src/mcp_superset/
    ├── __init__.py             # Инициализация с __version__
    ├── __main__.py             # CLI с argparse
    ├── server.py               # Настройка FastMCP-сервера
    ├── auth.py                 # JWT-аутентификация (login, refresh, CSRF)
    ├── client.py               # HTTP-клиент (авто-аутентификация, retry, RISON-пагинация)
    ├── models.py               # Pydantic-модели
    └── tools/
        ├── __init__.py         # register_all_tools()
        ├── helpers.py          # Авто-синхронизация datasource_access
        ├── dashboards.py       # Дашборды + фильтры (20)
        ├── charts.py           # Графики (11)
        ├── databases.py        # Базы данных (18)
        ├── datasets.py         # Датасеты (11)
        ├── queries.py          # SQL Lab + сохранённые запросы (13)
        ├── security.py         # Пользователи, роли, права, RLS (22)
        ├── groups.py           # Группы (9)
        ├── audit.py            # Аудит прав (1)
        ├── tags.py             # Теги (7)
        └── system.py           # Отчёты, аннотации, логи, ассеты (21)
```

## Совместимость с Superset

- **Протестировано с**: Apache Superset 6.0.1
- **Аутентификация**: JWT (рекомендуется) — API Key (`sst_*`) не реализован в Superset
- **Требуемый пользователь**: роль Admin (для полного доступа к API)

### Рекомендуемая настройка Superset

Добавьте в `superset_config.py`:

```python
from datetime import timedelta

# Увеличить время жизни JWT-токена (по умолчанию 15 мин)
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

# Максимальный размер страницы API
FAB_API_MAX_PAGE_SIZE = 100
```

## Разработка

### Настройка окружения

```bash
git clone https://github.com/bintocher/mcp-superset.git
cd superset-mcp

# Создать виртуальное окружение и установить в режиме разработки
uv venv
uv pip install -e ".[dev]"

# Скопировать и настроить .env
cp .env.example .env
# Отредактируйте .env с вашими данными Superset
```

### Локальный запуск

```bash
# Запуск из исходников
uv run python -m mcp_superset

# Или через CLI
uv run mcp-superset --port 8001
```

### Запуск тестов

```bash
uv run python test_all_tools.py
```

## Лицензия

[MIT](LICENSE) — Stanislav Chernov ([@bintocher](https://github.com/bintocher))
