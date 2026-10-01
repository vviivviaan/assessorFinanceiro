"""Esquemas Pydantic usados para forçar saída estruturada do agente extrator."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ItemGasto(BaseModel):
    category: str
    amount: float
    type: Literal["Debito", "Credito"]
    data: Optional[str] = Field(
        default=None,
        description=(
            "Data em que a transação aconteceu, no formato AAAA-MM-DD, "
            "SOMENTE se o usuário mencionar quando foi (data explícita como "
            "'12 de agosto de 2026', ou relativa como 'ontem', 'semana "
            "passada'). Se nenhuma data for mencionada na mensagem, deixe "
            "null — nunca invente uma data."
        ),
    )


class ListaGastos(BaseModel):
    gastos: list[ItemGasto]
