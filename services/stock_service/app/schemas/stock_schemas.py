from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MovementInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    product_id: int = Field(ge=1, le=9223372036854775807)
    type: Literal["IN", "OUT", "ADJUSTMENT"]
    quantity: int = Field(ge=0, le=2147483647)
    reason: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)
    expected_version: int = Field(ge=1)

    @field_validator("reason")
    @classmethod
    def clean(cls, value):
        if not value.strip():
            raise ValueError("Motif requis")
        return value.strip()
