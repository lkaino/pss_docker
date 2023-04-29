from datetime import datetime, timedelta
import hashlib
import json
import random
from typing import List, Optional

import aiohttp
from asyncio import Lock

import settings
import utils

import logging as log

# ---------- Constants & Internals ----------

ACCESS_TOKEN_TIMEOUT: timedelta = timedelta(minutes=3)

DEVICE_LOGIN_PATH: str = 'UserService/DeviceLogin8'

DEFAULT_DEVICE_TYPE: str = 'DeviceTypeMac'
DEVICES: 'DeviceCollection' = None


# ---------- Empty Classes ----------

class LoginError(Exception):
    """
    Raised, when an error occurs during login.
    """
    pass


class DeviceInUseError(LoginError):
    """
    Raised, when a device belongs to a real account.
    """
    pass


# ---------- Classes ----------

class Device():
    def __init__(self, device_key: str, can_login_until: datetime = None, device_type: str = None, access_token: str = None, last_login: datetime = None) -> None:
        self.__key: str = device_key
        self.__checksum: str = None
        self.__device_type = device_type or DEFAULT_DEVICE_TYPE
        self.__last_login: datetime = last_login
        self.__can_login_until: datetime = can_login_until
        self.__access_token: str = access_token
        self.__access_token_expires_at: datetime = None
        self.__set_access_token_expiry()
        self.__user: dict = None
        self.__token_lock: Lock = Lock()
        self.__update_lock: Lock = Lock()
        self.__can_login_until_changed: bool = False

    @property
    def access_token_expired(self) -> bool:
        if self.__access_token and self.__access_token_expires_at:
            return self.__access_token_expires_at < utils.get_utc_now()
        return True

    @property
    def can_login(self) -> bool:
        if self.__can_login_until is None:
            return True
        utc_now = utils.get_utc_now()
        if self.__can_login_until <= utc_now and self.__can_login_until.date == utc_now.date:
            return False
        return True

    @property
    def can_login_until(self) -> datetime:
        return self.__can_login_until
    
    @property
    def last_login(self) -> datetime:
        return self.__last_login

    @property
    def checksum(self) -> str:
        return self.__checksum

    @property
    def key(self) -> str:
        return self.__key

    async def get_access_token(self) -> str:
        """
        Returns a valid access token. If there's no valid access token related to this Device, this method will attempt to log in and retrieve an access token via the PSS API.
        """
        async with self.__token_lock:
            if self.access_token_expired:
                log.info("Access token is expired!")
                if self.can_login:
                    log.info("Logging in!")
                    await self.__login()
                else:
                    raise LoginError('Cannot login currently. Please try again later.')
            return self.__access_token


    async def __login(self) -> None:
        base_url = "https://api.pixelstarships.com/"
        url = f'{base_url}{DEVICE_LOGIN_PATH}'
        utc_now = utils.get_utc_now()
        client_datetime = utils.format.pss_datetime(utc_now)
        query_params = {
            'advertisingKey': '""',
            'checksum': _create_device_checksum(self.__key, self.__device_type, client_datetime),
            #'clientDateTime': client_datetime,
            'deviceKey': self.__key,
            'deviceType': self.__device_type,
            'isJailBroken': 'false',
            'languageKey': 'en',
        }
        if settings.PRINT_DEBUG_WEB_REQUESTS:
            print(f'[WebRequest] Attempting to get data from url: {url}')
            print(f'[WebRequest]   with parameters: {json.dumps(query_params, separators=(",", ":"))}')
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=query_params) as response:
                data = await response.text(encoding='utf-8')
                if settings.PRINT_DEBUG_WEB_REQUESTS:
                    log_data = data or ''
                    if log_data and len(log_data) > 100:
                        log_data = log_data[:100]
                    print(f'[WebRequest] Returned data: {log_data}')

        result = utils.convert.raw_xml_to_dict(data)
        self.__last_login = utc_now
        if 'UserService' in result.keys():
            user = result['UserService']['UserLogin'].get('User')

            if user and user.get('Name', None):
                self.__user = None
                self.__access_token = None
                raise DeviceInUseError('Cannot login. The device is already in use.')
            self.__user = user
            self.__access_token = result['UserService']['UserLogin']['accessToken']
            self.__set_can_login_until(utc_now)
        else:
            error_message = result.get('UserLogin', {}).get('errorMessage')
            if error_message:
                raise LoginError(error_message)
            self.__access_token = None
        self.__set_access_token_expiry()

    def __set_access_token_expiry(self) -> None:
        if self.__last_login and self.__access_token:
            self.__access_token_expires_at = self.__last_login + ACCESS_TOKEN_TIMEOUT
        else:
            self.__access_token_expires_at = None

    def __set_can_login_until(self, last_login: datetime) -> None:
        if not self.__can_login_until or last_login > self.__can_login_until:
            next_day = utils.datetime.get_next_day(self.__can_login_until) - utils.datetime.ONE_SECOND
            login_until = last_login + utils.datetime.FIFTEEN_HOURS
            self.__can_login_until = min(login_until, next_day)
            self.__can_login_until_changed = True


# ---------- Helper functions ----------

def _create_device_key() -> str:
    h = '0123456789abcdef'
    result = ''.join(
        random.choice(h)
        + random.choice('26ae')
        + random.choice(h)
        + random.choice(h)
        + random.choice(h)
        + random.choice(h)
        + random.choice(h)
        + random.choice(h)
        + random.choice(h)
        + random.choice(h)
        + random.choice(h)
        + random.choice(h)
    )
    return result


def _create_device_checksum(device_key: str, device_type: str, client_datetime: str) -> str:
    #result = hashlib.md5(
    #    f'{device_key}{client_datetime}{device_type}{settings.DEVICE_LOGIN_CHECKSUM_KEY}savysoda'.encode(
    #        'utf-8')).hexdigest()
    result = hashlib.md5((device_key + 'DeviceTypeMac' + 'savysoda').encode('utf-8')).hexdigest()
    return result

