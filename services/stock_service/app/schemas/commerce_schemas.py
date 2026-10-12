from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Literal
from .product_schemas import normalize_price


class Mutation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    idempotency_key: str = Field(min_length=8, max_length=128)


class SaleLine(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    product_id: int = Field(ge=1, le=9223372036854775807)
    quantity: int = Field(ge=1, le=2147483647)
    unit_price_ttc: str
    discount_ttc: str = "0"
    tax_rate: str
    unit_cost_ht: str | None = None

    @field_validator("unit_price_ttc", "discount_ttc", "tax_rate", "unit_cost_ht")
    @classmethod
    def money(cls, value):
        return normalize_price(value) if value is not None else None

    @model_validator(mode="after")
    def amounts(self):
        if Decimal(self.tax_rate) > 100 or Decimal(self.discount_ttc) > Decimal(
            self.unit_price_ttc
        ):
            raise ValueError("Taxe ou remise invalide")
        return self


class DocumentInput(Mutation):
    reference: str = Field(min_length=1, max_length=100)
    kind: Literal["SALE", "QUOTE"]
    customer_id: int | None = Field(default=None, ge=1, le=9223372036854775807)
    note: str = Field(default="", max_length=2000)
    lines: list[SaleLine] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def distinct(self):
        if len({line.product_id for line in self.lines}) != len(self.lines):
            raise ValueError("Regrouper les quantités d'un même produit")
        return self


class ConfirmInput(Mutation):
    expected_version: int = Field(ge=1)
    product_versions: dict[str, int]
    sale_reference: str | None = Field(default=None, min_length=1, max_length=100)


class CancelInput(Mutation):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class ReturnInput(Mutation):
    quantity: int = Field(ge=1, le=2147483647)
    restock: bool
    reason: str = Field(min_length=1, max_length=1000)
    expected_product_version: int = Field(ge=1)
