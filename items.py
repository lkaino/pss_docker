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
        filename = os.path.join(data_path, "items", f"df")
        if os.path.exists(filename):
            with open(filename, "rb") as infile:
                self._items = pickle.load(infile)
        else:
            self._items = api.get_items()
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "wb") as outfile:
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
