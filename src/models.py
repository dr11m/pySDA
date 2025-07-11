"""
Pydantic модели для Steam API ответов
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import IntEnum
from dataclasses import dataclass


class ConfirmationMethod(IntEnum):
    """Методы подтверждения трейдов"""
    NONE = 0              # Подтверждение не требуется
    EMAIL = 1             # Подтверждение через email
    MOBILE_APP = 2        # Подтверждение через мобильное приложение (Steam Guard)

    @property
    def display_name(self) -> str:
        """Человеко-читаемое название метода"""
        names = {
            0: "None",
            1: "Email", 
            2: "MobileApp"
        }
        return names.get(self.value, f"Unknown({self.value})")


class TradeOfferState(IntEnum):
    """Состояния трейд офферов согласно официальной документации Steam"""
    INVALID = 1
    ACTIVE = 2            # This trade offer has been sent, neither party has acted on it yet.
    ACCEPTED = 3          # The trade offer was accepted by the recipient and items were exchanged.
    COUNTERED = 4         # The recipient made a counter offer
    EXPIRED = 5           # The trade offer was not accepted before the expiration date
    CANCELED = 6          # The sender cancelled the offer
    DECLINED = 7          # The recipient declined the offer
    INVALID_ITEMS = 8     # Some of the items in the offer are no longer available (indicated by the missing flag in the output)
    CREATED_NEEDS_CONFIRMATION = 9  # The offer hasn't been sent yet and is awaiting further confirmation
    CANCELED_BY_SECOND_FACTOR = 10  # Either party canceled the offer via email/mobile confirmation
    IN_ESCROW = 11        # The trade has been placed on hold

    @property
    def display_name(self) -> str:
        """Человеко-читаемое название состояния"""
        names = {
            1: "Invalid",
            2: "Active", 
            3: "Accepted",
            4: "Countered",
            5: "Expired",
            6: "Canceled",
            7: "Declined",
            8: "InvalidItems",
            9: "CreatedNeedsConfirmation",
            10: "CanceledBySecondFactor",
            11: "InEscrow"
        }
        return names.get(self.value, f"Unknown({self.value})")


class TradeItem(BaseModel):
    """Предмет в трейде"""
    appid: int
    contextid: str
    assetid: str
    classid: str
    instanceid: str
    amount: str
    missing: Optional[bool] = None
    est_usd: Optional[str] = None


class TradeOffer(BaseModel):
    """Трейд оффер"""
    tradeofferid: str
    accountid_other: int
    message: Optional[str] = None
    expiration_time: Optional[int] = None
    trade_offer_state: TradeOfferState
    items_to_give: Optional[List[TradeItem]] = Field(default_factory=list)
    items_to_receive: Optional[List[TradeItem]] = Field(default_factory=list)
    is_our_offer: bool
    time_created: int
    time_updated: int
    tradeid: Optional[str] = None
    from_real_time_trade: bool = False
    escrow_end_date: int = 0
    confirmation_method: int = 0
    eresult: Optional[int] = None
    delay_settlement: bool = False

    @property
    def state_name(self) -> str:
        """Человеко-читаемое название состояния"""
        return self.trade_offer_state.display_name

    @property
    def is_active(self) -> bool:
        """Проверка, активен ли трейд"""
        return self.trade_offer_state == TradeOfferState.ACTIVE

    @property
    def needs_confirmation(self) -> bool:
        """Требует ли трейд подтверждения через Guard"""
        # Логика подтверждения:
        # 1. Для входящих трейдов (is_our_offer = False):
        #    - Если трейд активный (ACTIVE = 2) и confirmation_method == 2 (MobileApp), 
        #      то требуется подтверждение через Guard
        #    - Если трейд принят (ACCEPTED = 3) и confirmation_method == 2 (MobileApp) 
        #      и tradeid пустой, то требуется подтверждение через Guard
        # 2. Для исходящих трейдов (is_our_offer = True):
        #    - Если трейд в состоянии CREATED_NEEDS_CONFIRMATION (9), то требуется подтверждение
        
        # Для входящих трейдов
        if not self.is_our_offer:
            # Активный трейд с мобильным подтверждением
            if (self.trade_offer_state == TradeOfferState.ACTIVE and 
                self.confirmation_method == ConfirmationMethod.MOBILE_APP):
                return True

        
        # Для исходящих трейдов
        else:
            # Трейд создан и ожидает подтверждения
            if self.trade_offer_state == TradeOfferState.CREATED_NEEDS_CONFIRMATION:
                return True
        
        return False

    @property
    def items_to_give_count(self) -> int:
        """Количество предметов к отдаче"""
        return len(self.items_to_give) if self.items_to_give else 0

    @property
    def items_to_receive_count(self) -> int:
        """Количество предметов к получению"""
        return len(self.items_to_receive) if self.items_to_receive else 0

    @property
    def confirmation_method_name(self) -> str:
        """Название метода подтверждения"""
        try:
            return ConfirmationMethod(self.confirmation_method).display_name
        except ValueError:
            return f"Unknown({self.confirmation_method})"

    @property
    def is_incoming(self) -> bool:
        """Является ли трейд входящим"""
        return not self.is_our_offer

    @property
    def is_outgoing(self) -> bool:
        """Является ли трейд исходящим"""
        return self.is_our_offer

    @property
    def requires_mobile_confirmation(self) -> bool:
        """Требует ли трейд мобильного подтверждения"""
        return self.confirmation_method == ConfirmationMethod.MOBILE_APP


class ItemDescription(BaseModel):
    """Описание предмета"""
    appid: int
    classid: str
    instanceid: str
    currency: bool = False
    background_color: Optional[str] = None
    icon_url: Optional[str] = None
    icon_url_large: Optional[str] = None
    descriptions: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tradable: bool = True
    actions: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    fraudwarnings: Optional[List[str]] = Field(default_factory=list)
    name: str
    name_color: Optional[str] = None
    type: Optional[str] = None
    market_name: Optional[str] = None
    market_hash_name: Optional[str] = None
    commodity: bool = False
    market_tradable_restriction: int = 0
    market_marketable_restriction: int = 0
    marketable: bool = True
    tags: Optional[List[Dict[str, str]]] = Field(default_factory=list)


class TradeOffersResponse(BaseModel):
    """Ответ API для получения трейд офферов"""
    trade_offers_received: Optional[List[TradeOffer]] = Field(default_factory=list)
    trade_offers_sent: Optional[List[TradeOffer]] = Field(default_factory=list)
    descriptions: Optional[List[ItemDescription]] = Field(default_factory=list)
    next_cursor: Optional[int] = None

    @property
    def active_received(self) -> List[TradeOffer]:
        """Активные входящие трейды"""
        return [offer for offer in self.trade_offers_received if offer.is_active]

    @property
    def active_sent(self) -> List[TradeOffer]:
        """Активные исходящие трейды"""
        return [offer for offer in self.trade_offers_sent if offer.is_active]

    @property
    def confirmation_needed_received(self) -> List[TradeOffer]:
        """Входящие трейды, требующие подтверждения"""
        return [offer for offer in self.trade_offers_received if offer.needs_confirmation]

    @property
    def confirmation_needed_sent(self) -> List[TradeOffer]:
        """Исходящие трейды, требующие подтверждения"""
        return [offer for offer in self.trade_offers_sent if offer.needs_confirmation]

    @property
    def total_active_offers(self) -> int:
        """Общее количество активных офферов"""
        return len(self.active_received) + len(self.active_sent)

    @property
    def total_confirmation_needed(self) -> int:
        """Общее количество офферов, требующих подтверждения"""
        return len(self.confirmation_needed_received) + len(self.confirmation_needed_sent)


@dataclass
class SteamApiResponse:
    success: bool


class TradeOffersSummaryResponse(BaseModel):
    """Краткая сводка по трейд офферам"""
    pending_received_count: int = 0
    new_received_count: int = 0
    updated_received_count: int = 0
    historical_received_count: int = 0
    pending_sent_count: int = 0
    newly_accepted_sent_count: int = 0
    updated_sent_count: int = 0
    historical_sent_count: int = 0
    escrow_received_count: int = 0
    escrow_sent_count: int = 0


class SteamApiSummaryResponse(BaseModel):
    """Ответ API для сводки трейд офферов"""
    response: TradeOffersSummaryResponse 