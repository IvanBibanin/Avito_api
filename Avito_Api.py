from datetime import datetime, timedelta
import time

import pandas as pd
import requests


class Avito_API:
    BASE_URL = 'https://api.avito.ru'
    DEFAULT_TIMEOUT = (5, 60)
    DEFAULT_MAX_RETRIES = 5
    DEFAULT_RETRY_SLEEP = 10
    DEFAULT_ITEM_IDS_CHUNK_SIZE = 200
    DEFAULT_ACCOUNT_STATS_LIMIT = 1000
    DEFAULT_AD_STAT_METRICS = ['views']
    DEFAULT_ACCOUNT_METRICS = ['views', 'contacts', 'presenceSpending']

    def __init__(
        self,
        client_id=None,
        client_secret=None,
        user_id=None,
        access_token=None,
        timeout=DEFAULT_TIMEOUT,
        max_retries=DEFAULT_MAX_RETRIES,
        retry_sleep=DEFAULT_RETRY_SLEEP,
        item_ids_chunk_size=DEFAULT_ITEM_IDS_CHUNK_SIZE,
        account_stats_limit=DEFAULT_ACCOUNT_STATS_LIMIT,
        session=None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_id = user_id
        self.access_token = access_token
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_sleep = retry_sleep
        self.item_ids_chunk_size = item_ids_chunk_size
        self.account_stats_limit = account_stats_limit
        self.session = session or requests.Session()

        self.url_get_token = f'{self.BASE_URL}/token/'
        self.url_ad_list = f'{self.BASE_URL}/core/v1/items'
        self.url_get_accounts = f'{self.BASE_URL}/stats/v2/accounts/{self.user_id}/items'
        self.url_get_ad = f'{self.BASE_URL}/stats/v1/accounts/{self.user_id}/items'

    def _auth_headers(self):
        if not self.access_token:
            token = self.get_token()
            if not token:
                return None
        return {'Authorization': f'Bearer {self.access_token}'}

    def _json_headers(self):
        headers = self._auth_headers()
        if headers is None:
            return None
        headers['Content-Type'] = 'application/json'
        return headers

    def _parse_json(self, response):
        try:
            return response.json()
        except ValueError:
            print(f'Avito вернул не JSON. STATUS:{response.status_code} BODY:{response.text}')
            return None

    def _is_token_error(self, response):
        if response.status_code not in (401, 403):
            return False
        text = (response.text or '').lower()
        token_markers = ('access token expired', 'invalid access token', 'unauthorized', 'forbidden')
        return any(marker in text for marker in token_markers)

    def _request_json(self, method, url, retry_auth=True, **kwargs):
        kwargs.setdefault('timeout', self.timeout)

        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
            except requests.RequestException:
                wait = self.retry_sleep * (attempt + 1)
                if attempt == self.max_retries - 1:
                    print('Ошибка соединения с Avito API')
                    return None
                print(f'Ошибка соединения. Повтор через {wait} сек.')
                time.sleep(wait)
                continue

            if response.status_code == 200:
                return self._parse_json(response)

            if response.status_code == 429:
                wait = self.retry_sleep * (attempt + 1)
                print(f'Лимит запросов Avito. Повтор через {wait} сек.')
                time.sleep(wait)
                continue

            if response.status_code in (500, 502, 503, 504):
                wait = self.retry_sleep * (attempt + 1)
                if attempt == self.max_retries - 1:
                    print(f'Ошибка на стороне Avito. STATUS:{response.status_code} BODY:{response.text}')
                    return None
                print(f'Ошибка Avito {response.status_code}. Повтор через {wait} сек.')
                time.sleep(wait)
                continue

            if retry_auth and self._is_token_error(response):
                print(f'Ошибка авторизации ({response.status_code}). Обновляем токен...')
                token = self.get_token()
                if not token:
                    return None
                headers = kwargs.get('headers') or {}
                headers['Authorization'] = f'Bearer {self.access_token}'
                kwargs['headers'] = headers
                retry_auth = False
                continue

            print(f'Ошибка Avito API. STATUS:{response.status_code} BODY:{response.text}')
            return None

        return None

    @staticmethod
    def _chunks(items, chunk_size):
        for start in range(0, len(items), chunk_size):
            yield items[start:start + chunk_size]

    @staticmethod
    def _parse_date(date_value, field_name):
        if not date_value:
            raise ValueError(f'{field_name} обязателен в формате YYYY-MM-DD')
        return datetime.strptime(date_value, '%Y-%m-%d')

    def _validate_date_range(self, date_from, date_to):
        start_date = self._parse_date(date_from, 'dateFrom')
        end_date = self._parse_date(date_to, 'dateTo')
        if end_date < start_date:
            raise ValueError('dateTo не может быть раньше dateFrom')
        return start_date, end_date

    @staticmethod
    def _normalize_metrics(metrics, default_metrics):
        if metrics is None:
            return list(default_metrics)
        if isinstance(metrics, str):
            return [metrics]
        return list(metrics)

    def get_token(self):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        data = self._request_json(
            'POST',
            self.url_get_token,
            data=payload,
            headers=headers,
            retry_auth=False,
        )
        if not data or 'access_token' not in data:
            print('Не удалось получить access_token')
            return None

        self.access_token = data['access_token']
        return self.access_token

    def get_ad_list(self):
        """Получаем список объявлений и описание."""
        headers = self._auth_headers()
        if headers is None:
            self.all_items_ad = []
            self.df_ad = pd.DataFrame()
            return self.df_ad

        self.all_items_ad = []
        page = 1

        while True:
            data = self._request_json(
                'GET',
                self.url_ad_list,
                headers=headers,
                params={'page': page},
            )
            if data is None:
                break

            resources = data.get('resources', [])
            print(f'Page {page}, items {len(resources)}')
            if not resources:
                break

            self.all_items_ad.extend(resources)
            page += 1

        self.df_ad = pd.DataFrame(self.all_items_ad)
        return self.df_ad

    def get_ad_stat(self, dateFrom=None, dateTo=None, metrics=None):
        """Получаем статистику по списку объявлений и возвращаем DataFrame."""
        metrics = self._normalize_metrics(metrics, self.DEFAULT_AD_STAT_METRICS)
        headers = self._json_headers()
        if headers is None:
            self.df_ad_stat = pd.DataFrame()
            return self.df_ad_stat
        try:
            self._validate_date_range(dateFrom, dateTo)
        except ValueError as error:
            print(error)
            self.df_ad_stat = pd.DataFrame()
            return self.df_ad_stat

        ad_list = self.get_ad_list()
        if ad_list.empty or 'id' not in ad_list.columns:
            print('Список объявлений пуст или не содержит колонку id')
            self.df_ad_stat = pd.DataFrame()
            return self.df_ad_stat
        headers = self._json_headers()
        if headers is None:
            self.df_ad_stat = pd.DataFrame()
            return self.df_ad_stat

        item_ids = ad_list['id'].dropna().unique().tolist()
        rows = []
        self.ad_stat = []

        for item_ids_chunk in self._chunks(item_ids, self.item_ids_chunk_size):
            payload = {
                'dateFrom': dateFrom,
                'dateTo': dateTo,
                'fields': metrics,
                'itemIds': item_ids_chunk,
                'periodGrouping': 'day',
            }
            data = self._request_json('POST', self.url_get_ad, json=payload, headers=headers)
            if data is None:
                continue

            self.ad_stat.append(data)
            items = data.get('result', {}).get('items', [])
            if not items:
                print('Avito не вернул статистику по текущему блоку itemIds')
                continue

            for item in items:
                item_id = item.get('itemId')
                stats = item.get('stats') or []
                if not stats:
                    empty_row = {'itemId': item_id, 'date': None}
                    empty_row.update({metric: 0 for metric in metrics})
                    rows.append(empty_row)
                    continue

                for stat in stats:
                    rows.append({'itemId': item_id, **stat})

        self.df_ad_stat = pd.DataFrame(rows)
        return self.df_ad_stat

    def get_stats_accounts(self, dateFrom=None, dateTo=None, metrics=None):
        metrics = self._normalize_metrics(metrics, self.DEFAULT_ACCOUNT_METRICS)
        headers = self._json_headers()
        if headers is None:
            self.data_stats_accounts = pd.DataFrame()
            return self.data_stats_accounts

        try:
            start_date, end_date = self._validate_date_range(dateFrom, dateTo)
        except ValueError as error:
            print(error)
            self.data_stats_accounts = pd.DataFrame()
            return self.data_stats_accounts

        all_rows = []
        current_date = start_date

        while current_date <= end_date:
            day = current_date.strftime('%Y-%m-%d')
            offset = 0

            while True:
                payload = {
                    'dateFrom': day,
                    'dateTo': day,
                    'limit': self.account_stats_limit,
                    'metrics': metrics,
                    'grouping': 'item',
                    'offset': offset,
                }
                data = self._request_json('POST', self.url_get_accounts, json=payload, headers=headers)
                if data is None:
                    break

                groupings = data.get('result', {}).get('groupings', [])
                print(f'Дата {day}, offset {offset}, строк {len(groupings)}')
                if not groupings:
                    break

                for item in groupings:
                    row = {'item_id': item.get('id'), 'date': day}
                    for metric in item.get('metrics', []):
                        row[metric.get('slug')] = metric.get('value')
                    all_rows.append(row)

                if len(groupings) < self.account_stats_limit:
                    break
                offset += self.account_stats_limit

            current_date += timedelta(days=1)

        self.data_stats_accounts = pd.DataFrame(all_rows)
        return self.data_stats_accounts
