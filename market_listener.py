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

    def __init__(self, api: PSSApi, items: Items, data_path: str):
        self._interest_items = {}
        self._api = api
        self._items = items
        self._known_sale_ids: List[int] = []
        self._telegram: Optional[TelegramBot] = None
        self._data_path = data_path
        self._load_interest_items()

    def set_telegram(self, telegram: TelegramBot):
        self._telegram = telegram

    def list(self):
        return self._interest_items

    def get_stat_keys(self):
        return self.STAT_MAX.keys()

    def add_interest_items(self, name: str, stats: List[str]):
        for stat in stats:
            if stat not in self.STAT_MAX:
                raise Exception(f"Uknown stat {stat} for {name}, possible options: {self.STAT_MAX.keys()}!")
        design_id = self._items.get_design_id_by_name(name)

        sales = self._api.get_sales_for_design_id(design_id, past_days=10)
        mean = sales["SinglePrice"].mean()
        std = sales["SinglePrice"].std()
        mean_price = sales[(sales["SinglePrice"] > mean - std) & (sales["SinglePrice"] < mean + std)].mean(numeric_only=True)["SinglePrice"]
        self._interest_items[design_id] = {"stats": stats, "mean_price": mean_price}
        self.store_interest_items()

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
        pass

    async def run(self):
        while True:
            interest_items = self._interest_items.copy()
            for design_id, vals in interest_items.items():
                df = self._api.get_market_messages(design_id)
                if df is not None:
                    for index, row in df.iterrows():
                        sale_id = row["SaleId"]
                        msg = row["Message"]

                        currency = row["ActivityArgument"].split(":")[0]
                        amount = float(row["ActivityArgument"].split(":")[1])
                        interesting = False
                        for stat in vals["stats"]:
                            if stat in msg:
                                interesting = True

                        if interesting and sale_id not in self._known_sale_ids:
                            stat_val = re.search("\(.*\)", msg).group().split(" ")
                            stat_amount = float(re.findall(r'(?:\d*\.*\d+)', stat_val[0])[0])
                            stat_name = stat_val[1][:-1]
                            stat_max = self.STAT_MAX[stat_name]
                            stat_percentage = 1 + stat_amount / stat_max
                            market_price = vals["mean_price"]
                            # cheap_price = market_price + market_price * stat_percentage * 3
                            # ok_price = cheap_price + market_price * stat_percentage * 4
                            cheap_price = market_price + \
                                          market_price / 2 * stat_percentage + \
                                          market_price / 6 * pow(stat_percentage, 2)
                            ok_price = market_price + \
                                       market_price * stat_percentage + \
                                       market_price * pow(stat_percentage, 2)
                            if currency == "starbux":
                                if amount < cheap_price:
                                    price_comment = "cheap"
                                elif amount < ok_price:
                                    price_comment = "OK"
                                else:
                                    price_comment = "expensive"
                            else:
                                price_comment = "not starbux"
                            name = self._items.get_name_by_design_id(design_id)
                            message = f"Found {name} {stat_amount} {stat_name} for {amount} {currency}. " \
                                      f"The price is {price_comment} (market {int(market_price)}/ cheap" \
                                      f" {int(cheap_price)}/ ok {int(ok_price)})"
                            await self._telegram.send_message(message)
                            log.info(message)
                        self._known_sale_ids.append(sale_id)
                await asyncio.sleep(1)
            await asyncio.sleep(15)
