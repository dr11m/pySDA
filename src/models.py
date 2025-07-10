"""
Pydantic модели для Steam API ответов
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import IntEnum
from dataclasses import dataclass


class TradeOfferState(IntEnum):
    """Состояния трейд офферов"""
    INVALID = 1
    ACTIVE = 2  
    ACCEPTED = 3
    COUNTERED = 4
    EXPIRED = 5
    CANCELED = 6
    DECLINED = 7
    INVALID_ITEMS = 8
    CREATED_NEEDS_CONFIRMATION = 9
    CANCELED_BY_SECOND_FACTOR = 10
    IN_ESCROW = 11

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
        """Требует ли трейд подтверждения"""
        return self.trade_offer_state == TradeOfferState.CREATED_NEEDS_CONFIRMATION

    @property
    def items_to_give_count(self) -> int:
        """Количество предметов к отдаче"""
        return len(self.items_to_give) if self.items_to_give else 0

    @property
    def items_to_receive_count(self) -> int:
        """Количество предметов к получению"""
        return len(self.items_to_receive) if self.items_to_receive else 0


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