# Email Mailing Service

Backend-сервис email-рассылок для учебной платформы.

Проект показывает практическое применение Redis:

- Redis Queue через `LPUSH` / `BRPOP` для фоновых задач.
- Redis Pub/Sub для live-уведомлений.
- Redis Streams для истории событий.
- SMTP для реальной отправки писем в тестовый почтовый ящик.

В проекте есть графический frontend: можно загрузить получателей, создать рассылку, смотреть статусы писем, live-события и историю.

## Быстрый старт

### 1. Подготовить `.env`

```bash
cp .env.example .env
```

Для первого запуска ничего менять не нужно: проект уже настроен на тестовый SMTP Mailpit.

### 2. Запустить проект через Docker Compose

```bash
docker compose up --build
```

Поднимутся сервисы:

- `backend` - FastAPI-приложение.
- `redis` - Redis для очередей, Pub/Sub и Streams.
- `smtp` - Mailpit, тестовый SMTP-сервер.
- `import_worker` - worker импорта получателей.
- `email_worker` - worker отправки писем.

### 3. Открыть страницы

- Frontend проекта: http://localhost:8000
- Swagger API: http://localhost:8000/docs
- Mailpit, входящие письма: http://localhost:8025

Если порт `8000` уже занят, можно запустить локально на другом порту, например `8001`, и открыть `http://127.0.0.1:8001`.

## Как работать через frontend

Откройте:

```text
http://localhost:8000
```

На странице есть несколько зон:

- `Импорт получателей` - загрузка CSV/XLSX-файла.
- `Новая рассылка` - создание email-рассылки.
- `Рассылки` - список рассылок и прогресс отправки.
- `Письма рассылки` - статусы отдельных писем.
- `Live` - уведомления из Redis Pub/Sub.
- `История событий` - события из Redis Streams.
- `Получатели` - сохраненные получатели из БД.

## Шаг 1. Добавить получателей

Файл, который загружается в проект, нужен не как вложение к письму.

Его смысл - массово добавить получателей в базу данных. То есть CSV/XLSX является таблицей адресатов: кто должен получать письма, какой у него email и к какой группе он относится.

После импорта файл уже не отправляется получателям. Система берет из него email-адреса, проверяет их, сохраняет корректные адреса в БД, а затем эти адреса можно использовать при создании рассылки.

Можно использовать готовые файлы:

```text
examples/recipients.csv
examples/more_recipients.csv
```

### Формат CSV

```csv
name,email,group
Иван Петров,ivan@example.com,РПО-1
Анна Смирнова,anna@example.com,РПО-2
Петр Иванов,wrong-email,РПО-1
```

### Что означают колонки

- `name` - имя получателя. Может использоваться для просмотра в таблице и будущей персонализации писем.
- `email` - адрес получателя. Это главная колонка, без нее строка не имеет смысла.
- `group` - учебная группа или категория получателей, например `РПО-1`.

Колонка `group` нужна, чтобы потом создать рассылку не вручную по адресам, а сразу по группе. Например, если в файле есть 20 студентов с группой `РПО-1`, то при создании рассылки можно указать `РПО-1`, и система сама найдет всех этих студентов.

### Что происходит с файлом после загрузки

Когда администратор прикрепляет файл во frontend и нажимает `Загрузить в очередь`, происходит такой процесс:

1. Frontend отправляет файл в backend endpoint `POST /imports`.
2. Backend сохраняет файл в папку загрузок.
3. В таблице `recipient_imports` создается задача импорта со статусом `queued`.
4. ID задачи кладется в Redis Queue `imports:queue`.
5. HTTP-запрос завершается быстро, потому что сам файл не обрабатывается внутри запроса.
6. `app.workers.import_worker` отдельно забирает ID задачи из Redis через `BRPOP`.
7. Worker открывает файл с диска.
8. Worker читает строки из CSV/XLSX.
9. Для каждой строки проверяется email.
10. Невалидные email считаются как ошибки импорта.
11. Дублирующиеся email не добавляются повторно.
12. Корректные получатели сохраняются в таблицу `recipients`.
13. Статус импорта меняется на `done` или `failed`.
14. Событие пишется в Redis Streams `system:events`.
15. Live-уведомление публикуется в Redis Pub/Sub канал `notifications`.

### Пример результата импорта

Если загрузить файл:

```csv
name,email,group
Иван Петров,ivan@example.com,РПО-1
Анна Смирнова,anna@example.com,РПО-2
Петр Иванов,wrong-email,РПО-1
Иван Дубль,ivan@example.com,РПО-1
```

то результат будет примерно такой:

```json
{
  "status": "done",
  "total_rows": 4,
  "valid_emails": 2,
  "invalid_emails": 1,
  "duplicates": 1
}
```

Объяснение:

