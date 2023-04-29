from typing import List, Optional
from items import Items
from pss_api import PSSApi
from characters import Characters
import re
from telegram_bot import TelegramBot
import time
import logging as log
import asyncio
import os
import cloudpickle as pickle
import pandas as pd
import datetime

class FleetListener:
    def __init__(self, api: PSSApi, characters: Characters, items: Items, data_path: str):
        self._interest_crew = {}
        self._api = api
        self._characters = characters
        self._items = items
        self._last_sale_id: int = 0
        self._telegram: Optional[TelegramBot] = None
        self._data_path = data_path
        self._alliance_id: Optional[int] = self._load_alliance_id()
        self._load_interest_crew()
        self._crew_df: Optional[pd.DataFrame] = None
        self._telegram: Optional[TelegramBot] = None

    def remove_interest_crew(self, stat: str):
        if stat in self._interest_crew:
            del self._interest_crew[stat]
            self.store_interest_crew()
            return True
        else:
            return False

    def set_telegram(self, telegram: TelegramBot):
        self._telegram = telegram

    def add_interest_crew(self, stat: str, amount: int):
        self._interest_crew[stat] = amount
        self.store_interest_crew()

    def store_interest_crew(self):
        filename = os.path.join(
            self._data_path, "fleet", "interest_crew.pickle")
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as outfile:
            pickle.dump(self._interest_crew, outfile)

    def _load_interest_crew(self):
        filename = os.path.join(
            self._data_path, "fleet", "interest_crew.pickle")
        if os.path.exists(filename):
            with open(filename, "rb") as infile:
                self._interest_crew = pickle.load(infile)

    def _store_alliance_id(self):
        filename = os.path.join(self._data_path, "fleet", "alliance_id.pickle")
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as outfile:
            pickle.dump(self._alliance_id, outfile)

    def _load_alliance_id(self) -> Optional[int]:
        filename = os.path.join(
            self._data_path, "fleet", "alliance_id.pickle")
        if os.path.exists(filename):
            with open(filename, "rb") as infile:
                return pickle.load(infile)
        return None

    async def set_fleet(self, name: str) -> bool:
        all = await self._api.get_alliances()
        fleet = all[all["AllianceName"] == name]
        if len(fleet) == 1:
            self._alliance_id = fleet.iloc[0]["AllianceId"]
            self._store_alliance_id()
            return True
        else:
            return False

    async def _do_check(self, df: Optional[pd.DataFrame]):
        if df is None:
            df = await self._api.get_available_donated_crew_for_fleet(self._alliance_id)
        if df is not None and len(df) > 0:
            for index, row in df.iterrows():
                id = row.CharacterDesignId
                level = row.Level
                name = row.CharacterName
                for stat, value in self._interest_crew.items():
                    crew_stat_value = self._characters.get_stat_at_level(character_id=id, level=level, stat=stat)
                    improvement = row[f"{stat}Improvement"]
                    crew_stat_value = crew_stat_value * ((100 + improvement) / 100)
                    if isinstance(row.ItemDesignIDs, str):
                        ids = row.ItemDesignIDs.split(',')
                        for item_id in ids:
                            item_id = int(item_id)
                            enc_type, enc_value = self._items.get_enhancement(item_id)
                            if enc_type == stat:
                                crew_stat_value += enc_value
                        bonus_stats = row.ItemBonusStats.split(',')
                        bonus_vals = row.ItemBonusVals.split(',')
                        index = 0
                        for bonus_stat in bonus_stats:
                            if bonus_stat == stat:
                                crew_stat_value += float(bonus_vals[index])
                            index += 1
                    if crew_stat_value > value:
                        yield f'<i>crew available</i> - <b>{name}</b> - <b>{row.OwnerUsername}</b> - {stat} {int(crew_stat_value)}'

    async def get_current_messages(self) -> str:
        async for message in self._do_check(self._crew_df):
            yield message

    async def run(self):
        while True:
            interest_crew = self._interest_crew.copy()
            if len(interest_crew) == 0 or self._alliance_id is None:
                await asyncio.sleep(2)
                continue

            df = await self._api.get_available_donated_crew_for_fleet(self._alliance_id)
            if self._crew_df is not None:
                merged = df.merge(self._crew_df, how='left', indicator=True)
                new = df[merged['_merge'] == 'right_only']
            else:
                new = df

            async for message in self._do_check(new):
                await self._telegram.send_message(message)
            self._crew_df = df

            await asyncio.sleep(5)