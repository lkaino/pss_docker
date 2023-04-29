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

    async def setup(self):
        self._dev = await self._get_device()
        response = requests.get('http://ifconfig.me')
        log.info(f"External IP address: {response.text}")

    async def _get_token(self, get_new=False):
        return await self._dev.get_access_token()

    async def _get_device(self, get_new=False) -> Optional[Device]:
        filename = os.path.join(self._data_path, "device.pickle")
        dev = None
        if not get_new and os.path.exists(filename):
            with open(filename, "rb") as infile:
                data = pickle.load(infile)
                log.info(f"Creating device with {data}")
                dev = Device(
                    device_key=data[0], can_login_until=data[1], access_token=data[2], last_login=data[3])
        else:
            dev = Device(_create_device_key())
            token = await dev.get_access_token()
            with open(filename, "wb") as outfile:
                data = (dev.key, dev.can_login_until, token, dev.last_login)
                pickle.dump(data, outfile)

        return dev

    async def _check_if_token_expired_from_response(self, response: str):
        if "Failed to authorize" in response:
            self.token = await self._get_token(get_new=True)

    async def get_items(self, _token=None) -> pd.DataFrame:
        df: pd.DataFrame = None
        params = {
            'accessToken': await self._get_token(),
        }
        try:
            response = requests.get(
                self.BASE_URL + "ItemService/ListItemDesigns2", params=params)
        except Exception as e:
            return df

        try:
            df = pd.read_xml(
                response.text, xpath="/ItemService/ListItemDesigns/ItemDesigns//ItemDesign")
        except Exception as e:
            await self._check_if_token_expired_from_response(response.text)
            print(f"ERROR: {e}: {response.text}")

        return df

    async def get_characters(self, _token=None) -> pd.DataFrame:
        df: pd.DataFrame = None
        params = {
        }
        try:
            response = requests.get(
                self.BASE_URL + "CharacterService/ListAllCharacterDesigns2", params=params)
        except Exception as e:
            return df

        try:
            df = pd.read_xml(
                response.text, xpath="/CharacterService/ListAllCharacterDesigns/CharacterDesigns//CharacterDesign")
        except Exception as e:
            await self._check_if_token_expired_from_response(response.text)
            print(f"ERROR: {e}: {response.text}")

        return df

    async def get_star_system_markers(self, _token=None) -> pd.DataFrame:
        log.info(f"Getting star system markers")
        df: pd.DataFrame = None
        params = {
            'accessToken': await self._get_token(),
        }
        try:
            response = requests.get(
                self.BASE_URL + "GalaxyService/ListStarSystemMarkers", params=params)
        except Exception as e:
            return df

        try:
            df = pd.read_xml(response.text, xpath="/GalaxyService/ListStarSystemMarkers/StarSystemMarkers//StarSystemMarker",
                             parse_dates=["StarSystemArrivalDate", "ExpiryDate", "TravelStartDate", "LastUpdateDate"])
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
                'accessToken': await self._get_token(),
            }
            response = requests.get(
                self.BASE_URL + "/MarketService/ListSalesByItemDesignId", params=params)
            try:
                df_new = pd.read_xml(response.text, xpath="/MarketService/ListSalesByItemDesignId/Sales//Sale",
                                     parse_dates=["StatusDate"])
            except Exception as e:
                if "Too many" in response.text:
                    log.info(
                        f"Got too many response while getting sales for {design_id}")
                    await asyncio.sleep(10)
                    continue
                await self._check_if_token_expired_from_response(response.text)
                log.error(f"ERROR: {response.text}")
                return df
            len_all = len(df_new)
            df_new = df_new[df_new["CurrencyType"] == "Starbux"]
            df_new["SinglePrice"] = df_new["CurrencyValue"] / \
                df_new["Quantity"]
            if len_all > 0:
                if df is None:
                    df = df_new
                else:
                    df = pd.concat([df, df_new], ignore_index=True)
            else:
                break
            start += 20
            end += 20
            if pd.Timestamp.now() - df["StatusDate"].min() > pd.Timedelta(days=past_days):
                break
            if len(df) > max_count:
                break
            await asyncio.sleep(2)
        return df

    async def get_market_messages(self, design_id: Optional[int], count=999999) -> pd.DataFrame:

        log.debug(f"Getting market for id {design_id}")

        df: pd.DataFrame = None
        params = {
            'currencyType': 'Unknown',
            'itemSubType': 'None',
            'rarity': 'None',
            'userId': 0,
            'skip': 0,
            'take': count,
            'accessToken': await self._get_token(),
        }
        if design_id:
            params['itemDesignId'] = design_id
        log.debug(params)
        try:
            response = requests.get(
                self.BASE_URL + "/MessageService/ListActiveMarketplaceMessages5", params=params)
        except Exception as e:
            print(e)
            return df

        try:
            log.debug(f"RESPONSE {response.text}")
            df = pd.read_xml(response.text, xpath="/MessageService/ListActiveMarketplaceMessages/Messages//Message",
                             parse_dates=["MessageDate"])
        except Exception as e:
            await self._check_if_token_expired_from_response(response.text)
            if "Too many" in response.text:
                time.sleep(10)
        return df

    async def get_available_donated_crew_for_fleet(self, fleet_id: int, count=999999) -> pd.DataFrame:
        log.debug(f"Getting donated crew for id {fleet_id}")

        df: pd.DataFrame = None
        params = {
            'allianceId': fleet_id,
            'skip': 0,
            'take': count,
            'accessToken': await self._get_token(),
        }
        try:
            response = requests.get(
                self.BASE_URL + "/AllianceService/ListCharactersGivenInAlliance", params=params)
        except Exception as e:
            print(e)
            return df

        try:
            log.debug(f"RESPONSE {response.text}")
            df = pd.read_xml(response.text, xpath="/AllianceService/ListCharactersGivenInAlliance/Characters//Character",
                             stylesheet="fleetitems.xsl",
                             parse_dates=["TrainingEndDate", "DeploymentDate", "AvailableDate"])
        except Exception as e:
            await self._check_if_token_expired_from_response(response.text)
            if "Too many" in response.text:
                time.sleep(10)
        return df

    async def get_alliances(self, count=100) -> pd.DataFrame:
        df: pd.DataFrame = None
        params = {
            'take': count,
        }
        try:
            response = requests.get(
                self.BASE_URL + "/AllianceService/ListAlliancesByRanking", params=params)
        except Exception as e:
            print(e)
            return df

        try:
            log.debug(f"RESPONSE {response.text}")
            df = pd.read_xml(response.text, xpath="/AllianceService/ListAlliancesByRanking/Alliances//Alliance",
                             parse_dates=["ImmunityDate"])
        except Exception as e:
            await self._check_if_token_expired_from_response(response.text)
            if "Too many" in response.text:
                time.sleep(10)
        return df
