from typing import Optional
from pss_api import PSSApi
import cloudpickle as pickle
import os
import pandas as pd

class Characters:
    def __init__(self, data_path, api: PSSApi):
        self._filename = os.path.join(data_path, "characters", f"df")
        self._api = api
        self._characters: pd.DataFrame = None
    
    async def setup(self):
        if os.path.exists(self._filename):
            with open(self._filename, "rb") as infile:
                self._characters = pickle.load(infile)
        else:
            self._characters = await self._api.get_characters()
            os.makedirs(os.path.dirname(self._filename), exist_ok=True)
            with open(self._filename, "wb") as outfile:
                pickle.dump(self._characters, outfile)

    def get_stat_at_level(self, character_id: int, level: int, stat: str) -> float:
        row = self._characters[self._characters["CharacterDesignId"] == character_id].iloc[0]
        if not row.empty:
            initial = row[stat]
            final = row[f"Final{stat}"]
            gain = float(level) / 40.
            range = final - initial
            return initial + range * gain
        else:
            return 0