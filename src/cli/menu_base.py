#!/usr/bin/env python3
"""
Базовые классы для системы меню
"""

from abc import ABC, abstractmethod
from typing import Dict, Callable, Optional, Any
import sys

from .constants import Formatting


class MenuItem:
    """Элемент меню"""
    
    def __init__(self, key: str, label: str, action: Callable[[], Any], enabled: bool = True):
        self.key = key
        self.label = label
        self.action = action
        self.enabled = enabled
    
    def execute(self) -> Any:
        """Выполнить действие элемента меню"""
        if not self.enabled:
            return None
        return self.action()
    
    def __str__(self) -> str:
        return f"{self.key}. {self.label}"


class BaseMenu(ABC):
    """Базовый класс для меню"""
    
    def __init__(self, title: str):
        self.title = title
        self.items: Dict[str, MenuItem] = {}
        self.running = True
    
    def add_item(self, item: MenuItem) -> None:
        """Добавить элемент в меню"""
        self.items[item.key] = item
    
    def remove_item(self, key: str) -> None:
        """Удалить элемент из меню"""
        if key in self.items:
            del self.items[key]
    
    def get_item(self, key: str) -> Optional[MenuItem]:
        """Получить элемент меню по ключу"""
        return self.items.get(key)
    
    def display_header(self) -> None:
        """Отобразить заголовок меню"""
        print(f"\n{Formatting.SEPARATOR}")
        print(self.title)
        print(Formatting.SEPARATOR)
    
    def display_items(self) -> None:
        """Отобразить элементы меню"""
        for item in self.items.values():
            if item.enabled:
                print(item)
    
    def display_footer(self) -> None:
        """Отобразить подвал меню"""
        print(Formatting.LINE)
    
    def display_menu(self) -> None:
        """Отобразить полное меню"""
        self.display_header()
        self.display_items()
        self.display_footer()
        
        # Принудительно отправляем вывод в терминал (для PowerShell)
        sys.stdout.flush()
    
    def get_user_choice(self) -> str:
        """Получить выбор пользователя"""
        from .constants import Messages
        return input(Messages.CHOOSE_ACTION).strip()
    
    def handle_choice(self, choice: str) -> bool:
        """
        Обработать выбор пользователя
        
        Returns:
            bool: True если меню должно продолжить работу, False для выхода
        """
        item = self.get_item(choice)
        if item and item.enabled:
            try:
                result = item.execute()
                return self.process_action_result(choice, result)
            except Exception as e:
                self.handle_error(e)
                return True
        else:
            self.handle_invalid_choice(choice)
            return True
    
    def process_action_result(self, choice: str, result: Any) -> bool:
        """
        Обработать результат выполнения действия
        
        Args:
            choice: Выбранный пункт меню
            result: Результат выполнения действия
            
        Returns:
            bool: True если меню должно продолжить работу
        """
        return True
    
    def handle_invalid_choice(self, choice: str) -> None:
        """Обработать неверный выбор"""
        from .constants import Messages
        print(Messages.INVALID_CHOICE)
    
    def handle_error(self, error: Exception) -> None:
        """Обработать ошибку"""
        print(f"❌ Ошибка: {error}")
    
    def should_pause(self) -> bool:
        """Определить, нужна ли пауза после действия"""
        return True
    
    def pause(self) -> None:
        """Пауза для чтения результата"""
        if self.should_pause():
            from .constants import Messages
            input(f"\n{Messages.PRESS_ENTER}")
    
    @abstractmethod
    def setup_menu(self) -> None:
        """Настроить элементы меню (должно быть реализовано в наследниках)"""
        pass
    
    def run(self) -> None:
        """Запустить меню"""
        self.setup_menu()
        
        while self.running:
            self.display_menu()
            choice = self.get_user_choice()
            
            if not self.handle_choice(choice):
                break
            
            self.pause()
    
    def stop(self) -> None:
        """Остановить меню"""
        self.running = False


class NavigableMenu(BaseMenu):
    """Меню с возможностью навигации (возврат назад)"""
    
    def __init__(self, title: str, back_key: str = "0", back_label: str = "⬅️  Назад"):
        super().__init__(title)
        self.back_key = back_key
        self.back_label = back_label
    
    def setup_menu(self) -> None:
        """Базовая настройка - переопределяется в наследниках"""
        pass
    
    def run(self) -> None:
        """Запустить меню с добавлением кнопки 'Назад' в конце"""
        self.setup_menu()
        # Добавляем кнопку "Назад" в конец после всех остальных элементов
        self.add_item(MenuItem(self.back_key, self.back_label, self.go_back))
        
        while self.running:
            self.display_menu()
            choice = self.get_user_choice()
            
            if not self.handle_choice(choice):
                break
            
            self.pause()
    
    def go_back(self) -> None:
        """Вернуться назад"""
        self.stop()
    
    def process_action_result(self, choice: str, result: Any) -> bool:
        """Обработать результат с учетом навигации"""
        if choice == self.back_key:
            return False
        return super().process_action_result(choice, result)
    
    def should_pause(self) -> bool:
        """Не делаем паузу при возврате назад"""
        return True 