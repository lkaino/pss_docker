import os
from typing import Optional
from pss_login import Device, _create_device_key
import cloudpickle as pickle
import asyncio
import pandas as pd
import requests
import logging as log
import time


class PSSApi:
    BASE_URL = "https://api.pixelstarships.com/"

    def __init__(self, data_path):
        self._data_path = data_path
        self._token = None

    async def setup(self):
        self._token = await self._get_token()

    async def _get_token(self):
        filename = os.path.join(self._data_path, "dev.pickle")
        if os.path.exists(filename):
            with open(filename, "rb") as infile:
                _token = pickle.load(infile)
        else:
            dev = Device(_create_device_key())
            _token = await dev.get_access_token()
            with open(filename, "wb") as outfile:
                pickle.dump(_token, outfile)

        return _token

    def get_items(self, _token=None) -> pd.DataFrame:
        log.info(f"Getting sales for id {id}")
        df: pd.DataFrame = None
        params = {
            'accessToken': self._token,
        }
        try:
            response = requests.get(self.BASE_URL + "ItemService/ListItemDesigns2", params=params)
        except Exception as e:
            return df

        try:
            df = pd.read_xml(response.text, xpath="/ItemService/ListItemDesigns/ItemDesigns//ItemDesign")
        except Exception as e:
            print(f"ERROR: {e}: {response.text}")

        return df

    async def get_sales_for_design_id(self, design_id: int, past_days=2, max_count=100) -> pd.DataFrame:
        start = 0
        end = 20

        df: pd.DataFrame = None
        while True:
            params = {
                'itemDesignId': design_id,
                'saleStatus': 'Sold',
                'from': start,
                'to': end,
                'accessToken': self._token,
            }
            response = requests.get(self.BASE_URL + "/MarketService/ListSalesByItemDesignId", params=params)
            try:
                df_new = pd.read_xml(response.text, xpath="/MarketService/ListSalesByItemDesignId/Sales//Sale",
                                     parse_dates=["StatusDate"])
            except Exception as e:
                if "Too many" in response.text:
                    log.info(f"Got too many response while getting sales for {design_id}")
                    await asyncio.sleep(10)
                    continue
                log.error(f"ERROR: {response.text}")
                return df
            len_all = len(df_new)
            df_new = df_new[df_new["CurrencyType"] == "Starbux"]
            df_new["SinglePrice"] = df_new["CurrencyValue"] / df_new["Quantity"]
            if len_all > 0:
                if df is None:
                    df = df_new
                else:
                    df = pd.concat([df, df_new], ignore_index=True)
            else:
                break
            start += 20
            end += 20
            if pd.Timestamp.now() - df.min()["StatusDate"] > pd.Timedelta(days=past_days):
                break
            if len(df) > max_count:
                break
            await asyncio.sleep(2)
        return df

    def get_market_messages(self, design_id: Optional[int], count=999999) -> pd.DataFrame:

        log.debug(f"Getting market for id {design_id}")

        df: pd.DataFrame = None
        params = {
            'currencyType': 'Unknown',
            'itemSubType': 'None',
            'rarity': 'None',
            'userId': 0,
            'skip': 0,
            'take': count,
            'accessToken': self._token,
        }
        if design_id:
            params['itemDesignId'] = design_id
        log.debug(params)
        try:
            response = requests.get(self.BASE_URL + "/MessageService/ListActiveMarketplaceMessages5", params=params)
        except Exception as e:
            print(e)
            return df

        try:
            log.debug(f"RESPONSE {response.text}")
            df = pd.read_xml(response.text, xpath="/MessageService/ListActiveMarketplaceMessages/Messages//Message",
                             parse_dates=["MessageDate"])
        except Exception as e:
            if "Too many" in response.text:
                time.sleep(10)
        return df