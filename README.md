# Avito API Client

Небольшой Python-класс `Avito_API` для работы с Avito API:

- получение access token;
- выгрузка списка объявлений;
- получение статистики по объявлениям;
- получение статистики аккаунта по дням;
- возврат результатов в виде `pandas.DataFrame`.

Основной файл: `Avito_Api.py`.

## Установка зависимостей

Минимально нужны:

```bash
pip install requests pandas sqlalchemy psycopg2-binary
```

Если устанавливать пакет из текущей папки:

```bash
pip install .
```

## Быстрый старт

```python
from Avito_Api import Avito_API

avito = Avito_API(
    client_id='your_client_id',
    client_secret='your_client_secret',
    user_id='your_user_id',
)

# Получить токен
access_token = avito.get_token()

# Получить список объявлений
df_ads = avito.get_ad_list()

# Получить статистику по объявлениям
df_ad_stat = avito.get_ad_stat(
    dateFrom='2026-05-01',
    dateTo='2026-05-07',
    metrics=['views'],
)

# Получить статистику аккаунта в разрезе объявлений и дней
df_account_stat = avito.get_stats_accounts(
    dateFrom='2026-05-01',
    dateTo='2026-05-07',
    metrics=['views', 'contacts', 'presenceSpending'],
)
```

## Инициализация класса

```python
avito = Avito_API(
    client_id=None,
    client_secret=None,
    user_id=None,
    access_token=None,
    timeout=(5, 60),
    max_retries=5,
    retry_sleep=10,
    item_ids_chunk_size=200,
    account_stats_limit=1000,
    session=None,
)
```

### Параметры

`client_id`

ID приложения Avito. Используется для получения access token.

`client_secret`

Секрет приложения Avito. Используется для получения access token.

`user_id`

ID пользователя/аккаунта Avito. Используется в URL статистики.

`access_token`

Готовый access token. Если передать его сразу, класс не будет получать токен до тех пор, пока API не вернет ошибку авторизации.

`timeout`

Таймаут для HTTP-запросов. По умолчанию `(5, 60)`, где `5` секунд на подключение и `60` секунд на чтение ответа.

`max_retries`

Максимальное количество повторов запроса при сетевых ошибках, лимите запросов `429` и серверных ошибках `5xx`.

`retry_sleep`

Базовая задержка между повторами в секундах. На каждой следующей попытке задержка увеличивается: `retry_sleep * номер_попытки`.

`item_ids_chunk_size`

Размер блока объявлений для метода `get_ad_stat()`. По умолчанию `200`, чтобы не отправлять слишком много `itemIds` одним запросом.

`account_stats_limit`

Размер страницы для статистики аккаунта в `get_stats_accounts()`. По умолчанию `1000`.

`session`

Опциональный объект `requests.Session` или совместимый объект. Обычно не нужен. Полезен для тестов или кастомной настройки HTTP-сессии.

## Публичные методы

## `get_token()`

Получает access token через Avito OAuth `client_credentials`.

### Что принимает

Метод не принимает аргументы. Использует значения, переданные в конструктор:

- `client_id`;
- `client_secret`.

### Что делает

Отправляет `POST`-запрос на:

```text
https://api.avito.ru/token/
```

С payload:

```python
{
    'grant_type': 'client_credentials',
    'client_id': self.client_id,
    'client_secret': self.client_secret,
}
```

Если токен получен успешно, сохраняет его в:

```python
self.access_token
```

### Что возвращает

Возвращает строку `access_token`.

Если токен получить не удалось, возвращает `None`.

### Пример

```python
token = avito.get_token()

if token:
    print('Токен получен')
else:
    print('Не удалось получить токен')
```

## `get_ad_list()`

Получает список объявлений аккаунта.

### Что принимает

Метод не принимает аргументы.

### Что делает

Если `self.access_token` пустой, сначала вызывает:

```python
self.get_token()
```

Затем постранично запрашивает объявления через:

```text
https://api.avito.ru/core/v1/items
```

Метод идет по страницам, начиная с `page=1`, пока Avito возвращает непустой список `resources`.

