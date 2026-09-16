"""Serviço de importação de extratos financeiros em múltiplos formatos.

Isola as bibliotecas de parsing (pandas, ofxparse, pypdf) num único lugar do
sistema. Cada formato tabular (CSV, XLSX, OFX) converge para o mesmo shape de
colunas (`COLUNAS_PADRAO`), então o restante do app (`state.py`) não precisa
saber qual formato foi enviado — só itera o DataFrame resultante.

PDF é tratado à parte: extratos em PDF não têm uma tabela fixa (cada banco
formata diferente), então aqui só extraímos o texto bruto; quem transforma
esse texto em transações estruturadas é o agente extrator (LLM), orquestrado
em `state.py` — a mesma infraestrutura que já processa o texto do chat.
"""
import io
from pathlib import Path

import pandas as pd

COLUNAS_PADRAO = ["data", "descricao", "valor", "tipo"]
_INDICE_COLUNA_VALOR = COLUNAS_PADRAO.index("valor")

FORMATOS_TABULARES_SUPORTADOS = {".csv", ".xlsx", ".xls", ".ofx", ".qfx"}
FORMATOS_SUPORTADOS = FORMATOS_TABULARES_SUPORTADOS | {".pdf"}


def _primeira_linha_e_cabecalho(primeira_linha: list) -> bool:
    """Detecta se a primeira linha é um cabeçalho (ex.: "data,descricao,valor,tipo").

    O arquivo não tem um cabeçalho fixo esperado, mas é comum que exportações
    reais venham com um — em vez de exigir que o usuário sempre remova a
    primeira linha, checamos se a coluna que deveria ser numérica (`valor`)
    de fato converte para número. Se não converter, é texto de cabeçalho, e a
    linha é descartada.
    """
    try:
        valor_bruto = str(primeira_linha[_INDICE_COLUNA_VALOR])
        float(valor_bruto.strip().replace(",", "."))
        return False
    except (ValueError, IndexError):
        return True


def parse_transacoes_csv(raw_bytes: bytes) -> pd.DataFrame:
    """Lê os bytes de um CSV de extrato e retorna um DataFrame limpo.

    Espera colunas na ordem: data, descricao, valor, tipo. Funciona com ou
    sem linha de cabeçalho (detectada automaticamente).
    """
    primeira_linha = pd.read_csv(
        io.BytesIO(raw_bytes), header=None, nrows=1, encoding="utf-8"
    ).iloc[0].tolist()
    tem_cabecalho = _primeira_linha_e_cabecalho(primeira_linha)

    df = pd.read_csv(
        io.BytesIO(raw_bytes),
        header=0 if tem_cabecalho else None,
        names=COLUNAS_PADRAO,
        encoding="utf-8",  # Garante a leitura correta de acentos como 'Crédito'
    )
    df.columns = df.columns.str.strip()
    df["descricao"] = df["descricao"].str.strip()
    df["tipo"] = df["tipo"].str.strip()
    return df


def parse_transacoes_xlsx(raw_bytes: bytes) -> pd.DataFrame:
    """Lê uma planilha Excel (.xlsx/.xls) com o mesmo layout do CSV (com ou sem cabeçalho)."""
    primeira_linha = pd.read_excel(io.BytesIO(raw_bytes), header=None, nrows=1).iloc[0].tolist()
    tem_cabecalho = _primeira_linha_e_cabecalho(primeira_linha)

    df = pd.read_excel(
        io.BytesIO(raw_bytes),
        header=0 if tem_cabecalho else None,
        names=COLUNAS_PADRAO,
    )
    df["descricao"] = df["descricao"].astype(str).str.strip()
    df["tipo"] = df["tipo"].astype(str).str.strip()
    return df


def parse_transacoes_ofx(raw_bytes: bytes) -> pd.DataFrame:
    """Lê um extrato bancário no formato OFX/QFX (padrão de exportação de bancos).

    O tipo (Crédito/Débito) é derivado do sinal do valor, não do campo
    `trntype` do OFX — esse campo tem valores variados demais entre bancos
    (CREDIT, DEBIT, PAYMENT, POS, ATM, ...) para mapear com confiança, mas o
    sinal do valor é universal no padrão OFX.
    """
    from ofxparse import OfxParser

    ofx = OfxParser.parse(io.BytesIO(raw_bytes))

    linhas = []
    for conta in ofx.accounts:
        if conta.statement is None:
            continue
        for transacao in conta.statement.transactions:
            valor = float(transacao.amount)
            descricao = (transacao.memo or transacao.payee or "Transação OFX").strip()
            linhas.append({
                "data": transacao.date,
                "descricao": descricao,
                "valor": abs(valor),
                "tipo": "Credito" if valor >= 0 else "Debito",
            })

    return pd.DataFrame(linhas, columns=COLUNAS_PADRAO)


def parse_extrato_tabular(nome_arquivo: str, raw_bytes: bytes) -> pd.DataFrame:
    """Detecta o formato tabular pela extensão do arquivo e devolve um DataFrame padronizado.

    Não cobre PDF — para isso, use `extrair_texto_pdf` (o texto ainda precisa
    passar pelo agente extrator, que não é responsabilidade deste módulo).
    """
    extensao = Path(nome_arquivo).suffix.lower()

    if extensao == ".csv":
        return parse_transacoes_csv(raw_bytes)
    if extensao in (".xlsx", ".xls"):
        return parse_transacoes_xlsx(raw_bytes)
    if extensao in (".ofx", ".qfx"):
        return parse_transacoes_ofx(raw_bytes)

    msg = f"Formato de arquivo não suportado para importação tabular: '{extensao}'"
    raise ValueError(msg)


def extrair_texto_pdf(raw_bytes: bytes) -> str:
    """Extrai todo o texto de um PDF (ex.: extrato bancário exportado em PDF).

    O texto extraído é passado adiante para o agente extrator (LLM) interpretar
    — PDFs de extrato não têm uma tabela fixa e variam demais entre bancos
    para um parser determinístico dar conta de todos.
    """
    from pypdf import PdfReader

    leitor = PdfReader(io.BytesIO(raw_bytes))
    paginas = [pagina.extract_text() or "" for pagina in leitor.pages]
    return "\n".join(paginas).strip()
