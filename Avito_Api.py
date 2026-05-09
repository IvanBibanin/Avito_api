import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import pandas as pd
import time

class Avito_API():
    def __init__(self, client_id=None, client_secret=None, user_id=None, access_token=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_id = user_id
        self.url_get_token = "https://api.avito.ru/token/"
        self.url_ad_list = 'https://api.avito.ru/core/v1/items'
        self.url_get_accounts = f"https://api.avito.ru/stats/v2/accounts/{self.user_id}/items"
        self.url_get_ad = f"https://api.avito.ru/stats/v1/accounts/{self.user_id}/items"
        self.access_token = access_token
        
    def get_token(self):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
                    }
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
                }
        res = requests.post(self.url_get_token, data=payload, headers=headers)
        print(res.status_code)
        if res.status_code != 200:
            print(res.text)
            return None
        self.access_token = res.json()["access_token"]
        return self.access_token

    def get_ad_list(self):
        # Получаем список объявлений и описание
        if self.access_token is None:
            self.get_token()
    
        self.all_items_ad = []
        page = 1
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
    
        while True:
            params = {
                "page": page
            }
            res = requests.get(self.url_ad_list, headers=headers, params=params)
            print(f"Page {page},status_code {res.status_code}")
    
            if res.status_code != 200:
                print(res.text)
                break
            data = res.json().get("resources", [])
    
            if not data:
                break
    
            self.all_items_ad.extend(data)
            page += 1
            
        self.df_ad = pd.DataFrame(self.all_items_ad)
        return self.df_ad

    def get_ad_stat(self,dateFrom=None, dateTo=None, metrics=None):
        #получаем статистику по списку объявлений и возвращаем датафрейм
        if self.access_token is None:
            self.get_token()
            
        ad_list = self.get_ad_list()
        itemIds = ad_list['id'].unique().tolist()
        payload={
                "dateFrom": dateFrom,
                "dateTo": dateTo,
                "fields": [
                "views"
                ],
                "itemIds": itemIds,
                "periodGrouping": "day"
                }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        res = requests.post(self.url_get_ad,json=payload,headers=headers)
        self.ad_stat = res.json()

        rows = []
        for item in self.ad_stat['result']['items']:
            item_id = item['itemId']
            if not item['stats']:
                rows.append({
                    "itemId": item_id,
                    "date": None,
                    "views": 0,
                    "uniqViews": 0,
                    "uniqContacts": 0,
                    "uniqFavorites": 0
                })
            else:
                for stat in item['stats']:
                    row = {"itemId": item_id, **stat}
                    rows.append(row)
        
        self.df_ad_stat = pd.DataFrame(rows)
    
        return self.df_ad_stat
        
    
    
    def get_stats_accounts(self, dateFrom=None, dateTo=None, metrics=None):
        if metrics is None:
            metrics = ["views", "contacts", "presenceSpending"]
    
        if self.access_token is None:
            self.get_token()
    
        headers = {"Authorization": f"Bearer {self.access_token}","Content-Type": "application/json"}
        start_date = datetime.strptime(dateFrom, "%Y-%m-%d")
        end_date = datetime.strptime(dateTo, "%Y-%m-%d")
        current_date = start_date
        all_rows = []
    
        while current_date <= end_date:
            day = current_date.strftime("%Y-%m-%d")
            payload = {"dateFrom": day,"dateTo": day,"limit": 1000,"metrics": metrics,"grouping": "item","offset": 0}
    
            for attempt in range(5):
                res = requests.post(self.url_get_accounts,json=payload,headers=headers)
                print(f"Дата {day}, статус:", res.status_code)
    
                if res.status_code == 200:
                    data = res.json()
                    for item in data["result"]["groupings"]:
                        row = {"item_id": item["id"], "date": day}
                        for metric in item["metrics"]:
                            row[metric["slug"]] = metric["value"]
                        all_rows.append(row)
                    break

    
                if res.status_code == 429:
                    wait = 10 * (attempt + 1)
                    print(f"Лимит запросов. Ждём {wait} секунд...")
                    time.sleep(wait)
                    continue
                if res.status_code == 400:
                    print("Ошибка в параметрах запроса")
                    print(res.text)
                    return None
    
                if res.status_code in (401, 403):
                    print(f"Ошибка авторизации ({res.status_code})")
                    print(res.text)
                    need_refresh = any(["access token expired" in res.text,"invalid access token" in res.text])
                    if need_refresh:
                        print("Обновляем токен...")
                        self.get_token()
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        continue
                    return None
                    
                if res.status_code == 500:
                    print("Ошибка на стороне Avito")
                    print(res.text)
                    return None
            
            current_date += timedelta(days=1)
    
        self.data_stats_accounts = pd.DataFrame(all_rows)
        return self.data_stats_accounts