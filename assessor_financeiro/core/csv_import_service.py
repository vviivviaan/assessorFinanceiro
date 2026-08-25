"""Serviço de importação de extratos financeiros em CSV.

Isola o `pandas` num único lugar do sistema — se um dia vocês trocarem o
formato de entrada (Excel, OFX, etc.), é aqui que mexem.
"""
import io

import pandas as pd

CSV_COLUMNS = ["data", "descricao", "valor", "tipo"]


def parse_transacoes_csv(raw_bytes: bytes) -> pd.DataFrame:
    """Lê os bytes de um CSV de extrato (sem cabeçalho) e retorna um DataFrame limpo.

    Espera colunas na ordem: data, descricao, valor, tipo.
    """
    df = pd.read_csv(
        io.BytesIO(raw_bytes),
        header=None,
        names=CSV_COLUMNS,
        encoding="utf-8",  # Garante a leitura correta de acentos como 'Crédito'
    )
    df.columns = df.columns.str.strip()
    df["descricao"] = df["descricao"].str.strip()
    df["tipo"] = df["tipo"].str.strip()
    return df
