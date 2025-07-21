from __future__ import annotations

import enum
import json
import time
from http import HTTPStatus
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from . import guard
from .exceptions import ConfirmationExpected
from .login import InvalidCredentials
from src.utils.logger_setup import logger

if TYPE_CHECKING:
    import requests


class Confirmation:
    def __init__(self, data_confid, nonce, creator_id) -> None:
        self.data_confid = data_confid
        self.nonce = nonce
        self.creator_id = creator_id


class Tag(enum.Enum):
    CONF = 'conf'
    DETAILS = 'details'
    ALLOW = 'allow'
    CANCEL = 'cancel'


class ConfirmationExecutor:
    CONF_URL = 'https://steamcommunity.com/mobileconf'

    def __init__(self, identity_secret: str, my_steam_id: str, session: requests.Session) -> None:
        self._my_steam_id = my_steam_id
        self._identity_secret = identity_secret
        self._session = session

    def send_trade_allow_request(self, trade_offer_id: str) -> dict:
        confirmations = self._get_confirmations()
        confirmation = self._select_trade_offer_confirmation(confirmations, trade_offer_id)
        return self._send_confirmation(confirmation)

    def confirm_sell_listing(self, asset_id: str) -> dict:
        confirmations = self._get_confirmations()
        confirmation = self._select_sell_listing_confirmation(confirmations, asset_id)
        return self._send_confirmation(confirmation)

    def _send_confirmation(self, confirmation: Confirmation) -> dict:
        tag = Tag.ALLOW
        params = self._create_confirmation_params(tag.value)
        params['op'] = (tag.value,)
        params['cid'] = confirmation.data_confid
        params['ck'] = confirmation.nonce
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        response = self._session.get(f'{self.CONF_URL}/ajaxop', params=params, headers=headers).json()
        logger.info(f"🔑 Отправлен запрос на подтверждение, response:\n {response}")
        
        return response

    def _get_confirmations(self) -> list[Confirmation]:
        confirmations = []
        confirmations_page = self._fetch_confirmations_page()
        if confirmations_page.status_code == HTTPStatus.OK:
            confirmations_json = json.loads(confirmations_page.text)
            for conf in confirmations_json['conf']:
                data_confid = conf['id']
                nonce = conf['nonce']
                creator_id = int(conf["creator_id"])
                confirmations.append(Confirmation(data_confid, nonce, creator_id))
            return confirmations
        else:
            raise ConfirmationExpected
        
    def get_confirmation(self, key: str | int, *, update_listings=True) -> Confirmation:
        """
        Fetch all confirmations from `Steam`, filter and get one.

        :param key: `MarketListingItem` ident code, `TradeOffer` id or request id
        :param update_listings: update confirmation details if its type is listing.
            Needed to map confirmation to listing
        :return: `Confirmation`
        :raises KeyError: when unable to find confirmation by key
        :raises EResultError: for ordinary reasons
        """
        key = int(key)

        confs: list[Confirmation] = self._get_confirmations()
        # not well performant but anyway
        conf = next(filter(lambda c: c.creator_id == key, confs), None)
        if conf is None:
            raise KeyError(f"Unable to find confirmation for {key} ident/trade/listing id")

        return conf
        
    def confirm_api_key_request(self, request_id: str) -> Confirmation:
        """Perform api key request confirmation."""

        conf = self.get_confirmation(request_id)
        conf_response = self._send_confirmation(conf)

        return conf

    def _fetch_confirmations_page(self) -> requests.Response:
        tag = Tag.CONF.value
        params = self._create_confirmation_params(tag)
        headers = {'X-Requested-With': 'com.valvesoftware.android.steam.community'}
        response = self._session.get(f'{self.CONF_URL}/getlist', params=params, headers=headers)
        if 'Steam Guard Mobile Authenticator is providing incorrect Steam Guard codes.' in response.text:
            raise InvalidCredentials('Invalid Steam Guard file')
        # Сохраняем ответ в текстовый файл для отладки
        try:
            with open("debug_confirmations_page.txt", "w", encoding="utf-8") as f:
                f.write(response.text)
        except Exception as e:
            pass  # Не мешаем основной логике, если не удалось сохранить
        return response

    def _fetch_confirmation_details_page(self, confirmation: Confirmation) -> str:
        tag = f'details{confirmation.data_confid}'
        params = self._create_confirmation_params(tag)
        response = self._session.get(f'{self.CONF_URL}/details/{confirmation.data_confid}', params=params)
        return response.json()['html']

    def _create_confirmation_params(self, tag_string: str) -> dict:
        timestamp = int(time.time())
        confirmation_key = guard.generate_confirmation_key(self._identity_secret, tag_string, timestamp)
        android_id = guard.generate_device_id(self._my_steam_id)
        return {
            'p': android_id,
            'a': self._my_steam_id,
            'k': confirmation_key,
            't': timestamp,
            'm': 'android',
            'tag': tag_string,
        }

    def _select_trade_offer_confirmation(self, confirmations: list[Confirmation], trade_offer_id: str) -> Confirmation:
        for confirmation in confirmations:
            confirmation_details_page = self._fetch_confirmation_details_page(confirmation)
            confirmation_id = self._get_confirmation_trade_offer_id(confirmation_details_page)
            if confirmation_id == trade_offer_id:
                return confirmation
        raise ConfirmationExpected

    def _select_sell_listing_confirmation(self, confirmations: list[Confirmation], asset_id: str) -> Confirmation:
        for confirmation in confirmations:
            confirmation_details_page = self._fetch_confirmation_details_page(confirmation)
            confirmation_id = self._get_confirmation_sell_listing_id(confirmation_details_page)
            if confirmation_id == asset_id:
                return confirmation
        raise ConfirmationExpected

    @staticmethod
    def _get_confirmation_sell_listing_id(confirmation_details_page: str) -> str:
        soup = BeautifulSoup(confirmation_details_page, 'html.parser')
        scr_raw = soup.select('script')[2].string.strip()
        scr_raw = scr_raw[scr_raw.index("'confiteminfo', ") + 16:]
        scr_raw = scr_raw[: scr_raw.index(', UserYou')].replace('\n', '')
        return json.loads(scr_raw)['id']

    @staticmethod
    def _get_confirmation_trade_offer_id(confirmation_details_page: str) -> str:
        soup = BeautifulSoup(confirmation_details_page, 'html.parser')
        full_offer_id = soup.select('.tradeoffer')[0]['id']
        return full_offer_id.split('_')[1]