Все объявления складываются в:

```python
self.all_items_ad
```

И преобразуются в DataFrame:

```python
self.df_ad
```

### Что возвращает

Возвращает `pandas.DataFrame` со списком объявлений.

Если токен получить не удалось или API вернул ошибку, возвращает пустой `DataFrame` либо `DataFrame` с теми данными, которые успели загрузиться до ошибки.

### Пример

```python
df_ads = avito.get_ad_list()

print(df_ads.head())
print(df_ads.columns)
```

## `get_ad_stat(dateFrom=None, dateTo=None, metrics=None)`

Получает статистику по объявлениям за период.

### Что принимает

`dateFrom`

Дата начала периода в формате `YYYY-MM-DD`.

Пример:

```python
'2026-05-01'
```

`dateTo`

Дата окончания периода в формате `YYYY-MM-DD`.

Пример:

```python
'2026-05-07'
```

`metrics`

Список метрик, которые нужно запросить. Если не передать, используется:

```python
['views']
```

Можно передать строку:

```python
metrics='views'
```

Или список:

```python
metrics=['views', 'uniqViews']
```

### Что делает

1. Проверяет даты `dateFrom` и `dateTo`.
2. Получает список объявлений через `get_ad_list()`.
3. Берет уникальные ID объявлений из колонки `id`.
4. Делит список ID на чанки по `item_ids_chunk_size`, по умолчанию по `200` объявлений.
5. Для каждого чанка отправляет запрос статистики на:

```text
https://api.avito.ru/stats/v1/accounts/{user_id}/items
```

6. Собирает результат в:

```python
self.df_ad_stat
```

Также сырые ответы Avito сохраняются в:

```python
self.ad_stat
```

### Что возвращает

Возвращает `pandas.DataFrame` со статистикой объявлений.

Обычно в результате есть:

- `itemId`;
- `date`;
- колонки с запрошенными метриками.

Если по объявлению нет статистики, метод добавляет строку с `date=None` и нулевыми значениями для запрошенных метрик.

Если возникла ошибка или нет объявлений, возвращает пустой `DataFrame`.

### Пример

```python
df_stat = avito.get_ad_stat(
    dateFrom='2026-05-01',
    dateTo='2026-05-07',
    metrics=['views'],
)

print(df_stat.head())
```

### Зачем нужны чанки `itemIds`

Не стоит отправлять тысячи ID объявлений одним запросом. Поэтому метод режет список:

```python
[1, 2, 3, 4, 5]
```

При `item_ids_chunk_size=2` получится:

```python
[1, 2]
[3, 4]
[5]
```

Так запросы становятся стабильнее.

## `get_stats_accounts(dateFrom=None, dateTo=None, metrics=None)`

Получает статистику аккаунта в разрезе каждого объявления и каждого дня.

Это основной метод, если тебе нужно сохранить обе колонки:

- `item_id`;
- `date`.

### Почему метод ходит по каждому дню

Endpoint статистики аккаунта принимает только одно значение `grouping` за один запрос.

Если поставить:

```python
'grouping': 'day'
```

то Avito вернет строки по датам, но без `item_id`.

Если поставить:

```python
'grouping': 'item'
```

то Avito вернет строки по объявлениям, но показатели будут суммарно за весь период без дневной разбивки.

Поэтому для результата `item_id + date` метод делает запрос отдельно за каждый день с:

```python
'grouping': 'item'
```

и сам добавляет колонку `date` в каждую строку.

### Что принимает

`dateFrom`

Дата начала периода в формате `YYYY-MM-DD`.

`dateTo`

Дата окончания периода в формате `YYYY-MM-DD`.

`metrics`

Список метрик. Если не передать, используется:

```python
['views', 'contacts', 'presenceSpending']
```

### Что делает

1. Проверяет диапазон дат.
2. Проходит по каждому дню периода.
3. Для каждого дня запрашивает данные с `grouping='item'`.
4. Использует `limit` и `offset`, если за день больше строк, чем `account_stats_limit`.
5. Добавляет в каждую строку дату текущего дня.
6. Собирает результат в:

