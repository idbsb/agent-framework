from __future__ import annotations

from functools import lru_cache

from ..integration.system_data import SystemDataService
from .service import get_services


@lru_cache(maxsize=1)
def get_system_data() -> SystemDataService:
    return SystemDataService(get_services())

