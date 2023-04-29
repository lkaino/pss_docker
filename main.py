from typing import Optional
from pss_api import PSSApi
from market_listener import MarketListener
from items import Items
from characters import Characters
from fleet_listener import FleetListener
import time
import re
import telegram_bot
import asyncio
import json
import pandas as pd
import cloudpickle as pickle
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)8.8s] %(message)s",
)
logger = logging.getLogger(__name__)


def consumables(api: PSSApi):
    output = {
        "item": [],
        "price": [],
        "mean": [],
        "count": [],
        "dna_cost": [],
        "rarity": [],
        "oldest": [],
    }

    design_ids = {
        702: {"rarity": "common",
              "name": "Military Recruit Handbook"},
        296: {"rarity": "common",
              "name": "Small Protein Shake"},
        352: {"rarity": "common",
              "name": "Drop of Brain Juice"},
        330: {"rarity": "common",
              "name": "Paracetamol"},
        359: {"rarity": "common",
              "name": "Repair Guide"},
        344: {"rarity": "common",
              "name": "Street Map"},
        297: {"rarity": "elite",
              "name": "Regular Protein Shake"},
        338: {"rarity": "elite",
              "name": "Yakitori"},
        360: {"rarity": "elite",
              "name": "New Repair Guide"},
        324: {"rarity": "elite",
              "name": "Large Cola"},
        331: {"rarity": "elite",
              "name": "Paracetamol Rapid"},
        353: {"rarity": "elite",
              "name": "Sliver of Brain Juice"},
        345: {"rarity": "elite",
              "name": "Travel Map"},
        703: {"rarity": "elite",
              "name": "Standard Combat Manual"},
        373: {"rarity": "elite",
              "name": "Obsolete Engineering Tool Kit"},
        298: {"rarity": "unique",
              "name": "Large Protein Shake"},
        354: {"rarity": "unique",
              "name": "Brew of Brain Juice"},
        332: {"rarity": "unique",
              "name": "Ibuprofen"},
        704: {"rarity": "unique",
              "name": "Galetrooper Training Manual"},
        346: {"rarity": "unique",
              "name": "World Map"},
        339: {"rarity": "unique",
              "name": "Double Yakitori"},
        361: {"rarity": "unique",
              "name": "Advanced Repair Guide"},
        325: {"rarity": "unique",
              "name": "Mountain Brew"},
        374: {"rarity": "unique",
              "name": "Starter Engineering Tool Kit"},
        662: {"rarity": "hero",
              "name": "Rocket Pig"},
        678: {"rarity": "hero",
              "name": "King Husky"},
        1493: {"rarity": "hero",
               "name": "Immensity Gauntlet"},
        1494: {"rarity": "hero",
               "name": "Starburst Bulwark"},
    }

    rarity_to_dna = {
        "common": 10,
        "elite": 40,
        "unique": 120,
        "epic": 400,
        "hero": 1600,
        "special": 5000,
        "legendary": 12000,
    }

    for id in design_ids:
        df: pd.DataFrame = None
        filename = os.path.join("data", "market", f"{id}")
        if os.path.exists(filename):
            with open(filename, "rb") as infile:
                df = pickle.load(infile)
        else:
            df = api.get_sales_for_design_id(id, past_days=7)
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "wb") as outfile:
                pickle.dump(df, outfile)
        try:
            count = len(df)
        except TypeError as e:
            count = 0
            pass
        name = design_ids[id]["name"]
        dna_cost = rarity_to_dna[design_ids[id]["rarity"]]
        mean = df["SinglePrice"].mean()
        std = df["SinglePrice"].std()
        price = df[(df["SinglePrice"] > mean - std) & (df["SinglePrice"] < mean + std)].mean(numeric_only=True)["SinglePrice"]

        output["item"].append(name)
        output["count"].append(count)
        output["price"].append(price)
        output["mean"].append(mean)
        output["dna_cost"].append(dna_cost)
        output["rarity"].append(design_ids[id]["rarity"])
        output["oldest"].append(df["StatusDate"].min())

    df = pd.DataFrame(output)
    df["bux/dna"] = df["price"] / df["dna_cost"]
    print(df.drop(columns=["oldest"]).sort_values("bux/dna", ascending=False).to_string(index=False))
    pass


async def main():
    data_path = "/data"
    if not os.path.exists(data_path):
        data_path = "data"

    api = PSSApi(data_path)
    await api.setup()
    items = Items(data_path, api)
    await items.setup()
    market = MarketListener(api, items, data_path)

    characters = Characters(data_path, api)
    await characters.setup()

    fleet = FleetListener(api, characters, items, data_path)

    with open (os.path.join(data_path, "config.json")) as f:
        config = json.load(f)

    bot = telegram_bot.TelegramBot(config["telegram"], market, items, fleet)
    market.set_telegram(bot)
    fleet.set_telegram(bot)

    await asyncio.gather(
        market.run(),
        market.run_trader_check(),
        bot.run(),
        fleet.run())


if __name__ == "__main__":
    asyncio.run(main())