```python
self.data_stats_accounts
```

### Что возвращает

Возвращает `pandas.DataFrame` со строками вида:

- `item_id`;
- `date`;
- запрошенные метрики.

### Пример

```python
df_item_day = avito.get_stats_accounts(
    dateFrom='2026-05-01',
    dateTo='2026-05-07',
    metrics=['views', 'contacts', 'presenceSpending'],
)

print(df_item_day.head())
```

## Запись в PostgreSQL

Для записи полученного `DataFrame` в PostgreSQL добавлен отдельный модуль `to_postgresql.py` и класс `ToPostgreSQL`.

Логика специально вынесена отдельно от `Avito_API`:

- `Avito_API` получает данные из Avito;
- `ToPostgreSQL` записывает готовый `DataFrame` в PostgreSQL.

### Импорт

```python
from to_postgresql import ToPostgreSQL
```

### Инициализация

```python
pg = ToPostgreSQL(
    host='localhost',
    port=5432,
    user='postgres',
    password='postgres',
    database='postgres',
    schema='avito',
)
```

### Параметры

`host`

Адрес PostgreSQL-сервера.

`port`

Порт PostgreSQL. Обычно `5432`.

`user`

Имя пользователя PostgreSQL.

`password`

Пароль пользователя PostgreSQL.

`database`

Название базы данных.

`schema`

Название схемы, в которую будут создаваться таблицы.

`connect_timeout`

Таймаут подключения к PostgreSQL. По умолчанию `30` секунд.

`pool_recycle`

Время жизни соединения в пуле SQLAlchemy. По умолчанию `1800` секунд.

`batch_page_size`

Размер пачки для batch insert. По умолчанию `500`.

## `create_table(table_name=None, data=None)`

Создает схему и таблицу, если они еще не существуют.

### Что принимает

`table_name`

Название таблицы.

`data`

`pandas.DataFrame`, по колонкам которого будет создана таблица.

### Что делает

- проверяет, что `data` не пустой;
- проверяет, что в `data` есть колонка `date`;
- создает schema через `CREATE SCHEMA IF NOT EXISTS`;
- создает таблицу через `CREATE TABLE IF NOT EXISTS`;
- колонку `date` создает как `DATE`;
- остальные колонки создает как `TEXT`.

### Что возвращает

Возвращает `True`, если таблица успешно создана или уже существовала.

### Пример

```python
pg.create_table(table_name='account_stats', data=df_account_stat)
```

## `insert_into_table(table_name=None, data=None)`

Записывает данные в таблицу PostgreSQL.

### Что принимает

`table_name`

Название таблицы.

`data`

`pandas.DataFrame` с колонкой `date`.

### Что делает

1. Копирует `DataFrame`, чтобы не менять исходные данные.
2. Преобразует колонку `date` к типу даты.
3. Определяет минимальную и максимальную дату в данных.
4. Удаляет из таблицы старые строки за этот диапазон дат.
5. Вставляет новые строки пачкой.

Такой подход удобен для регулярной перезаливки статистики: можно заново загрузить период, и в таблице не будет дублей за эти даты.

### Что возвращает

Возвращает `True`, если запись прошла успешно.

### Пример

```python
pg.insert_into_table(table_name='account_stats', data=df_account_stat)
```

### Полный пример Avito -> PostgreSQL

```python
from Avito_Api import Avito_API
from to_postgresql import ToPostgreSQL

avito = Avito_API(
    client_id='your_client_id',
    client_secret='your_client_secret',
    user_id='your_user_id',
)

df_account_stat = avito.get_stats_accounts(
    dateFrom='2026-05-01',
    dateTo='2026-05-07',
    metrics=['views', 'contacts', 'presenceSpending'],
)

pg = ToPostgreSQL(
    host='localhost',
    port=5432,
    user='postgres',
    password='postgres',
    database='postgres',
    schema='avito',
)

pg.create_table(table_name='account_stats', data=df_account_stat)
pg.insert_into_table(table_name='account_stats', data=df_account_stat)
```

