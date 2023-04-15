from typing import List, Optional
from items import Items
from pss_api import PSSApi
import re
from telegram_bot import TelegramBot
import time
import logging as log
import asyncio
import os
import cloudpickle as pickle
import pandas as pd
import datetime


class MarketMessage:
    def __init__(self, row: pd.DataFrame):
        self.message_id = row["MessageId"]
        self.message = row["Message"]
        arguments = row["Argument"].split("x")
        self.design_id = int(arguments[0].split(":")[1])
        self.count = int(arguments[1])
        self.sale_id = row["SaleId"]
        self.currency = row["ActivityArgument"].split(":")[0]
        self.amount = int(int(row["ActivityArgument"].split(":")[1]) / self.count)
        if "(" in self.message:
            stat_val = re.search("\(.*\)", self.message).group().split(" ")
            try:
                self.stat_amount = float(re.findall(r'(?:\d*\.*\d+)', stat_val[0])[0])
                self.stat_name = stat_val[1][:-1]
            except IndexError:
                self.stat_amount = None
                self.stat_name = None
        else:
            self.stat_amount = None
            self.stat_name = None


class MarketListener:
    STAT_MAX = {
        "Weapon": 6.7,
        "Ability": 15.7,
        "Science": 9.7,
        "Hp": 3.0,
        "Stamina": 25,
        "Attack": 0.7,
        "FireResistance": 56.2,
        "Engine": 6.7,
        "Pilot": 10.5,
        "Repair": 10.5,
    }

    STAT_SHORT = {
        "Weapon": "WPN",
        "Ability": "ABL",
        "Science": "SCI",
        "Hp": "HP",
        "Stamina": "STA",
        "Attack": "ATK",
        "FireResistance": "RST",
        "Engine": "ENG",
        "Pilot": "PLT",
        "Repair": "RPR",
    }

    def __init__(self, api: PSSApi, items: Items, data_path: str):
        self._interest_items = {}
        self._api = api
        self._items = items
        self._last_sale_id: int = 0
        self._telegram: Optional[TelegramBot] = None
        self._data_path = data_path
        self._load_interest_items()

    def set_telegram(self, telegram: TelegramBot):
        self._telegram = telegram

    def list(self):
        return self._interest_items

    def get_stat_keys(self):
        return self.STAT_MAX.keys()

    async def add_interest_items(self, name: str, stats: List[str]):
        try:
            for stat in stats:
                if stat not in self.STAT_MAX:
                    raise Exception(f"Uknown stat {stat} for {name}, possible options: {self.STAT_MAX.keys()}!")
            design_id = self._items.get_design_id_by_name(name)

            sales = await self._api.get_sales_for_design_id(design_id, past_days=10)
            mean = sales["SinglePrice"].mean()
            std = sales["SinglePrice"].std()
            mean_price = sales[(sales["SinglePrice"] > mean - std) & (sales["SinglePrice"] < mean + std)].mean(numeric_only=True)["SinglePrice"]
            self._interest_items[design_id] = {"stats": stats}
            self.update_interest_item_price(design_id)
            self.store_interest_items()
        except Exception as e:
            log.error(e)


    def update_interest_item_price(self, design_id: int):
        item = self._interest_items[design_id]
        now = datetime.datetime.now()
        if "last_price_update" not in item or now - item["last_price_update"] > datetime.timedelta(hours=1):
            sales = self._api.get_sales_for_design_id(design_id, past_days=10)
            mean = sales["SinglePrice"].mean()
            std = sales["SinglePrice"].std()
            mean_price = sales[(sales["SinglePrice"] > mean - std) & (sales["SinglePrice"] < mean + std)].mean(numeric_only=True)["SinglePrice"]
            item["mean_price"] = mean_price
            item["last_price_update"] = now

    def remove_interest_items(self, name: str):
        design_id = self._items.get_design_id_by_name(name)
        if design_id in self._interest_items:
            del self._interest_items[design_id]
            self.store_interest_items()
            return True
        else:
            return False

    def store_interest_items(self):
        filename = os.path.join(self._data_path, "market", "interest_items.pickle")
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as outfile:
            pickle.dump(self._interest_items, outfile)

    def _load_interest_items(self):
        filename = os.path.join(self._data_path, "market", "interest_items.pickle")
        if os.path.exists(filename):
            with open(filename, "rb") as infile:
                self._interest_items = pickle.load(infile)

    async def run(self):
        first = True
        while True:
            if first:
                count = 999999
                first = False
            else:
                count = 20
            interest_items = self._interest_items.copy()
            df = self._api.get_market_messages(design_id=None, count=count)
            if df is not None:
                df = df[df["SaleId"] > self._last_sale_id]
                for index, row in df.iterrows():
                    msg = MarketMessage(row)
                    if msg.design_id in interest_items:
                        interesting = False
                        vals = interest_items[msg.design_id]
                        can_have_substats = self._items.item_can_have_substats(msg.design_id)
                        if can_have_substats:
                            for stat in vals["stats"]:
                                if stat in msg:
                                    interesting = True
                        else:
                            interesting = True

                        if interesting:
                            self.update_interest_item_price(msg.design_id)
                            market_price = interest_items[msg.design_id]["mean_price"]
                            if can_have_substats:
                                stat_percentage = 1 + msg.stat_amount / self.STAT_MAX[msg.stat_name]
                                cheap_price = market_price + \
                                            market_price / 2 * stat_percentage + \
                                            market_price / 6 * pow(stat_percentage, 2)
                                ok_price = market_price + \
                                        market_price * stat_percentage + \
                                        market_price * pow(stat_percentage, 2)
                            else:
                                cheap_price = market_price * 0.9
                                ok_price = market_price * 1.1
                            icon = ""
                            if msg.currency == "starbux":
                                bux = True
                                if msg.amount < cheap_price:
                                    icon = '\U0001F7E2'
                                    price_comment = "Cheap"
                                elif msg.amount < ok_price:
                                    icon = '\U0001F7E1'
                                    price_comment = "OK"
                                else:
                                    icon = '\U0001F534'
                                    price_comment = "Expensive"
                            else:
                                bux = False
                                price_comment = "Cheap"
                                icon = '\U0001F7E2'

                            if can_have_substats or (not can_have_substats and price_comment != "Expensive"): 
                                name = self._items.get_name_by_design_id(msg.design_id)
                                message = f'{icon} <b>{name}</b> - '
                                if can_have_substats:
                                    message += f'{msg.stat_amount} {self.STAT_SHORT[msg.stat_name]} - '
                                message += f'{msg.amount} '
                                if not bux:
                                    message += f'{msg.currency} '
                                message += f'- <a href="https://pixyship.com/item/{msg.design_id}">pixyship</a>'
                                await self._telegram.send_message(message, html=False)
                                log.info(message)
                    self._last_sale_id = max(self._last_sale_id, msg.sale_id)
            await asyncio.sleep(2)
