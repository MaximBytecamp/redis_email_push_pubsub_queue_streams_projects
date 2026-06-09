# Отправка на настоящую почту

По умолчанию проект отправляет письма в Mailpit. Это безопасный тестовый режим:

```text
http://localhost:8025
```

Быстро вернуться к Mailpit из любых реальных SMTP-настроек:

```bash
cp .env.mailpit .env
docker compose up --build -d
```

Чтобы письма реально уходили людям, нужно подключить SMTP-аккаунт в `.env`.

## Что менять в проекте

Откройте файл `.env` и найдите блок:

```env
SMTP_HOST=smtp
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@example.com
SMTP_USE_TLS=false
SMTP_USE_SSL=false
SMTP_TIMEOUT=5
```

Именно эти `SMTP_*` значения используются Docker Compose для `backend` и `email_worker`.

После изменения `.env` всегда перезапускайте проект:

```bash
docker compose up --build -d
```

## Gmail: куда нажимать

Для Gmail нужен App Password. Обычный пароль от Gmail сюда вставлять не надо.

### 1. Включить двухэтапную проверку

1. Откройте браузер.
2. Перейдите на страницу Google Account:

```text
https://myaccount.google.com/security
```

3. Войдите в тот Gmail-аккаунт, с которого будут уходить письма.
4. Откройте вкладку или раздел `Security` / `Безопасность`.
5. Найдите блок `How you sign in to Google` / `Как вы входите в аккаунт Google`.
6. Нажмите `2-Step Verification` / `Двухэтапная аутентификация`.
7. Нажмите `Get started` / `Начать`.
8. Пройдите шаги Google: телефон, Google Prompt, Authenticator или другой второй фактор.
9. Дождитесь, что статус двухэтапной проверки станет включенным.

### 2. Создать App Password

1. Откройте прямую страницу:

```text
https://myaccount.google.com/apppasswords
```

2. Если Google просит пароль от аккаунта, введите его.
3. Если страницы нет или пункта App Passwords не видно, проверьте:
   - включена ли 2-Step Verification;
   - это не рабочий/учебный аккаунт с запретом администратора;
   - не включена ли Advanced Protection.
4. В поле названия приложения напишите, например:

```text
Email Mailing Service
```

5. Нажмите `Create` / `Создать`.
6. Google покажет пароль приложения из 16 символов.
7. Скопируйте его сразу. После закрытия окна Google больше не покажет этот пароль.

### 3. Вставить Gmail-настройки в `.env`

В `.env` замените Docker Compose SMTP-блок:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_character_app_password
SMTP_FROM=your_email@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT=5
```

Где:

- `SMTP_USER` - ваш Gmail-адрес.
- `SMTP_FROM` - обычно тот же Gmail-адрес.
- `SMTP_PASSWORD` - App Password, не обычный пароль.
- `SMTP_PORT=587` и `SMTP_USE_TLS=true` - отправка через STARTTLS.

## Yandex: куда нажимать

Для Yandex тоже лучше использовать пароль приложения.

### 1. Разрешить почтовые клиенты

1. Откройте Yandex Mail:

```text
https://mail.yandex.com/
```

2. Войдите в нужный аккаунт.
3. Откройте настройки почты. Обычно это иконка шестеренки.
4. Перейдите в раздел `Email clients` / `Почтовые программы`.
5. Включите опции для почтовых клиентов:
   - использование почтового клиента;
   - `App passwords and OAuth tokens` / `Пароли приложений и OAuth-токены`.
6. Сохраните изменения.

Если удобнее идти прямой ссылкой, попробуйте:

```text
https://mail.yandex.com/#setup/client
```

Если ссылка после входа откроет не тот экран, идите через шестеренку настроек.

### 2. Создать пароль приложения

1. Откройте Yandex ID:

```text
https://id.yandex.com/security/app-passwords
```

2. Войдите в тот же Yandex-аккаунт.
3. Нажмите `Create an app password` / `Создать пароль приложения`.
4. Выберите тип приложения `Mail` / `Почта`.
5. Введите название, например:

```text
Email Mailing Service
```

6. Нажмите `Next` / `Далее`.
7. Скопируйте показанный пароль приложения сразу. Yandex показывает его один раз.

### 3. Вставить Yandex-настройки в `.env`

Вариант через SSL-порт `465`:

```env
SMTP_HOST=smtp.yandex.com
SMTP_PORT=465
SMTP_USER=your_email@yandex.com
SMTP_PASSWORD=your_yandex_app_password
SMTP_FROM=your_email@yandex.com
SMTP_USE_TLS=false
SMTP_USE_SSL=true
SMTP_TIMEOUT=5
```

Если у вас адрес `@yandex.ru`, можно указать его:

```env
SMTP_USER=your_email@yandex.ru
SMTP_FROM=your_email@yandex.ru
```

Альтернативный вариант через STARTTLS-порт `587`:

```env
SMTP_HOST=smtp.yandex.com
SMTP_PORT=587
SMTP_USER=your_email@yandex.com
SMTP_PASSWORD=your_yandex_app_password
SMTP_FROM=your_email@yandex.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT=5
```

## Проверка после настройки

1. Перезапустите Docker Compose:

```bash
docker compose up --build -d
```

2. Откройте frontend:

```text
http://localhost:8000
```

3. Импортируйте CSV с настоящим email-адресом, лучше сначала только своим.
4. Создайте рассылку на эту группу или адрес.
5. Посмотрите статус письма в таблице `Письма рассылки`.

Если статус `sent`, письмо успешно передано SMTP-серверу.

## Частые ошибки

### `SMTP AUTH extension is not supported`

Обычно это значит, что вы пытаетесь авторизоваться на тестовом Mailpit или не тот SMTP-сервер. Для Mailpit логин и пароль должны быть пустыми. Для Gmail/Yandex должен быть реальный SMTP-хост.

### `Username and Password not accepted`

Для Gmail/Yandex чаще всего вставлен обычный пароль вместо App Password.

### `Connection refused`

Проверьте `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_USE_SSL`.

### Письмо долго висит в `sending`

Worker ждет ответ SMTP-сервера. За это отвечает:

```env
SMTP_TIMEOUT=5
```

Если SMTP не ответит за это время, задача станет `failed`, а worker перейдет к следующему письму.

### Письмо ушло, но попало в спам

Для реальных массовых рассылок нужен нормальный домен и DNS-настройки SPF, DKIM, DMARC.

## Важно

- App Password нельзя коммитить в git и нельзя отправлять в чат.
- Не отправляйте рассылку на `@example.com`: это тестовые адреса.
- Сначала проверьте отправку на 1 свой адрес.
- Gmail/Yandex подходят для маленького теста, но не для большой массовой рассылки.
- Для production лучше использовать специализированный SMTP-провайдер.
