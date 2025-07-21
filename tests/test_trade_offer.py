#!/usr/bin/env python3
"""
Тест обработки trade offer подтверждений
"""

import json
from src.utils.confirmation_utils import determine_confirmation_type_from_json, extract_confirmation_info

# Данные из debug файла
test_data = {
    "type": 2,
    "type_name": "Trade Offer",
    "id": "17893493700",
    "creator_id": "8290798358",
    "nonce": "7352666265781679998",
    "creation_time": 1753056725,
    "cancel": "Cancel",
    "accept": "Send Offer",
    "icon": "https://avatars.fastly.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg",
    "multi": False,
    "headline": "tHomaS11",
    "summary": ["You will give up your The Enforcer", "You will receive nothing"],
    "warn": None
}

def test_trade_offer():
    print("🧪 Тестируем обработку trade offer...")
    
    # Определяем тип
    conf_type = determine_confirmation_type_from_json(test_data)
    print(f"📋 Тип подтверждения: {conf_type}")
    
    # Получаем информацию
    info = extract_confirmation_info(test_data, conf_type)
    print(f"📝 Описание: {info['description']}")
    print(f"👤 Партнер: {info['partner_name']}")
    print(f"📦 Элементы: {info['summary_items']}")

if __name__ == "__main__":
    test_trade_offer() 