- `ivan@example.com` сохранится один раз.
- `anna@example.com` сохранится.
- `wrong-email` не сохранится, потому что это невалидный email.
- второй `ivan@example.com` не сохранится, потому что это дубль.

### Почему файл не прикрепляется к письму

В этом проекте файл импорта - это не attachment.

Он используется только на первом этапе, чтобы наполнить базу получателей. После этого рассылка работает уже с данными из БД:

```text
CSV/XLSX файл
     |
     v
app.workers.import_worker
     |
     v
таблица recipients
     |
     v
создание рассылки по группе или email
     |
     v
app.workers.email_worker отправляет письма через SMTP
```

Если нужно отправлять пользователям файл как вложение к письму, это отдельная доработка: надо добавить загрузку attachment при создании рассылки и изменить `smtp_client.py`, чтобы он прикреплял файл к email-сообщению.

Что делать:

1. Откройте frontend.
2. В блоке `Импорт получателей` выберите CSV или XLSX.
3. Нажмите `Загрузить в очередь`.
4. FastAPI сохранит файл и положит ID задачи в Redis Queue `imports:queue`.
5. `app.workers.import_worker` заберет задачу через `BRPOP`.
6. После обработки получатели появятся в таблице `Получатели`.

Worker считает:

- всего строк;
- валидные email;
- невалидные email;
- дубли.

## Шаг 2. Создать рассылку

В блоке `Новая рассылка` можно выбрать два режима.

### Вариант 1. Получатели вручную

Выберите режим `Email` и введите адреса через запятую или с новой строки:

```text
ivan@example.com, anna@example.com
```

Заполните:

- `Название`;
- `Тема письма`;
- `Текст письма`;
- `Получатели вручную`.

Нажмите:

```text
Создать и отправить
```

### Вариант 2. Получатели по группе

Выберите режим `Группа`.

Например:

```text
РПО-1
```

Система найдет всех получателей из этой группы и создаст отдельную email-задачу для каждого.

## Что происходит после создания рассылки

После нажатия `Создать и отправить`:

1. FastAPI создает запись в таблице `mailings`.
2. Для каждого получателя создается запись в `email_tasks`.
3. Каждой задаче ставится статус `queued`.
4. ID задач кладутся в Redis Queue `email:queue`.
5. `app.workers.email_worker` забирает задачи через `BRPOP`.
6. Worker отправляет письма через SMTP.
7. Статусы меняются на `sending`, затем `sent` или `failed`.
8. События пишутся в Redis Streams `system:events`.
9. Live-уведомления публикуются в Redis Pub/Sub канал `notifications`.

## Где посмотреть пришедшие письма

Для тестовой почты используется Mailpit.

Откройте:

```text
http://localhost:8025
```

Это веб-интерфейс тестового почтового ящика.

Что там можно увидеть:

- список всех отправленных писем;
- получателя письма;
- тему письма;
- текст письма;
- дату отправки;
- технические заголовки письма.

Как проверить письмо:

1. Создайте рассылку во frontend.
2. Дождитесь статуса `sent` в таблице писем.
3. Откройте Mailpit: http://localhost:8025
4. Нажмите на нужное письмо в списке.
5. Проверьте `To`, `Subject` и тело письма.

Важно: письма не уходят реальным людям, если используется Mailpit. Они попадают в локальный тестовый ящик.

## SMTP-настройки

Настройки находятся в `.env`.

Для локального запуска с Mailpit:

```env
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@example.com
SMTP_USE_TLS=false
SMTP_USE_SSL=false
```

В Docker Compose backend и worker подключаются к Mailpit по имени сервиса:

```env
SMTP_HOST=smtp
SMTP_PORT=1025
SMTP_USE_TLS=false
SMTP_USE_SSL=false
```

Это уже прописано в `docker-compose.yml`.

Быстро вернуться в тестовый режим Mailpit:

```bash
cp .env.mailpit .env
docker compose up --build -d
```

После этого письма снова не уходят реальным людям, а появляются в Mailpit: http://localhost:8025.

## Как использовать настоящий SMTP

Можно подключить Gmail, Yandex, Mailtrap, Ethereal Email или другой SMTP.

Для Docker Compose меняются переменные `SMTP_*` в `.env`.

Пример для Gmail или другого SMTP на порту `587`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=your_email@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

