"""Esquemas Pydantic usados para forçar saída estruturada do agente extrator."""
from typing import Literal
from pydantic import BaseModel


class ItemGasto(BaseModel):
    category: str
    amount: float
    type: Literal["Debito", "Credito"]


class ListaGastos(BaseModel):
    gastos: list[ItemGasto]
