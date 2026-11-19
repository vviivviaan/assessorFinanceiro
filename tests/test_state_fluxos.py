"""Fluxos do estado (`AdvisorState`) que não dependem de um LLM de verdade:
controle de acesso entre contas, correções pelo chat, exportação e os limites
que protegem o servidor. O LLM é trocado por um `run_with_fallback` falso."""
import asyncio
from types import SimpleNamespace

import pytest
from agno.run.base import RunStatus

import assessor_financeiro.state as modulo_state
from assessor_financeiro.agents.schemas import ItemGasto, ListaGastos
from assessor_financeiro.core import auth_service as auth
from assessor_financeiro.core import transaction_repository as repo
from assessor_financeiro.state import AdvisorState

pytestmark = pytest.mark.usefixtures("banco")


def novo_estado(email="a@b.com"):
    """Estado de uma usuária logada, com uma chave cadastrada e o perfil Pessoal aberto."""
    usuario = auth.registrar(email, "senha-forte-1")
    auth.salvar_chave(usuario.id, "groq", "gsk_chave_de_teste")
    estado = AdvisorState(_reflex_internal_init=True)
    estado.usuario_id = usuario.id
    estado.usuario_email = usuario.email
    estado.session_id_ativo = auth.session_id_pessoal(usuario.id)
    estado._entrar_na_sessao()
    return estado


def rodar(gerador_async):
    """Executa um handler assíncrono (gerador) até o fim."""
    async def consumir():
        async for _ in gerador_async:
            pass
    asyncio.run(consumir())


@pytest.fixture
def llm_falso(monkeypatch):
    """Troca a chamada ao LLM: o extrator devolve `saida["extrator"]` e o
    conselheiro `saida["conselheiro"]`; guarda as mensagens recebidas."""
    saida = {"extrator": ListaGastos(), "conselheiro": "Tudo certo!", "mensagens": []}

    def falso(agent_factory, provider, message, api_keys=None):
        saida["mensagens"].append(message)
        eh_extrator = message.startswith("MENSAGEM DO USUÁRIO:")
        conteudo = saida["extrator"] if eh_extrator else saida["conselheiro"]
        if conteudo is None:
            return None, provider
        status = RunStatus.error if conteudo == "ERRO" else RunStatus.completed
        return SimpleNamespace(content=conteudo, status=status), provider

    monkeypatch.setattr(modulo_state, "run_with_fallback", falso)
    monkeypatch.setattr(modulo_state, "log_llm_call", lambda *a, **k: None)
    return saida


class TestAcessoEntreContas:
    def test_nao_abre_cliente_de_outra_conta(self):
        dona = novo_estado("dona@x.com")
        dona.novo_cliente_nome = "Empresa da Dona"
        dona.criar_cliente()
        session_da_dona = dona.session_id_ativo
        repo.add_transactions(
            [{"category": "Segredo", "amount": 999.0, "type": "Debito"}], session_id=session_da_dona
        )

        intrusa = novo_estado("intrusa@x.com")
        perfil_da_intrusa = intrusa.session_id_ativo
        intrusa.selecionar_cliente(session_da_dona)

        assert intrusa.session_id_ativo == perfil_da_intrusa
        assert intrusa.transacoes_todas == []

    def test_abre_o_proprio_cliente_com_o_nome_do_banco(self):
        estado = novo_estado()
        estado.novo_cliente_nome = "  Padaria   Central  "
        estado.criar_cliente()
        assert estado.cliente_ativo_nome == "Padaria Central"
        assert estado.session_id_ativo.startswith("cliente_")

    def test_sem_login_os_handlers_nao_fazem_nada(self, llm_falso):
        repo.add_transactions([{"category": "X", "amount": 1.0, "type": "Debito"}], session_id="")
        estado = AdvisorState(_reflex_internal_init=True)
        estado.clear_chat()
        estado.escolher_modo("pessoal")
        rodar(estado.submit_message({"chat_input": "gastei 10"}))
        assert len(repo.get_transactions("")) == 1
        assert estado.modo_app == ""
        assert llm_falso["mensagens"] == []

    def test_modo_desconhecido_e_ignorado(self):
        estado = novo_estado()
        estado.escolher_modo("admin")
        assert estado.modo_app != "admin"