Для SMTP на порту `465`:

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_password_or_app_password
SMTP_FROM=your_email@example.com
SMTP_USE_TLS=false
SMTP_USE_SSL=true
```

После изменения `.env` перезапустите backend и `email_worker`:

```bash
docker compose up --build -d
```

Для Gmail обычно нужен не обычный пароль, а App Password.

Подробная инструкция: `REAL_EMAIL_SETUP.md`.

## Частая ошибка: localhost:1025 connection failed

Ошибка вида:

```text
Error connecting to localhost on port 1025
Connect call failed ('127.0.0.1', 1025)
```

означает, что SMTP-сервер не запущен.

Решение для Docker:

```bash
docker compose up -d smtp
```

Проверить Mailpit:

```text
http://localhost:8025
```

Проверить, что SMTP-порт слушается:

```bash
lsof -iTCP:1025 -sTCP:LISTEN
```

После запуска SMTP можно повторить failed-письма во frontend кнопкой:

```text
Retry failed
```

или через API:

```bash
curl -X POST http://localhost:8000/mailings/1/retry-failed
```

## Ручной запуск без Docker

Нужны отдельно запущенные Redis и SMTP-сервер.

### 1. Установить зависимости

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Запустить FastAPI

```bash
uvicorn app.main:app --reload --port 8000
```

Если порт занят:

```bash
uvicorn app.main:app --reload --port 8001
```

### 3. Запустить workers в отдельных терминалах

```bash
python -m app.workers.import_worker
```

```bash
python -m app.workers.email_worker
```

### 4. Опционально смотреть Pub/Sub в терминале

```bash
python scripts/pubsub_listener.py
```

## API endpoints

- `POST /imports` - загрузить файл получателей.
- `GET /imports/{import_id}` - получить статус импорта.
- `GET /recipients` - получить список получателей.
- `POST /mailings` - создать рассылку.
- `GET /mailings` - получить список рассылок.
- `GET /mailings/{mailing_id}` - получить конкретную рассылку.
- `GET /mailings/{mailing_id}/emails` - получить письма внутри рассылки.
- `POST /mailings/{mailing_id}/retry-failed` - повторить отправку failed-писем.
- `GET /events` - получить историю событий из Redis Streams.
- `GET /mailings/{mailing_id}/events` - события конкретной рассылки.
- `GET /notifications/stream` - live-уведомления через SSE.

## Примеры API-запросов

Загрузить CSV:

```bash
curl -F file=@examples/more_recipients.csv http://localhost:8000/imports
```

Создать рассылку по группе:

```bash
curl -X POST http://localhost:8000/mailings \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Демо-рассылка для РПО-1",
    "subject": "Проверка получения писем",
    "body": "Здравствуйте! Это демонстрационная рассылка через Redis Queue и SMTP.",
    "group": "РПО-1"
  }'
```

Проверить письма рассылки:

```bash
curl http://localhost:8000/mailings/1/emails
```

Повторить failed-письма:

```bash
curl -X POST http://localhost:8000/mailings/1/retry-failed
```

Посмотреть события:

```bash
curl http://localhost:8000/events
```

## Где используется Redis

### Redis Queue

Очередь импорта:

```text
imports:queue
```

Команды:

```text
LPUSH imports:queue <import_id>
BRPOP imports:queue
```

Очередь отправки писем:

```text
email:queue
```

Команды:

```text
LPUSH email:queue <email_task_id>
BRPOP email:queue
```

### Redis Pub/Sub

Канал:

```text
notifications
```

Используется для live-уведомлений на frontend. Для отладки события можно смотреть в `scripts/pubsub_listener.py`.

### Redis Streams

Stream:

```text
system:events
```

Используется как журнал событий.

Примеры событий:

- `import_queued`
- `import_started`
- `import_completed`
- `mailing_created`
- `email_queued`
- `email_sending`
- `email_sent`
- `email_failed`
- `retry_failed_emails`
- `mailing_completed`

## Статусы

### Импорт

- `queued` - файл ожидает обработки.
- `processing` - файл обрабатывается.
- `done` - импорт завершен.
- `failed` - ошибка импорта.

### Рассылка

- `created` - рассылка создана.
- `processing` - письма отправляются.
- `completed` - все письма отправлены.
- `partially_failed` - часть писем не отправилась.
- `failed` - все письма завершились ошибкой.

### Письмо

- `queued` - письмо ожидает отправки.
- `sending` - письмо отправляется.
- `sent` - письмо отправлено.
- `failed` - ошибка отправки.

## Сценарий демонстрации

1. Запустить проект:

```bash
docker compose up --build
```

2. Открыть frontend:

```text
http://localhost:8000
```

3. Загрузить:

```text
examples/more_recipients.csv
```

4. Убедиться, что получатели появились в таблице.

5. Создать рассылку по группе:

```text
РПО-1
```

6. Дождаться статусов `sent`.

7. Открыть Mailpit:

```text
http://localhost:8025
```

8. Открыть любое письмо и проверить тему, получателя и текст.

9. На frontend посмотреть:

- прогресс рассылки;
- таблицу писем;
- live-уведомления;
- историю событий.

10. Если есть failed-письма, нажать `Retry failed`.
