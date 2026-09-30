"""Ponto de entrada da aplicação Reflex.

Este é o arquivo apontado por `app_name` em `rxconfig.py`. Propositalmente
fino: só registra a página e o `on_load`. Toda a lógica real está em
`state.py` (backend) e `ui/` (frontend).
"""
import reflex as rx

from assessor_financeiro.state import AdvisorState
from assessor_financeiro.ui.pages import index

app = rx.App()
app.add_page(index, on_load=AdvisorState.on_load)
