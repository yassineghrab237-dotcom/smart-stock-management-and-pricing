from decimal import Decimal, InvalidOperation
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=180)
    sku: str = Field(min_length=1, max_length=80)
    category: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=40)
    cost_price: str | None = None
    current_price: str | None = None
    min_price: str | None = None
    threshold_min: int = Field(default=0, ge=0, le=2147483647)
    threshold_max: int | None = Field(default=None, ge=0, le=2147483647)

    @field_validator("name", "sku")
    @classmethod
    def clean(cls, value):
        if not value.strip():
            raise ValueError("Valeur requise")
        return value.strip()

    @field_validator("cost_price", "current_price", "min_price")
    @classmethod
    def price(cls, value):
        return normalize_price(value) if value is not None else None

    @model_validator(mode="after")
    def thresholds(self):
        if self.threshold_max is not None and self.threshold_max < self.threshold_min:
            raise ValueError("Le seuil maximum doit être supérieur ou égal au minimum")
        if (
            self.current_price is not None
            and self.min_price is not None
            and Decimal(self.current_price) < Decimal(self.min_price)
        ):
            raise ValueError("Le prix actuel est inférieur au prix minimum")
        return self


def normalize_price(value):
    try:
        price = Decimal(value)
        if (
            not price.is_finite()
            or price < 0
            or price > Decimal("999999999999.9999")
            or price.as_tuple().exponent < -4
        ):
            raise ValueError("Prix positif, maximum 4 décimales requis")
        return format(price.quantize(Decimal("0.0001")), "f")
    except InvalidOperation:
        raise ValueError("Prix invalide")


class ProductPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=180)
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    category: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=40)
    cost_price: str | None = None
    min_price: str | None = None
    threshold_min: int | None = Field(default=None, ge=0, le=2147483647)
    threshold_max: int | None = Field(default=None, ge=0, le=2147483647)


class PriceChange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    price: str
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)

    @field_validator("price")
    @classmethod
    def validate_price(cls, value):
        return normalize_price(value)

    @field_validator("reason")
    @classmethod
    def reason_required(cls, value):
        if not value.strip():
            raise ValueError("Motif requis")
        return value.strip()
