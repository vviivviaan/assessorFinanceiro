"""Testes de core/auth_service.py (login, sessões e chaves de API), com SQLite em memória."""
import datetime

import pytest

from assessor_financeiro.core import auth_service as auth
from assessor_financeiro.core import transaction_repository as repo
from assessor_financeiro.core.auth_service import ErroAutenticacao

pytestmark = pytest.mark.usefixtures("banco")


class TestRegistro:
    def test_registra_e_normaliza_o_email(self):
        usuario = auth.registrar("  Vivian@Exemplo.COM ", "senha-forte-1")
        assert usuario.email == "vivian@exemplo.com"

    def test_senha_nao_e_guardada_em_texto(self):
        auth.registrar("a@b.com", "senha-forte-1")
        assert "senha-forte-1" not in repo.get_usuario_por_email("a@b.com").senha_hash

    @pytest.mark.parametrize("email", ["", "sem-arroba", "a@b", "a b@c.com"])
    def test_email_invalido(self, email):
        with pytest.raises(ErroAutenticacao, match="e-mail válido"):
            auth.registrar(email, "senha-forte-1")

    def test_senha_curta(self):
        with pytest.raises(ErroAutenticacao, match="pelo menos 8"):
            auth.registrar("a@b.com", "1234567")

    def test_email_duplicado_mesmo_com_caixa_diferente(self):
        auth.registrar("a@b.com", "senha-forte-1")
        with pytest.raises(ErroAutenticacao, match="Já existe"):
            auth.registrar("A@B.com", "outra-senha-1")

    def test_primeiro_usuario_adota_os_dados_de_antes_do_login(self):
        repo.add_chat_message("user", "antiga", session_id="default_user")
        repo.add_transactions([{"category": "Padaria", "amount": 20.0, "type": "Debito"}], session_id="default_user")
        repo.create_cliente("Cliente Velho", "cliente_x")  # sem dono

        usuario = auth.registrar("a@b.com", "senha-forte-1")
        perfil = auth.session_id_pessoal(usuario.id)

        assert [m.content for m in repo.get_chat_history(perfil, "")] == ["antiga"]
        assert len(repo.get_transactions(perfil)) == 1
        assert repo.get_transactions("default_user") == []
        assert [c.nome for c in repo.list_clientes(usuario.id)] == ["Cliente Velho"]

    def test_segundo_usuario_nao_herda_nada(self):
        auth.registrar("a@b.com", "senha-forte-1")
        repo.add_chat_message("user", "dado novo do default", session_id="default_user")
        segundo = auth.registrar("c@d.com", "senha-forte-2")
        assert repo.get_chat_history(auth.session_id_pessoal(segundo.id), "") == []


class TestLogin:
    def test_login_correto(self):
        criado = auth.registrar("a@b.com", "senha-forte-1")
        assert auth.autenticar(" A@b.com", "senha-forte-1").id == criado.id

    def test_senha_errada_e_email_inexistente_dao_a_mesma_mensagem(self):
        auth.registrar("a@b.com", "senha-forte-1")
        with pytest.raises(ErroAutenticacao) as erro1:
            auth.autenticar("a@b.com", "errada-123")
        with pytest.raises(ErroAutenticacao) as erro2:
            auth.autenticar("naoexiste@b.com", "senha-forte-1")
        assert str(erro1.value) == str(erro2.value)


class TestSessao:
    def test_token_retoma_o_login(self):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        token = auth.criar_sessao(usuario.id)
        assert auth.usuario_da_sessao(token).id == usuario.id

    def test_token_nao_fica_guardado_em_texto_no_banco(self):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        token = auth.criar_sessao(usuario.id)
        assert repo.get_sessao(token) is None  # o banco só conhece o hash

    @pytest.mark.parametrize("token", ["", "inventado", None])
    def test_token_invalido(self, token):
        assert auth.usuario_da_sessao(token) is None

    def test_sair_invalida_o_token(self):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        token = auth.criar_sessao(usuario.id)
        auth.encerrar_sessao(token)
        assert auth.usuario_da_sessao(token) is None

    def test_sessao_expirada_e_recusada_e_removida(self, monkeypatch):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        token = auth.criar_sessao(usuario.id)
        depois = datetime.datetime.now() + datetime.timedelta(days=auth.VALIDADE_SESSAO_DIAS + 1)

        class Relogio(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return depois

        monkeypatch.setattr(auth.datetime, "datetime", Relogio)
        assert auth.usuario_da_sessao(token) is None


class TestChavesDeApi:
    def test_salva_e_recupera_decifrada(self):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        auth.salvar_chave(usuario.id, "groq", "gsk_abcdef123456")
        assert auth.chaves_decifradas(usuario.id) == {"groq": "gsk_abcdef123456"}

    def test_no_banco_a_chave_esta_cifrada(self):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        auth.salvar_chave(usuario.id, "openai", "sk-segredo-123456")
        assert "sk-segredo-123456" not in repo.list_chaves_api(usuario.id)[0].chave_cifrada

    def test_salvar_de_novo_substitui(self):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        auth.salvar_chave(usuario.id, "groq", "chave-antiga-1111")
        auth.salvar_chave(usuario.id, "groq", "chave-nova-2222")
        assert auth.chaves_decifradas(usuario.id) == {"groq": "chave-nova-2222"}
        assert len(repo.list_chaves_api(usuario.id)) == 1

    def test_mascara_mostra_so_os_ultimos_4(self):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        auth.salvar_chave(usuario.id, "groq", "gsk_abcdef123456")
        linha = {c["provedor"]: c for c in auth.chaves_mascaradas(usuario.id)}["groq"]
        assert linha["mascara"] == "••••3456"
        assert "abcdef" not in str(auth.chaves_mascaradas(usuario.id))

    def test_provedor_sem_chave_aparece_como_nao_cadastrado(self):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        linhas = {c["provedor"]: c["salva"] for c in auth.chaves_mascaradas(usuario.id)}
        assert linhas == {"groq": "nao", "openai": "nao", "google": "nao", "anthropic": "nao"}

    def test_remover(self):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        auth.salvar_chave(usuario.id, "groq", "gsk_abcdef123456")
        auth.remover_chave(usuario.id, "groq")
        assert auth.chaves_decifradas(usuario.id) == {}

    def test_chaves_de_um_usuario_nao_aparecem_para_outro(self):
        a = auth.registrar("a@b.com", "senha-forte-1")
        b = auth.registrar("c@d.com", "senha-forte-2")
        auth.salvar_chave(a.id, "groq", "gsk_do_usuario_a_1")
        assert auth.chaves_decifradas(b.id) == {}

    @pytest.mark.parametrize(("provedor", "chave"), [("xpto", "chave-longa-123"), ("groq", "curta"), ("groq", "   ")])
    def test_entradas_invalidas(self, provedor, chave):
        usuario = auth.registrar("a@b.com", "senha-forte-1")
        with pytest.raises(ErroAutenticacao):
            auth.salvar_chave(usuario.id, provedor, chave)

    def test_chave_ilegivel_com_outra_chave_mestra_e_ignorada(self, monkeypatch):
        from cryptography.fernet import Fernet

        from assessor_financeiro.core import security

        usuario = auth.registrar("a@b.com", "senha-forte-1")
        auth.salvar_chave(usuario.id, "groq", "gsk_abcdef123456")
        monkeypatch.setenv("VIVIA_SECRET_KEY", Fernet.generate_key().decode())
        security.limpar_cache_chave_mestra()
        assert auth.chaves_decifradas(usuario.id) == {}
