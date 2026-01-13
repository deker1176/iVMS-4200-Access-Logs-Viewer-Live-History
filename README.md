# iVMS-4200 Access Logs Viewer (Live + History)

Веб-панель для просмотра проходов (событий доступа) из Microsoft SQL Server, куда iVMS-4200 пишет таблицу (например `thirdparty.dbo.attlog`).

## Возможности

- Журнал событий (история).
- Live-обновление через SSE.
- Фильтры: дата/время, дверь, поиск (ФИО/карта/ID).
- Исправление “кракозябр” (mojibake) от iVMS-4200 для русских строк.
- Сводка “кто где”.
- Отчёт рабочего времени (если включено).

## Содержание

- [Требования](#требования)
- [Структура проекта](#структура-проекта)
- [Установка зависимостей](#установка-зависимостей)
- [SQL: база и таблица](#sql-база-и-таблица)
- [Настройка iVMS-4200](#настройка-ivms-4200)
- [Подключение к БД в проекте](#подключение-к-бд-в-проекте)
- [Запуск вручную](#запуск-вручную)
- [Запуск как служба через NSSM](#запуск-как-служба-через-nssm)
- [Почему бывают “кракозябры”](#почему-бывают-кракозябры)
- [API](#api)
- [Частые проблемы](#частые-проблемы)
- [Лицензия и рекомендации](#лицензия-и-рекомендации)
- [English Version](#english-version)

## Требования

### ОС

- Windows Server / Windows 10+ (проверено на Windows Server 2012/2016/2019/2022).

### Python

- Python 3.10+ (работает и на 3.13).

### База данных

- Microsoft SQL Server (локально или удалённо).
- Таблица `dbo.attlog` в базе `thirdparty` (или другая — настраивается).
- Инструкция по установке и настройке SQL Server: [SQL-Server-Basic-Installation-and-Configuration.pdf](SQL-Server-Basic-Installation-and-Configuration.pdf).

### ПО

- iVMS-4200 (модуль Access Control / Time & Attendance).
- (Опционально) `nssm.exe` для запуска как службы.

## Структура проекта

```
project/
  app.py
  db.py
  analytics.py
  utils.py
  templates.py
  requirements.txt
  logs/              # создаётся автоматически
```

## Установка зависимостей

Откройте CMD/PowerShell:

```bash
cd C:\scripts
python -m venv venv
venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Пример `requirements.txt`:

```
flask
pyodbc
```

> Если `pyodbc` не ставится — установите “Microsoft Visual C++ Redistributable” и ODBC драйвер SQL.

## SQL: база и таблица

### 1) Создать базу (если нужно)

```sql
CREATE DATABASE thirdparty;
GO
```

### 2) Создать таблицу `dbo.attlog`

Важно: `NVARCHAR` для русских полей. `serialNo` — уникальный, по нему удобно делать live-дозагрузку.

```sql
USE thirdparty;
GO

IF OBJECT_ID('dbo.attlog', 'U') IS NULL
BEGIN
  CREATE TABLE dbo.attlog (
      serialNo      INT            NOT NULL,
      authDateTime  DATETIME2(3)    NULL,
      authDate      NVARCHAR(20)    NULL,
      authTime      NVARCHAR(20)    NULL,
      direction     NVARCHAR(20)    NULL,      -- "vhod" / "vihod" или что пишет iVMS
      deviceName    NVARCHAR(255)   NULL,      -- дверь/устройство (часто кракозябра)
      deviceSN      NVARCHAR(128)   NULL,
      personName    NVARCHAR(255)   NULL,      -- ФИО (часто кракозябра)
      cardNo        NVARCHAR(64)    NULL,
      doorName      NVARCHAR(255)   NULL,
      readerName    NVARCHAR(255)   NULL,

      CONSTRAINT PK_attlog PRIMARY KEY CLUSTERED (serialNo)
  );
END
GO
```

### 3) Индексы (рекомендуется)

```sql
USE thirdparty;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_attlog_authDateTime' AND object_id=OBJECT_ID('dbo.attlog'))
    CREATE INDEX IX_attlog_authDateTime ON dbo.attlog(authDateTime DESC);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_attlog_deviceName' AND object_id=OBJECT_ID('dbo.attlog'))
    CREATE INDEX IX_attlog_deviceName ON dbo.attlog(deviceName);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_attlog_personName' AND object_id=OBJECT_ID('dbo.attlog'))
    CREATE INDEX IX_attlog_personName ON dbo.attlog(personName);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_attlog_cardNo' AND object_id=OBJECT_ID('dbo.attlog'))
    CREATE INDEX IX_attlog_cardNo ON dbo.attlog(cardNo);
GO
```

## Настройка iVMS-4200

### 1) Подключение к “сторонней базе”

В iVMS-4200 (Time & Attendance / Время и посещаемость):

- “Сторонняя база данных” → подключение к SQL Server.
- Таблица: `attlog`.

### 2) Маппинг полей (пример)

В iVMS обычно есть таблица соответствий:

- `serialNo` → `serialNo` (или `employeeID`, если так настроено, но лучше `serialNo`).
- `authDateTime` → `authDateTime`.
- `direction` → `direction` (значения: `vhod` / `vihod`).

Важно: если у вас разные устройства для входа/выхода — в iVMS нужно правильно связать считыватели и события (“Привязка события / Привязка карты”, “Точка контроля доступа”, и т.п.), иначе `vihod` может не появляться.

## Подключение к БД в проекте

В `app.py` задаётся строка подключения, например:

```python
DB_CONN_STR = (
    "DRIVER={SQL Server Native Client 11.0};"
    "SERVER=127.0.0.1;"
    "DATABASE=thirdparty;"
    "UID=sa;"
    "PWD=YOUR_PASSWORD;"
    "TrustServerCertificate=yes;"
)

TABLE_NAME = "dbo.attlog"
```

Можно переопределять через переменные окружения (если реализовано):

- `IVMS_HOST` (по умолчанию `0.0.0.0`)
- `IVMS_PORT` (по умолчанию `8099`)
- `IVMS_DEBUG` (`1`/`0`)

## Запуск вручную

```bash
cd C:\scripts
venv\Scripts\activate
python app.py
```

Открыть в браузере:

```
http://127.0.0.1:8099
```

## Запуск как служба через NSSM

### 1) Подготовка

Скачайте `nssm.exe` и положите, например, в `C:\nssm\nssm.exe`.

### 2) Установка службы

```bat
C:\nssm\nssm.exe install ivms_attlog
```

В окне NSSM:

**Application**

- **Path:** `C:\scripts\venv\Scripts\python.exe` (или путь к системному `python.exe`)
- **Arguments:** `C:\scripts\app.py`
- **Startup directory:** `C:\scripts`

**Environment (опционально)**

- `IVMS_HOST=0.0.0.0`
- `IVMS_PORT=8099`
- `IVMS_DEBUG=0`

### 3) Логи

Приложение пишет лог в файл:

```
C:\scripts\logs\log.txt
```

(ротация включена, будет несколько файлов)

### 4) Запуск/остановка

```bat
net start ivms_attlog
net stop ivms_attlog
```

## Почему бывают “кракозябры”

iVMS-4200 иногда пишет русские строки в базу в неверной кодировке (UTF-8 байты, интерпретированные как CP1251). Проект исправляет это на уровне приложения функцией в `utils.py`, чтобы:

- в UI всё отображалось по-русски;
- фильтрация по дверям работала даже если в базе “кракозябра”
  (в запросе используется вариант “как пришло” + “mojibake-вариант”).

## API

- `GET /api/doors` — список дверей/устройств для фильтра.
- `GET /api/log?...` — события (фильтры через query string).
- `GET /api/summary?...` — сводка.
- `GET /api/worktime?...` — рабочее время.
- `GET /sse` — live поток событий (Server-Sent Events).

## Частые проблемы

### “Internal Server Error” при запуске через NSSM

Почти всегда причина:

- неправильный **Startup directory** (должен быть `C:\scripts`);
- включён Flask reloader (`debug=True + reloader`) — для службы нельзя
  (в проекте `use_reloader=False`).

### Нет событий “Выход”

Проверьте в iVMS привязки:

- правильный тип события;
- правильный считыватель (вход/выход);
- правильная логика точки доступа/турникета.

## Лицензия и рекомендации

### Лицензия

Добавьте нужную (MIT/Apache-2.0/Private).

### Что ещё положить в репозиторий (рекомендации)

```
.gitignore
venv/
__pycache__/
*.pyc
logs/
*.log
STATE*.json
LICENSE
```

(по желанию)

---

## English Version

Web dashboard for viewing access events (live + history) from Microsoft SQL Server where iVMS-4200 writes its table (for example, `thirdparty.dbo.attlog`).

### Features

- Event log (history).
- Live updates via SSE.
- Filters: date/time, door, search (name/card/ID).
- Fixes mojibake from iVMS-4200 for Cyrillic strings.
- “Who is where” summary.
- Work time report (if enabled).

### Contents

- [Requirements](#requirements)
- [Project structure](#project-structure)
- [Install dependencies](#install-dependencies)
- [SQL: database and table](#sql-database-and-table)
- [iVMS-4200 configuration](#ivms-4200-configuration)
- [Database connection in the project](#database-connection-in-the-project)
- [Run manually](#run-manually)
- [Run as a service with NSSM](#run-as-a-service-with-nssm)
- [Why mojibake happens](#why-mojibake-happens)
- [API](#api-1)
- [Troubleshooting](#troubleshooting)
- [License and recommendations](#license-and-recommendations)

### Requirements

**OS**

- Windows Server / Windows 10+ (tested on Windows Server 2012/2016/2019/2022).

**Python**

- Python 3.10+ (works on 3.13).

**Database**

- Microsoft SQL Server (local or remote).
- `dbo.attlog` table in the `thirdparty` database (or another one — configurable).
- SQL Server install & configuration guide: [SQL-Server-Basic-Installation-and-Configuration.pdf](SQL-Server-Basic-Installation-and-Configuration.pdf).

**Software**

- iVMS-4200 (Access Control / Time & Attendance module).
- (Optional) `nssm.exe` to run as a service.

### Project structure

```
project/
  app.py
  db.py
  analytics.py
  utils.py
  templates.py
  requirements.txt
  logs/              # created automatically
```

### Install dependencies

Open CMD/PowerShell:

```bash
cd C:\scripts
python -m venv venv
venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Example `requirements.txt`:

```
flask
pyodbc
```

> If `pyodbc` fails to install, install the “Microsoft Visual C++ Redistributable” and SQL ODBC driver.

### SQL: database and table

**1) Create database (if needed)**

```sql
CREATE DATABASE thirdparty;
GO
```

**2) Create `dbo.attlog` table**

Important: use `NVARCHAR` for Cyrillic fields. `serialNo` is unique and is convenient for live pagination.

```sql
USE thirdparty;
GO

IF OBJECT_ID('dbo.attlog', 'U') IS NULL
BEGIN
  CREATE TABLE dbo.attlog (
      serialNo      INT            NOT NULL,
      authDateTime  DATETIME2(3)    NULL,
      authDate      NVARCHAR(20)    NULL,
      authTime      NVARCHAR(20)    NULL,
      direction     NVARCHAR(20)    NULL,      -- "vhod" / "vihod" or whatever iVMS writes
      deviceName    NVARCHAR(255)   NULL,      -- door/device (often mojibake)
      deviceSN      NVARCHAR(128)   NULL,
      personName    NVARCHAR(255)   NULL,      -- full name (often mojibake)
      cardNo        NVARCHAR(64)    NULL,
      doorName      NVARCHAR(255)   NULL,
      readerName    NVARCHAR(255)   NULL,

      CONSTRAINT PK_attlog PRIMARY KEY CLUSTERED (serialNo)
  );
END
GO
```

**3) Indexes (recommended)**

```sql
USE thirdparty;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_attlog_authDateTime' AND object_id=OBJECT_ID('dbo.attlog'))
    CREATE INDEX IX_attlog_authDateTime ON dbo.attlog(authDateTime DESC);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_attlog_deviceName' AND object_id=OBJECT_ID('dbo.attlog'))
    CREATE INDEX IX_attlog_deviceName ON dbo.attlog(deviceName);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_attlog_personName' AND object_id=OBJECT_ID('dbo.attlog'))
    CREATE INDEX IX_attlog_personName ON dbo.attlog(personName);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_attlog_cardNo' AND object_id=OBJECT_ID('dbo.attlog'))
    CREATE INDEX IX_attlog_cardNo ON dbo.attlog(cardNo);
GO
```

### iVMS-4200 configuration

**1) Connect to “third-party database”**

In iVMS-4200 (Time & Attendance):

- “Third-party database” → connect to SQL Server.
- Table: `attlog`.

**2) Field mapping (example)**

- `serialNo` → `serialNo` (or `employeeID` if configured, but `serialNo` is better).
- `authDateTime` → `authDateTime`.
- `direction` → `direction` (values: `vhod` / `vihod`).

Important: if you have separate entry/exit devices, bind the readers and events correctly (Event linkage / Card linkage / Access control point), otherwise `vihod` may never appear.

### Database connection in the project

Connection string in `app.py`, for example:

```python
DB_CONN_STR = (
    "DRIVER={SQL Server Native Client 11.0};"
    "SERVER=127.0.0.1;"
    "DATABASE=thirdparty;"
    "UID=sa;"
    "PWD=YOUR_PASSWORD;"
    "TrustServerCertificate=yes;"
)

TABLE_NAME = "dbo.attlog"
```

Environment variables (if implemented):

- `IVMS_HOST` (default `0.0.0.0`)
- `IVMS_PORT` (default `8099`)
- `IVMS_DEBUG` (`1`/`0`)

### Run manually

```bash
cd C:\scripts
venv\Scripts\activate
python app.py
```

Open in browser:

```
http://127.0.0.1:8099
```

### Run as a service with NSSM

**1) Preparation**

Download `nssm.exe` and place it, for example, at `C:\nssm\nssm.exe`.

**2) Install the service**

```bat
C:\nssm\nssm.exe install ivms_attlog
```

NSSM window:

**Application**

- **Path:** `C:\scripts\venv\Scripts\python.exe` (or system `python.exe`)
- **Arguments:** `C:\scripts\app.py`
- **Startup directory:** `C:\scripts`

**Environment (optional)**

- `IVMS_HOST=0.0.0.0`
- `IVMS_PORT=8099`
- `IVMS_DEBUG=0`

**3) Logs**

```
C:\scripts\logs\log.txt
```

(rotation enabled, multiple files)

**4) Start/stop**

```bat
net start ivms_attlog
net stop ivms_attlog
```

### Why mojibake happens

iVMS-4200 sometimes writes Cyrillic strings into the database using the wrong encoding (UTF-8 bytes interpreted as CP1251). The project fixes this in the app layer (see `utils.py`) so that:

- UI shows readable Russian;
- door filtering works even with mojibake (the query uses “as stored” + “mojibake variant”).

### API

- `GET /api/doors` — list of doors/devices for filters.
- `GET /api/log?...` — events (filters via query string).
- `GET /api/summary?...` — summary.
- `GET /api/worktime?...` — work time.
- `GET /sse` — live stream of events (Server-Sent Events).

### Troubleshooting

**“Internal Server Error” when running with NSSM**

Most common causes:

- wrong **Startup directory** (must be `C:\scripts`);
- Flask reloader enabled (`debug=True + reloader`) — not allowed for a service
  (set `use_reloader=False`).

**No “Exit” events**

Check in iVMS:

- correct event type;
- correct reader (entry/exit);
- correct access point/turnstile logic.

### License and recommendations

**License**

Add one (MIT/Apache-2.0/Private).

**Recommended files**

```
.gitignore
venv/
__pycache__/
*.pyc
logs/
*.log
STATE*.json
LICENSE
```
