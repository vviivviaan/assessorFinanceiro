"""Testes do agente extrator com LLM de verdade (casos de aresta de linguagem natural).

Estes testes chamam a API do provedor configurado e consomem créditos, por
isso ficam desligados por padrão. Para rodar, com as chaves reais no `.env`:

    # PowerShell
    $env:RUN_LLM_TESTS = "1"; pytest tests/test_extractor_llm.py -v

Como a saída de um LLM pode variar, os testes verificam o que importa para o
sistema (quantidade de itens, valor, tipo) e não o texto exato da categoria,
exceto onde o prompt do extrator define uma categoria obrigatória.
"""
import pytest

from assessor_financeiro.agents.extractor_agent import get_data_extractor_agent

pytestmark = pytest.mark.llm


def extrair(texto: str):
    resposta = get_data_extractor_agent().run(texto)
    return resposta.content.gastos


def test_um_gasto_simples_com_categoria_obrigatoria():
    gastos = extrair("gastei 40 reais na borracharia")
    assert len(gastos) == 1
    assert gastos[0].amount == 40.0
    assert gastos[0].type == "Debito"
    assert gastos[0].category == "Manutenção/Veículo"


def test_nao_duplica_um_unico_gasto():
    gastos = extrair("gastei 20 na padaria")
    assert len(gastos) == 1
    assert gastos[0].amount == 20.0


def test_multiplos_gastos_na_mesma_frase():
    gastos = extrair("Gastei 50 no supermercado hoje e 120 arrumando a bicicleta.")
    assert len(gastos) == 2
    assert sorted(g.amount for g in gastos) == [50.0, 120.0]
    assert all(g.type == "Debito" for g in gastos)


@pytest.mark.parametrize(
    ("frase", "valor"),
    [
        ("gastei quarenta e cinco reais na padaria", 45.0),
        ("paguei cento e vinte reais no mercado", 120.0),
        ("comprei um lanche por vinte reais", 20.0),
    ],
)
def test_valor_por_extenso(frase, valor):
    gastos = extrair(frase)
    assert len(gastos) == 1
    assert gastos[0].amount == valor
    assert gastos[0].type == "Debito"


def test_categoria_fora_da_lista_do_prompt():
    gastos = extrair("paguei 120 reais de mensalidade da academia")
    assert len(gastos) == 1
    assert gastos[0].amount == 120.0
    assert gastos[0].type == "Debito"
    assert gastos[0].category.strip() != ""


def test_receita_vira_credito():
    gastos = extrair("recebi meu salário de 2000")
    assert len(gastos) == 1
    assert gastos[0].amount == 2000.0
    assert gastos[0].type == "Credito"


def test_pergunta_sem_transacao_devolve_lista_vazia():
    assert extrair("Quais as dicas para economizar?") == []
