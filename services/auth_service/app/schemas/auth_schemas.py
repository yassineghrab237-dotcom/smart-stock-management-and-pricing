from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if "@" not in value or not value.split("@")[-1]:
            raise ValueError("Adresse email invalide")
        return value


class Setup(Login):
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value):
        if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError(
                "Le mot de passe doit contenir une majuscule et un chiffre"
            )
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Nom requis")
        return value


class CreateUser(Setup):
    role: Literal["ADMIN", "MANAGER", "VIEWER"]
