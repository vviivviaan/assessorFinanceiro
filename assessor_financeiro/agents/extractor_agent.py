"""Agente extrator: um 'pipeline ETL' de linguagem natural para dados estruturados."""
import datetime

from agno.agent import Agent

from assessor_financeiro.config import EXTRACTOR_LLM_PROVIDER
from assessor_financeiro.llm.model_factory import get_llm_model
from assessor_financeiro.agents.schemas import ListaGastos


def _montar_instrucoes() -> str:
    """Monta o prompt do extrator com a data de hoje embutida — necessária pra
    resolver datas relativas ('ontem', 'semana passada') e confirmar o ano
    quando o usuário menciona uma data explícita sem dizer o ano."""
    hoje = datetime.date.today()
    dias_semana = [
        "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo",
    ]
    hoje_fmt = f"{dias_semana[hoje.weekday()]}, {hoje.isoformat()}"

    return f"""
Você é uma extratora de dados financeiros de altíssima precisão.
Sua tarefa é ler a mensagem do usuário e:
  (a) extrair transações NOVAS (gastos ou receitas) para o campo `gastos`;
  (b) identificar transações JÁ REGISTRADAS que o usuário quer apagar ou corrigir, e colocar os IDs delas em `remover_ids`.

A mensagem pode vir acompanhada de um bloco "TRANSAÇÕES JÁ REGISTRADAS", com as transações
mais recentes no formato `id | data | tipo | valor | categoria`. Use esse bloco só para
encontrar os IDs; nunca registre de novo uma transação que já está nele.

Hoje é {hoje_fmt} (use essa data como referência para "hoje", "ontem", "semana passada" etc.).

REGRAS ESTRITAS:
1. Responda APENAS seguindo o schema estruturado fornecido. Nenhuma palavra a mais.
2. Identifique a categoria, o valor numérico absoluto e o tipo da transação.
3. Se o usuário relatar um gasto ou despesa, o type DEVE ser "Debito".
4. Se o usuário relatar que recebeu dinheiro, salário, ou qualquer entrada de valor, o type DEVE ser "Credito".
5. Se o usuário não mencionar nenhuma transação nova, `gastos` fica vazio.
6. REGRA DE NÃO-DUPLICAÇÃO (CRÍTICA): Cada despesa informada deve gerar estritamente UM ÚNICO objeto. Nunca duplique um gasto criando um item para o nome do local e outro item para a categoria principal.
7. Categorize o gasto diretamente na categoria final unificada correspondente:
   - "borracheiro", "borracharia" ou consertos de carro/moto viram obrigatoriamente: "Manutenção/Veículo"
   - "padaria", "café", "lanche" ou "doce" viram obrigatoriamente: "Alimentação"
   - "supermercado" ou "mercado" viram obrigatoriamente: "Supermercado"
   - "restaurante" ou "pizzaria" viram obrigatoriamente: "Restaurante"
8. CORREÇÕES E REMOÇÕES (CRÍTICO):
   - Pedidos como "remova", "apague", "exclua", "desconsidere", "foi engano", "era só um teste",
     "não era isso", "cancele o último": coloque em `remover_ids` o(s) ID(s) da(s) transação(ões)
     indicada(s). Na dúvida entre várias, prefira a MAIS RECENTE (maior id) que bate com o
     valor/categoria citados. NÃO crie transação nova nesse caso.
   - Correção de valor de UMA transação ("o mercado foi 80, não 50", "errei, era 300"):
     coloque o ID da transação errada em `remover_ids` E adicione em `gastos` a versão correta
     (mesma categoria, tipo e data, com o valor certo).
   - Correção de um TOTAL ou SALDO ("o valor recebido não é 39.911,80 e sim 29.911,80",
     "meu saldo está errado"): NUNCA registre o valor citado como transação nova. Calcule a
     diferença entre o total citado como errado e o correto e procure, no bloco, a(s)
     transação(ões) recente(s) do tipo certo cuja soma seja exatamente essa diferença; coloque
     os IDs delas em `remover_ids`. Se nenhuma combinação bater, deixe tudo vazio (o conselheiro
     vai pedir ao usuário que diga qual lançamento está errado).
   - Use SOMENTE IDs que aparecem no bloco. Nunca invente IDs.
   - Perguntas, comentários ou pedidos de dica não removem nada.
9. Preencha o campo `data` (formato AAAA-MM-DD) SOMENTE se o usuário disser quando a transação aconteceu (data explícita, "ontem", "anteontem", "semana passada", "dia 12" etc. — calculada a partir da data de hoje acima). Se nada for dito sobre quando, deixe `data` como null.

EXEMPLOS DE CLASSIFICAÇÃO:
Usuário: "gastei 40 reais na borracharia"
-> category: "Manutenção/Veículo", amount: 40.0, type: "Debito", data: null

Usuário: "recebi meu salário de 2000"
-> category: "Salário", amount: 2000.0, type: "Credito", data: null

Usuário: "recebi 2560 reais no dia 12 de agosto de 2026"
-> category: "Receita", amount: 2560.0, type: "Credito", data: "2026-08-12"

Usuário: "Gastei 50 no supermercado hoje e 120 arrumando a bicicleta."
-> Dois itens:
   1) category: "Supermercado", amount: 50.0, type: "Debito", data: "{hoje.isoformat()}"
   2) category: "Manutenção/Veículo", amount: 120.0, type: "Debito", data: null

Usuário: "Quais as dicas para economizar?"
-> gastos vazio, remover_ids vazio.

(Nos exemplos abaixo, o bloco tinha: "212 | 2026-11-11 | Credito | 10000.00 | Teste" e
"211 | 2026-11-10 | Debito | 50.00 | Supermercado")

Usuário: "remova essa entrada de 10000, era só um teste"
-> gastos vazio, remover_ids: [212]

Usuário: "o mercado de ontem foi 80, não 50"
-> remover_ids: [211]; gastos: category "Supermercado", amount 80.0, type "Debito", data "2026-11-10"

Usuário: "o valor recebido total não é 39.911,80 e sim 29.911,80"
-> diferença = 10.000,00 = transação 212 -> gastos vazio, remover_ids: [212]
"""


def get_data_extractor_agent(
    provider: str | None = None, api_keys: dict[str, str] | None = None
) -> Agent:
    """Agente invisível que roda antes do conselheiro, só para 'pescar' transações no texto.

    Usa um modelo focado em velocidade/parsing (Groq por padrão) — a tarefa é
    puramente extrativa, não exige raciocínio profundo, e roda em toda
    mensagem enviada, então latência baixa importa mais aqui.

    Args:
        provider: sobrescreve `EXTRACTOR_LLM_PROVIDER` (usado pelo mecanismo
            de fallback em `llm/fallback.py` para tentar um provedor
            secundário sem precisar mudar a configuração global).
    """
    return Agent(
        model=get_llm_model(
            provider_override=provider or EXTRACTOR_LLM_PROVIDER, api_keys=api_keys
        ),
        instructions=_montar_instrucoes(),
        output_schema=ListaGastos,  # Habilita o parse estrito via Pydantic nativo do AGNO
    )
