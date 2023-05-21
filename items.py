from typing import Optional
from pss_api import PSSApi
import cloudpickle as pickle
import os


class Items:
    PRICE_CORRECTIONS = {
        "Starburst Bulwark": 700,
        "Immensity Gauntlet": 700,
        "Rocket Pig": 600,
        "King Husky": 600,
    }

    def __init__(self, data_path, api: PSSApi):
        self._filename = os.path.join(data_path, "items", f"df")
        self._api = api
        self._items: Optional[Items] = None
    
    async def setup(self):
        if os.path.exists(self._filename):
            with open(self._filename, "rb") as infile:
                self._items = pickle.load(infile)
        else:
            self._items = await self._api.get_items()
            os.makedirs(os.path.dirname(self._filename), exist_ok=True)
            with open(self._filename, "wb") as outfile:
                pickle.dump(self._items, outfile)

    def get_design_id_by_name(self, name: str) -> Optional[int]:
        try:
            return int(self._items[self._items["ItemDesignName"] == name].iloc[0]['ItemDesignId'])
        except:
            return None

    def get_name_by_design_id(self, design_id: int) -> Optional[str]:
        try:
            return self._items[self._items["ItemDesignId"] == design_id].iloc[0]['ItemDesignName']
        except:
            return None

    def get_market_price(self, design_id: int) -> Optional[int]:
        name = self.get_name_by_design_id(design_id)
        if name is None:
            return None
        else:
            if name in self.PRICE_CORRECTIONS:
                return self.PRICE_CORRECTIONS[name]
            else:
                try:
                    return self._items[self._items["ItemDesignId"] == design_id].iloc[0]["MarketPrice"]
                except:
                    return None
    
    def get_rarity(self, design_id: int) -> Optional[str]:
        name = self.get_name_by_design_id(design_id)
        if name is None:
            return None
        else:
            try:
                return self._items[self._items["ItemDesignId"] == design_id].iloc[0]["Rarity"]
            except:
                return None
    
    def get_subtype(self, design_id: int) -> Optional[str]:
        name = self.get_name_by_design_id(design_id)
        if name is None:
            return None
        else:
            try:
                return self._items[self._items["ItemDesignId"] == design_id].iloc[0]["ItemSubType"]
            except:
                return None
    
    def get_main_stat(self, design_id: int):
        name = self.get_name_by_design_id(design_id)
        if name is None:
            return None
        else:
            try:
                return self._items[self._items["ItemDesignId"] == design_id].iloc[0]["EnhancementType"]
            except:
                return None

    def item_can_have_substats(self, design_id: int) -> Optional[str]:
        rarity = self.get_rarity(design_id)
        subtype = self.get_subtype(design_id)
        return "Equipment" in subtype and rarity in ("Hero", "Special", "Legendary")

    def get_enhancement(self, design_id: int) -> (Optional[str], Optional[float]):
        row = self._items[self._items["ItemDesignId"] == design_id].iloc[0]
        type = row.EnhancementType
        if 'None' in type:
            return None, None
        else:
            value = float(row.EnhancementValue)
        return type, value