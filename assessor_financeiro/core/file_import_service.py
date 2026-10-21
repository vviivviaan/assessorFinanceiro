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

ORIGEM_EXTRATO = "extrato"
ORIGEM_FATURA = "fatura"

_CREDITO = {"credito", "crédito"}
_DEBITO = {"debito", "débito"}
# Linhas de fatura de cartão que NÃO são gasto novo: o pagamento da fatura já
# aparece como débito no extrato da conta, então contá-lo de novo duplicaria.
_PALAVRAS_PAGAMENTO_FATURA = ("pagamento", "pgto", "pag fatura", "pagto", "saldo anterior")


class ErroImportacao(ValueError):
    """Problema no conteúdo do arquivo; a mensagem já é amigável pra mostrar no chat."""


FORMATOS_TABULARES_SUPORTADOS = {".csv", ".xlsx", ".xls", ".ofx", ".qfx"}
FORMATOS_SUPORTADOS = FORMATOS_TABULARES_SUPORTADOS | {".pdf"}


def _numero(bruto) -> float:
    """Converte "43.13", "43,13", "1.234,50" ou "R$ 1.234,50" em float (ValueError se não der)."""
    texto = str(bruto).replace("R$", "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def _primeira_linha_e_cabecalho(primeira_linha: list) -> bool:
    """Detecta se a primeira linha é um cabeçalho (ex.: "data,descricao,valor,tipo").

    O arquivo não tem um cabeçalho fixo esperado, mas é comum que exportações
    reais venham com um — em vez de exigir que o usuário sempre remova a
    primeira linha, checamos se a coluna que deveria ser numérica (`valor`)
    de fato converte para número. Se não converter, é texto de cabeçalho, e a
    linha é descartada.
    """
    try:
        _numero(primeira_linha[_INDICE_COLUNA_VALOR])
        return False
    except (ValueError, IndexError):
        return True


def _tentar_numero(valor):
    """Converte para número quando dá; senão devolve como veio (a validação
    em `normalizar_transacoes` aponta a linha problemática com uma mensagem clara)."""
    try:
        return _numero(valor)
    except ValueError:
        return valor


def _padronizar_colunas(bruto: pd.DataFrame) -> pd.DataFrame:
    """Leva uma tabela lida SEM cabeçalho para as colunas padrão.

    Aceita 3 colunas (data, descrição, valor — a coluna `tipo` é opcional e,
    se faltar, será deduzida pelo sinal do valor) ou 4 (com `tipo`), com ou
    sem linha de cabeçalho (detectada automaticamente).
    """
    if bruto.shape[1] < 3:
        raise ErroImportacao(
            "O arquivo precisa ter pelo menos 3 colunas: data, descrição e valor "
            "(a coluna tipo é opcional)."
        )
    bruto = bruto.copy()
    if bruto.shape[1] == 3:
        bruto["tipo"] = ""
    bruto = bruto.iloc[:, : len(COLUNAS_PADRAO)]
    bruto.columns = COLUNAS_PADRAO
    if bruto.empty:
        return bruto

    if _primeira_linha_e_cabecalho(bruto.iloc[0].tolist()):
        bruto = bruto.iloc[1:]

    bruto["descricao"] = bruto["descricao"].astype(str).str.strip()
    bruto["tipo"] = (
        bruto["tipo"].fillna("").astype(str).str.strip().replace({"nan": "", "None": ""})
    )
    bruto["valor"] = bruto["valor"].map(_tentar_numero)
    return bruto.reset_index(drop=True)


def parse_transacoes_csv(raw_bytes: bytes) -> pd.DataFrame:
    """Lê os bytes de um CSV de extrato/fatura e retorna um DataFrame limpo.

    Colunas na ordem: data, descricao, valor e (opcional) tipo. Funciona com
    ou sem linha de cabeçalho (detectada automaticamente).
    """
    bruto = pd.read_csv(
        io.BytesIO(raw_bytes),
        header=None,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8",  # Garante a leitura correta de acentos como 'Crédito'
    )
    return _padronizar_colunas(bruto)


def parse_transacoes_xlsx(raw_bytes: bytes) -> pd.DataFrame:
    """Lê uma planilha Excel (.xlsx/.xls) com o mesmo layout do CSV (com ou sem cabeçalho)."""
    bruto = pd.read_excel(io.BytesIO(raw_bytes), header=None)
    return _padronizar_colunas(bruto)


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


def normalizar_transacoes(df: pd.DataFrame, origem: str = ORIGEM_EXTRATO) -> tuple[pd.DataFrame, int]:
    """Valida e completa as colunas `valor` e `tipo` de um arquivo importado.

    - `valor` precisa ser numérico (aceita vírgula decimal e "R$").
    - `tipo` preenchido precisa ser crédito ou débito; qualquer outra coisa
      (ex.: uma categoria como "supermercado") é rejeitada com a linha do
      problema — antes o gasto entrava no banco e sumia dos totais.
    - `tipo` vazio é deduzido do sinal do valor. Extrato: positivo = crédito
      (entrada), negativo = débito. Fatura de cartão: o contrário (compra
      vem positiva = débito; estorno vem negativo = crédito).
    - Fatura: linhas de pagamento da fatura são descartadas (já contam no
      extrato da conta). Devolve também quantas foram descartadas.
    """
    df = df.copy()
    ignoradas = 0
    linhas = []
    for posicao, linha in enumerate(df.itertuples(index=False), start=1):
        numero_linha = posicao  # posição entre as linhas de dados (sem contar o cabeçalho)
        try:
            valor = _numero(linha.valor)
        except ValueError:
            raise ErroImportacao(
                f"Linha {numero_linha}: o valor '{linha.valor}' não é um número."
            ) from None

        descricao = str(linha.descricao).strip()
        if origem == ORIGEM_FATURA and any(
            p in descricao.lower() for p in _PALAVRAS_PAGAMENTO_FATURA
        ):
            ignoradas += 1
            continue

        tipo_bruto = str(linha.tipo).strip().lower()
        if tipo_bruto in _CREDITO:
            tipo = "Credito"
        elif tipo_bruto in _DEBITO:
            tipo = "Debito"
        elif tipo_bruto in ("", "nan", "none"):
            positivo = valor >= 0
            if origem == ORIGEM_FATURA:
                tipo = "Debito" if positivo else "Credito"
            else:
                tipo = "Credito" if positivo else "Debito"
        else:
            raise ErroImportacao(
                f"Linha {numero_linha}: a coluna de tipo tem '{linha.tipo}', mas só "
                "são aceitos 'Credito' ou 'Debito' (ou deixe vazio que eu deduzo "
                "pelo sinal do valor). Confira se a ordem das colunas é "
                "data, descrição, valor, tipo."
            )
        linhas.append({"data": linha.data, "descricao": descricao, "valor": abs(valor), "tipo": tipo})

    return pd.DataFrame(linhas, columns=COLUNAS_PADRAO), ignoradas


def parse_extrato_tabular(
    nome_arquivo: str, raw_bytes: bytes, origem: str = ORIGEM_EXTRATO
) -> pd.DataFrame:
    """Detecta o formato tabular pela extensão e devolve um DataFrame padronizado e validado.

    Não cobre PDF — para isso, use `extrair_texto_pdf` (o texto ainda precisa
    passar pelo agente extrator, que não é responsabilidade deste módulo).
    `origem` ("extrato" ou "fatura") define como o tipo é deduzido quando
    vem vazio. Use `parse_extrato_com_resumo` pra saber também quantas linhas
    de pagamento de fatura foram descartadas.
    """
    return parse_extrato_com_resumo(nome_arquivo, raw_bytes, origem)[0]


def parse_extrato_com_resumo(
    nome_arquivo: str, raw_bytes: bytes, origem: str = ORIGEM_EXTRATO
) -> tuple[pd.DataFrame, int]:
    extensao = Path(nome_arquivo).suffix.lower()

    if extensao == ".csv":
        df = parse_transacoes_csv(raw_bytes)
    elif extensao in (".xlsx", ".xls"):
        df = parse_transacoes_xlsx(raw_bytes)
    elif extensao in (".ofx", ".qfx"):
        # OFX já traz o tipo pelo sinal; só passa pela validação (e pelo filtro de pagamentos).
        df = parse_transacoes_ofx(raw_bytes)
    else:
        msg = f"Formato de arquivo não suportado para importação tabular: '{extensao}'"
        raise ValueError(msg)

    return normalizar_transacoes(df, origem)


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
