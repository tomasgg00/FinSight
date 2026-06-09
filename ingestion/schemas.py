from pydantic import BaseModel, field_validator, ConfigDict
from datetime import datetime
from typing import Optional

class PriceRecord(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=False)

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    ticker: str
    ingested_at: datetime

    @field_validator('close', 'open', 'high', 'low')
    @classmethod
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError(f"Price must be positive, got {v}")
        return v

    @field_validator('volume')
    @classmethod
    def volume_must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Volume must be non-negative, got {v}")
        return v

    @field_validator('high')
    @classmethod
    def high_must_be_gte_low(cls, v):
        return v

    @field_validator('ticker')
    @classmethod
    def ticker_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Ticker must not be empty")
        return v.upper()