class TestChat:
    def test_registra_transacao_e_avisa_o_conselheiro(self, llm_falso):
        estado = novo_estado()
        llm_falso["extrator"] = ListaGastos(
            gastos=[ItemGasto(category="Supermercado", amount=50, type="Debito")]
        )
        rodar(estado.submit_message({"chat_input": "gastei 50 no mercado"}))

        assert [t.category for t in repo.get_transactions(estado.session_id_ativo)] == ["Supermercado"]
        papeis = [m["role"] for m in estado.chat_history]
        assert papeis[-3:] == ["user", "confirmation", "agent"]
        assert "O sistema JÁ REGISTROU: Supermercado R$ 50,00" in llm_falso["mensagens"][-1]
        assert estado.is_loading is False

    def test_correcao_apaga_o_lancamento_e_nao_cria_outro(self, llm_falso):
        estado = novo_estado()
        repo.add_transactions(
            [{"category": "Teste", "amount": 10000.0, "type": "Credito"}],
            session_id=estado.session_id_ativo,
        )
        id_teste = repo.get_transactions(estado.session_id_ativo)[0].id
        llm_falso["extrator"] = ListaGastos(remover_ids=[id_teste, 424242])
        rodar(estado.submit_message({"chat_input": "remova a entrada de 10000"}))

        assert repo.get_transactions(estado.session_id_ativo) == []
        assert estado.saldo_fmt == "R$ 0,00"
        assert "🗑️" in estado.chat_history[-2]["content"]
        assert "JÁ APAGOU" in llm_falso["mensagens"][-1]

    def test_extrator_enxerga_as_transacoes_recentes(self, llm_falso):
        estado = novo_estado()
        repo.add_transactions(
            [{"category": "Aluguel", "amount": 900.0, "type": "Debito"}],
            session_id=estado.session_id_ativo,
        )
        rodar(estado.submit_message({"chat_input": "oi"}))
        entrada_do_extrator = llm_falso["mensagens"][0]
        assert "TRANSAÇÕES JÁ REGISTRADAS" in entrada_do_extrator
        assert "| Debito | 900.00 | Aluguel" in entrada_do_extrator

    @pytest.mark.parametrize("resposta", [None, "ERRO"])
    def test_falha_do_provedor_vira_mensagem_amigavel_e_fica_no_historico(self, llm_falso, resposta):
        estado = novo_estado()
        llm_falso["conselheiro"] = resposta
        rodar(estado.submit_message({"chat_input": "oi"}))

        ultima = estado.chat_history[-1]["content"]
        assert "Não consegui responder agora" in ultima
        assert "ERRO" not in ultima
        salvas = repo.get_chat_history(estado.session_id_ativo, estado.conversa_ativa_id)
        assert salvas[-1].content == ultima
        assert estado.is_loading is False

    def test_sem_chave_pede_para_cadastrar(self, llm_falso, monkeypatch):
        estado = novo_estado()
        auth.remover_chave(estado.usuario_id, "groq")
        for variavel in ("GROQ_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(variavel, raising=False)
        rodar(estado.submit_message({"chat_input": "oi"}))
        assert "cadastre sua chave de API" in estado.chat_history[-1]["content"]
        assert llm_falso["mensagens"] == []

    def test_so_as_mensagens_recentes_vao_para_o_prompt(self, llm_falso, monkeypatch):
        estado = novo_estado()
        for i in range(30):
            estado._add_chat_message(role="user", content=f"mensagem antiga {i}")
        estado._carregar_dados_sessao()
        capturado = {}

        def conselheiro_falso(financial_data, chat_history, provider, api_keys):
            capturado["historico"] = chat_history
            return SimpleNamespace()

        def falso(agent_factory, provider, message, api_keys=None):
            if not message.startswith("MENSAGEM DO USUÁRIO:"):
                agent_factory(provider)
            return SimpleNamespace(content="ok", status=RunStatus.completed), provider

        monkeypatch.setattr(modulo_state, "get_financial_advisor", conselheiro_falso)
        monkeypatch.setattr(modulo_state, "run_with_fallback", falso)
        rodar(estado.submit_message({"chat_input": "oi"}))

        linhas = capturado["historico"].splitlines()
        assert len(linhas) == modulo_state.LIMITE_HISTORICO_CONSELHEIRO
        assert "mensagem antiga 29" in linhas[-1]
        assert "mensagem antiga 5" not in capturado["historico"]


class TestTransacoesERelatorios:
    def _com_duas_transacoes(self):
        estado = novo_estado()
        repo.add_transactions(
            [
                {"category": "Salário", "amount": 2000.0, "type": "Credito"},
                {"category": "=cmd()", "amount": 1234.5, "type": "Debito"},
            ],
            session_id=estado.session_id_ativo,
        )
        estado._carregar_dados_sessao()
        return estado

    def test_lixeira_pede_confirmacao_antes_de_apagar(self):
        estado = self._com_duas_transacoes()
        alvo = next(t for t in estado.transacoes_todas if t["category"] == "Salário")

        estado.pedir_exclusao_transacao(alvo["id"])
        assert estado.exclusao_transacao_id == alvo["id"]
        assert estado.exclusao_transacao_descricao == "Salário · + R$ 2.000,00"
        assert len(repo.get_transactions(estado.session_id_ativo)) == 2

        estado.confirmar_exclusao_transacao()
        assert estado.exclusao_transacao_id == 0
        assert [t.category for t in repo.get_transactions(estado.session_id_ativo)] == ["=cmd()"]

    def test_cancelar_nao_apaga(self):
        estado = self._com_duas_transacoes()
        estado.pedir_exclusao_transacao(estado.transacoes_todas[0]["id"])
        estado.set_dialogo_exclusao_aberto(False)
        estado.confirmar_exclusao_transacao()
        assert len(repo.get_transactions(estado.session_id_ativo)) == 2

    def test_mes_selecionado_no_grafico_continua_apos_recarregar(self):
        estado = self._com_duas_transacoes()
        mes_atual = estado.relatorio_mensal[-1]
        estado.selecionar_mes_relatorio({"activeTooltipIndex": len(estado.relatorio_mensal) - 1})
        assert estado.relatorio_mes_selecionado == mes_atual["chave"]
        assert estado.relatorio_gastos_fmt_mes == "R$ 1.234,50"

        estado._carregar_dados_sessao()
        assert estado.relatorio_mes_selecionado == mes_atual["chave"]

        estado.selecionar_mes_relatorio({"activeLabel": mes_atual["mes"]})  # clicar de novo limpa
        assert estado.relatorio_mes_selecionado == ""

    def test_exportacao_no_formato_do_excel_em_portugues(self, monkeypatch):
        estado = self._com_duas_transacoes()
        capturado = {}
        monkeypatch.setattr(
            modulo_state.rx, "download", lambda data, filename: capturado.update(data=data, nome=filename)
        )
        estado.exportar_relatorio_csv()

        linhas = capturado["data"].lstrip("﻿").splitlines()
        assert linhas[0] == "Data;Hora;Categoria;Tipo;Valor (R$)"
        corpo = "\n".join(linhas[1:])
        assert ";Salário;Receita;2000,00" in corpo
        assert ";'=cmd();Gasto;-1234,50" in corpo  # não vira fórmula no Excel
        assert capturado["nome"] == "relatorio_vivIA.csv"

    def test_resumo_do_conselheiro_tem_o_detalhe_por_mes(self):
        estado = self._com_duas_transacoes()
        assert "Entradas e saídas por mês" in estado.database_summary
        assert "entradas R$ 2000.00 | saídas R$ 1234.50" in estado.database_summary