## Внутренние методы

Методы ниже начинаются с `_`, поэтому считаются внутренними. Обычно их не нужно вызывать напрямую.

## `_request_json(method, url, retry_auth=True, **kwargs)`

Единая точка для HTTP-запросов.

### Что делает

- добавляет `timeout`, если он не передан;
- выполняет запрос через `requests.Session`;
- парсит JSON;
- повторяет запрос при сетевых ошибках;
- повторяет запрос при `429 Too Many Requests`;
- повторяет запрос при ошибках Avito `500`, `502`, `503`, `504`;
- при ошибке авторизации `401/403` пытается обновить токен и повторить запрос один раз.

### Что возвращает

Возвращает `dict` с JSON-ответом Avito или `None` при ошибке.

## `_auth_headers()`

Возвращает headers с авторизацией:

```python
{'Authorization': f'Bearer {self.access_token}'}
```

Если токена нет, сначала вызывает `get_token()`.

## `_json_headers()`

Возвращает headers для JSON-запросов:

```python
{
    'Authorization': f'Bearer {self.access_token}',
    'Content-Type': 'application/json',
}
```

## `_chunks(items, chunk_size)`

`@staticmethod`, который режет список на части.

Пример:

```python
list(Avito_API._chunks([1, 2, 3, 4, 5], 2))
```

Результат:

```python
[[1, 2], [3, 4], [5]]
```

## `_parse_date(date_value, field_name)`

`@staticmethod`, который проверяет дату и превращает строку формата `YYYY-MM-DD` в объект `datetime`.

## `_validate_date_range(date_from, date_to)`

Проверяет, что обе даты переданы и что `dateTo` не раньше `dateFrom`.

## `_normalize_metrics(metrics, default_metrics)`

`@staticmethod`, который приводит метрики к списку.

Примеры:

```python
None -> default_metrics
'views' -> ['views']
['views', 'contacts'] -> ['views', 'contacts']
```

## Атрибуты с результатами

После вызова методов класс сохраняет результаты в атрибуты:

`self.access_token`

Текущий access token.

`self.all_items_ad`

Список объявлений в виде списка словарей.

`self.df_ad`

DataFrame со списком объявлений.

`self.ad_stat`

Сырые JSON-ответы статистики объявлений.

`self.df_ad_stat`

DataFrame со статистикой объявлений.

`self.data_stats_accounts`

DataFrame со статистикой аккаунта в разрезе каждого объявления и каждого дня.

## Обработка ошибок

Класс не бросает исключения наружу в обычных API-методах. При ошибке он печатает сообщение и возвращает:

- `None` для `get_token()`;
- пустой `DataFrame` или частично собранный `DataFrame` для методов статистики.

Типичные ошибки:

- не удалось получить токен;
- Avito вернул не JSON;
- лимит запросов `429`;
- ошибка авторизации `401/403`;
- серверная ошибка Avito `5xx`;
- неверный формат дат.

## Пример полного сценария

```python
from Avito_Api import Avito_API

avito = Avito_API(
    client_id='your_client_id',
    client_secret='your_client_secret',
    user_id='your_user_id',
    item_ids_chunk_size=200,
    account_stats_limit=1000,
)

ads = avito.get_ad_list()
print('Объявлений:', len(ads))

ad_stats = avito.get_ad_stat(
    dateFrom='2026-05-01',
    dateTo='2026-05-07',
    metrics=['views'],
)
print(ad_stats.head())

account_stats = avito.get_stats_accounts(
    dateFrom='2026-05-01',
    dateTo='2026-05-07',
    metrics=['views', 'contacts', 'presenceSpending'],
)
print(account_stats.head())
```

## Важные замечания

- Не храните `client_secret` прямо в публичном репозитории.
- Для реальной работы нужны доступы Avito API и корректный `user_id`.
- Названия доступных метрик зависят от конкретного метода Avito API и прав приложения.
- Если данных много, увеличивать `item_ids_chunk_size` и `account_stats_limit` стоит осторожно.
