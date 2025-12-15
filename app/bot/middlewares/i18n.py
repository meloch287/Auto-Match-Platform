import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.models.user import LanguageEnum, User

DEFAULT_LANGUAGE = LanguageEnum.AZ

TRANSLATIONS_DIR = Path(__file__).parent.parent / "translations"

class TranslationManager:

    
    _instance: Optional["TranslationManager"] = None
    _translations: Dict[str, Dict[str, str]] = {}
    
    def __new__(cls) -> "TranslationManager":

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_translations()
        return cls._instance
    
    def _load_translations(self) -> None:

        self._translations = {}
        
        for lang in LanguageEnum:
            file_path = TRANSLATIONS_DIR / f"{lang.value}.json"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    self._translations[lang.value] = json.load(f)
            else:
                self._translations[lang.value] = {}
    
    def reload(self) -> None:

        self._load_translations()
    
    def get(
        self,
        key: str,
        lang: str = DEFAULT_LANGUAGE.value,
        **kwargs: Any,
    ) -> str:
        """
        Get a translation by key.
        
        Args:
            key: Translation key (supports dot notation for nested keys)
            lang: Language code (az, ru, en)
            **kwargs: Format arguments for the translation string
            
        Returns:
            Translated string or the key if not found
        """
        translations = self._translations.get(lang, {})
        
        value = translations
        for part in key.split("."):
            if isinstance(value, dict):
                value = value.get(part, {})
            else:
                value = {}
        
        if isinstance(value, str):
            try:
                return value.format(**kwargs) if kwargs else value
            except KeyError:
                return value
        
        if lang != DEFAULT_LANGUAGE.value:
            return self.get(key, DEFAULT_LANGUAGE.value, **kwargs)
        
        return key
    
    def get_all_keys(self, lang: str = DEFAULT_LANGUAGE.value) -> list[str]:

        def _flatten_keys(d: Dict, prefix: str = "") -> list[str]:
            keys = []
            for k, v in d.items():
                full_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys.extend(_flatten_keys(v, full_key))
                else:
                    keys.append(full_key)
            return keys
        
        return _flatten_keys(self._translations.get(lang, {}))

class Translator:

    
    def __init__(self, lang: str, manager: TranslationManager):

        self.lang = lang
        self._manager = manager
    
    def __call__(self, key: str, **kwargs: Any) -> str:

        return self._manager.get(key, self.lang, **kwargs)
    
    def get(self, key: str, **kwargs: Any) -> str:

        return self(key, **kwargs)

class I18nMiddleware(BaseMiddleware):

    
    def __init__(self) -> None:

        self.manager = TranslationManager()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Process the event and inject translation function.
        
        Args:
            handler: The next handler in the chain
            event: The incoming event
            data: Handler data dictionary
            
        Returns:
            Result from the handler
        """
        user: Optional[User] = data.get("user")
        
        if user is not None:
            lang = user.language.value
        else:
            lang = DEFAULT_LANGUAGE.value
        
        translator = Translator(lang, self.manager)
        
        data["_"] = translator
        data["i18n"] = translator
        data["lang"] = lang
        
        return await handler(event, data)

def get_translator(lang: str = DEFAULT_LANGUAGE.value) -> Translator:

    manager = TranslationManager()
    return Translator(lang, manager)

def _(key: str, lang: str = DEFAULT_LANGUAGE.value, **kwargs: Any) -> str:

    manager = TranslationManager()
    return manager.get(key, lang, **kwargs)
