from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CustomerIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    cpf: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        digits = "".join(char for char in value if char.isdigit())
        if len(digits) != 11 or len(set(digits)) == 1:
            raise ValueError("CPF inválido")
        for size in (9, 10):
            total = sum(int(digits[i]) * (size + 1 - i) for i in range(size))
            if ((10 * total) % 11) % 10 != int(digits[size]):
                raise ValueError("CPF inválido")
        return digits


class OrderItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=99)
    size: Literal["Pequeno", "Médio", "Grande"] | None = None
    meat_point: Literal["Ao ponto", "Bem passada"] | None = None


class OrderIn(BaseModel):
    customer: CustomerIn
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)


class PaymentIn(BaseModel):
    method: Literal["credit", "debit", "pix"]


class PaymentUpdate(BaseModel):
    status: Literal["waiting", "processing", "approved", "declined"]


class OrderStatusUpdate(BaseModel):
    status: Literal["preparing", "ready", "completed", "cancelled"]


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)

