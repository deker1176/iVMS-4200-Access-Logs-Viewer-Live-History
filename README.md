# iVMS-4200-Access-Logs-Viewer-Live-History-
iVMS-4200 Access Logs Viewer (Live + History)

Веб-панель для просмотра проходов (событий доступа) из SQL Server, куда iVMS-4200 пишет таблицу (например thirdparty.dbo.attlog).
Поддерживает:

Лог событий (история)

Live-обновление (SSE)

Фильтры: дата/время, дверь, поиск (ФИО/карта/ID)

Исправление “кракозябр” (mojibake) от iVMS-4200 для русских строк

Сводка “кто где”

Отчёт рабочего времени (если включено)

1) Требования
ОС

Windows Server / Windows 10+ (проверено на Windows Server 2012/2016/2019/2022)

Python 3.10+ (работает и на 3.13)

База данных

Microsoft SQL Server (локально или удалённо)

Таблица dbo.attlog в базе thirdparty (или другая — настраивается)

ПО

iVMS-4200 (модуль Access Control / Time & Attendance)

(Опционально) nssm.exe для запуска как службы

2) Структура проекта
project/
  app.py
  db.py
  analytics.py
  utils.py
  templates.py
  requirements.txt
  logs/              # создаётся автоматически

3) Установка Python зависимостей

Открой CMD/PowerShell:

cd C:\scripts
python -m venv venv
venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt


Пример requirements.txt:

flask
pyodbc


Если pyodbc не ставится — установи “Microsoft Visual C++ Redistributable” и ODBC драйвер SQL.

4) SQL: база и таблица
4.1 Создать базу (если нужно)
CREATE DATABASE thirdparty;
GO

4.2 Создать таблицу dbo.attlog

Важно: NVARCHAR для русских полей.
serialNo — уникальный, по нему удобно делать live-дозагрузку.

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

4.3 Индексы (рекомендуется)
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

5) Настройка iVMS-4200 (чтобы он писал в таблицу)
5.1 Подключение к “сторонней базе”

В iVMS-4200 (Time & Attendance / Время и посещаемость):

“Сторонняя база данных” → подключение к SQL Server

Таблица: attlog

5.2 Маппинг полей (пример)

В iVMS обычно есть таблица соответствий:

serialNo → serialNo (или employeeID если так сделано, но лучше serialNo)

authDateTime → authDateTime

direction → direction (значения: vhod / vihod)

Важно: если у вас разные устройства для входа/выхода — в iVMS нужно правильно связать считыватели и события (“Привязка события / Привязка карты”, “Точка контроля доступа”, и т.п.), иначе vihod может не появляться.

6) Настройка подключения к БД в проекте

В app.py задаётся строка подключения, например:

DB_CONN_STR = (
    "DRIVER={SQL Server Native Client 11.0};"
    "SERVER=127.0.0.1;"
    "DATABASE=thirdparty;"
    "UID=sa;"
    "PWD=YOUR_PASSWORD;"
    "TrustServerCertificate=yes;"
)

TABLE_NAME = "dbo.attlog"


Можно переопределять через переменные окружения (если реализовано):

IVMS_HOST (по умолчанию 0.0.0.0)

IVMS_PORT (по умолчанию 8099)

IVMS_DEBUG (1/0)

7) Запуск вручную
cd C:\scripts
venv\Scripts\activate
python app.py


Открыть в браузере:

http://127.0.0.1:8099

8) Запуск как служба через NSSM (Windows)
8.1 Подготовка

Скачай nssm.exe и положи, например, в C:\nssm\nssm.exe

8.2 Установка службы
C:\nssm\nssm.exe install ivms_attlog


В окне NSSM:

Application

Path: C:\scripts\venv\Scripts\python.exe
(или путь к системному python.exe)

Arguments: C:\scripts\app.py

Startup directory: C:\scripts

Environment (опционально)

IVMS_HOST=0.0.0.0

IVMS_PORT=8099

IVMS_DEBUG=0

8.3 Логи

Приложение пишет лог в файл:

C:\scripts\logs\log.txt


(ротация включена, будет несколько файлов)

8.4 Запуск/остановка
net start ivms_attlog
net stop ivms_attlog

9) Почему бывают “кракозябры” и как решено

iVMS-4200 иногда пишет русские строки в базу в неверной кодировке (UTF-8 байты, интерпретированные как CP1251).
Проект исправляет это на уровне приложения функцией в utils.py, чтобы:

в UI всё отображалось по-русски

фильтрация по дверям работала даже если в базе “кракозябра”
(в запросе используется вариант “как пришло” + “mojibake-вариант”)

10) API (если нужно интегрировать)

GET /api/doors — список дверей/устройств для фильтра

GET /api/log?... — события (фильтры через query string)

GET /api/summary?... — сводка

GET /api/worktime?... — рабочее время

GET /sse — live поток событий (Server-Sent Events)

11) Частые проблемы
“Internal Server Error” при запуске через NSSM

Почти всегда причина:

неправильный Startup directory (должен быть C:\scripts)

включён Flask reloader (debug=True + reloader) — для службы нельзя
(в проекте use_reloader=False)

Нет событий “Выход”

Проверь в iVMS привязки:

правильный тип события

правильный считыватель (вход/выход)

правильная логика точки доступа/турникета

12) Лицензия

Добавь нужную (MIT/Apache-2.0/Private).

Что ещё положить в репозиторий (рекомендации)

Добавь файлы:

.gitignore
venv/
__pycache__/
*.pyc
logs/
*.log
STATE*.json

LICENSE

(по желанию)
