"""Testes de "esqueci minha senha", "alterar senha" e do envio de e-mail (sem rede de verdade)."""
import re

import pytest

from assessor_financeiro.core import auth_service as auth
from assessor_financeiro.core import email_service, security
from assessor_financeiro.core import transaction_repository as repo
from assessor_financeiro.core.auth_service import ErroAutenticacao

pytestmark = pytest.mark.usefixtures("banco")


@pytest.fixture
def caixa_de_entrada(monkeypatch):
    """Finge um serviço de e-mail configurado e guarda o que seria enviado."""
    enviados = []
    monkeypatch.setattr(email_service, "configurado", lambda: True)
    monkeypatch.setattr(
        email_service, "enviar", lambda para, assunto, texto: enviados.append((para, assunto, texto))
    )
    return enviados


def _codigo_do_email(enviados) -> str:
    return re.search(r"código: ([A-Z0-9]{4}-[A-Z0-9]{4})", enviados[-1][2]).group(1)


class TestEsqueciMinhaSenha:
    def test_fluxo_completo(self, caixa_de_entrada):
        usuario = auth.registrar("a@b.com", "senha-antiga-1")
        auth.solicitar_redefinicao("  A@B.com ")

        assert len(caixa_de_entrada) == 1
        assert caixa_de_entrada[0][0] == "a@b.com"
        auth.redefinir_senha("a@b.com", _codigo_do_email(caixa_de_entrada), "senha-nova-22")

        assert auth.autenticar("a@b.com", "senha-nova-22").id == usuario.id
        with pytest.raises(ErroAutenticacao):
            auth.autenticar("a@b.com", "senha-antiga-1")

    def test_aceita_codigo_em_minusculas_e_sem_hifen(self, caixa_de_entrada):
        auth.registrar("a@b.com", "senha-antiga-1")
        auth.solicitar_redefinicao("a@b.com")
        codigo = _codigo_do_email(caixa_de_entrada).lower().replace("-", " ")
        auth.redefinir_senha("a@b.com", codigo, "senha-nova-22")
        auth.autenticar("a@b.com", "senha-nova-22")

    def test_email_sem_conta_nao_envia_nada_e_nao_revela(self, caixa_de_entrada):
        auth.solicitar_redefinicao("ninguem@b.com")  # não levanta erro
        assert caixa_de_entrada == []

    def test_sem_servico_de_email_avisa(self, monkeypatch):
        monkeypatch.setattr(email_service, "configurado", lambda: False)
        auth.registrar("a@b.com", "senha-antiga-1")
        with pytest.raises(ErroAutenticacao, match="não está configurada"):
            auth.solicitar_redefinicao("a@b.com")

    def test_email_invalido(self, caixa_de_entrada):
        with pytest.raises(ErroAutenticacao, match="e-mail válido"):
            auth.solicitar_redefinicao("sem-arroba")

    def test_falha_no_envio_vira_mensagem_amigavel(self, monkeypatch):
        monkeypatch.setattr(email_service, "configurado", lambda: True)

        def quebra(*_):
            raise email_service.ErroEnvioEmail("rede caiu")

        monkeypatch.setattr(email_service, "enviar", quebra)
        auth.registrar("a@b.com", "senha-antiga-1")
        with pytest.raises(ErroAutenticacao, match="Não foi possível enviar"):
            auth.solicitar_redefinicao("a@b.com")

    def test_limite_de_pedidos_de_codigo(self, caixa_de_entrada):
        auth.registrar("a@b.com", "senha-antiga-1")
        for _ in range(auth.MAX_PEDIDOS_CODIGO):
            auth.solicitar_redefinicao("a@b.com")
        with pytest.raises(ErroAutenticacao, match="Muitas tentativas"):
            auth.solicitar_redefinicao("a@b.com")
        assert len(caixa_de_entrada) == auth.MAX_PEDIDOS_CODIGO

    def test_codigo_errado_e_mensagem_generica(self, caixa_de_entrada):
        auth.registrar("a@b.com", "senha-antiga-1")
        with pytest.raises(ErroAutenticacao, match="inválido ou expirado"):
            auth.redefinir_senha("a@b.com", "AAAA-BBBB", "senha-nova-22")
        with pytest.raises(ErroAutenticacao, match="inválido ou expirado"):
            auth.redefinir_senha("naoexiste@b.com", "AAAA-BBBB", "senha-nova-22")

    def test_codigo_so_vale_uma_vez(self, caixa_de_entrada):
        auth.registrar("a@b.com", "senha-antiga-1")
        auth.solicitar_redefinicao("a@b.com")
        codigo = _codigo_do_email(caixa_de_entrada)
        auth.redefinir_senha("a@b.com", codigo, "senha-nova-22")
        with pytest.raises(ErroAutenticacao, match="inválido ou expirado"):
            auth.redefinir_senha("a@b.com", codigo, "outra-senha-33")

    def test_codigo_de_outra_conta_nao_serve(self, caixa_de_entrada):
        auth.registrar("a@b.com", "senha-antiga-1")
        auth.registrar("c@d.com", "senha-antiga-2")
        auth.solicitar_redefinicao("a@b.com")
        codigo_a = _codigo_do_email(caixa_de_entrada)
        with pytest.raises(ErroAutenticacao, match="inválido ou expirado"):
            auth.redefinir_senha("c@d.com", codigo_a, "senha-nova-22")

    def test_senha_nova_curta_nao_gasta_tentativa_nem_troca(self, caixa_de_entrada):
        auth.registrar("a@b.com", "senha-antiga-1")
        auth.solicitar_redefinicao("a@b.com")
        codigo = _codigo_do_email(caixa_de_entrada)
        with pytest.raises(ErroAutenticacao, match="pelo menos 8"):
            auth.redefinir_senha("a@b.com", codigo, "curta")
        auth.autenticar("a@b.com", "senha-antiga-1")  # continua a antiga
        auth.redefinir_senha("a@b.com", codigo, "senha-nova-22")  # e o código segue valendo

    def test_bloqueia_apos_varias_tentativas_mesmo_com_codigo_certo(self, caixa_de_entrada):
        auth.registrar("a@b.com", "senha-antiga-1")
        auth.solicitar_redefinicao("a@b.com")
        codigo = _codigo_do_email(caixa_de_entrada)
        for _ in range(auth.MAX_TENTATIVAS):
            with pytest.raises(ErroAutenticacao, match="inválido"):
                auth.redefinir_senha("a@b.com", "ZZZZ-ZZZZ", "senha-nova-22")
        with pytest.raises(ErroAutenticacao, match="Muitas tentativas"):
            auth.redefinir_senha("a@b.com", codigo, "senha-nova-22")

    def test_encerra_os_logins_antigos(self, caixa_de_entrada):
        usuario = auth.registrar("a@b.com", "senha-antiga-1")
        token = auth.criar_sessao(usuario.id)
        auth.solicitar_redefinicao("a@b.com")
        auth.redefinir_senha("a@b.com", _codigo_do_email(caixa_de_entrada), "senha-nova-22")
        assert auth.usuario_da_sessao(token) is None

    def test_libera_o_bloqueio_de_login(self, caixa_de_entrada):
        auth.registrar("a@b.com", "senha-antiga-1")
        for _ in range(auth.MAX_TENTATIVAS):
            with pytest.raises(ErroAutenticacao):
                auth.autenticar("a@b.com", "errada-123")
        auth.solicitar_redefinicao("a@b.com")
        auth.redefinir_senha("a@b.com", _codigo_do_email(caixa_de_entrada), "senha-nova-22")
        auth.autenticar("a@b.com", "senha-nova-22")

    def test_dados_e_chaves_continuam_depois_da_troca(self, caixa_de_entrada):
        usuario = auth.registrar("a@b.com", "senha-antiga-1")
        auth.salvar_chave(usuario.id, "groq", "gsk_chave_de_teste_123")
        auth.solicitar_redefinicao("a@b.com")
        auth.redefinir_senha("a@b.com", _codigo_do_email(caixa_de_entrada), "senha-nova-22")
        assert auth.chaves_decifradas(usuario.id) == {"groq": "gsk_chave_de_teste_123"}


class TestCodigoSemEstado:
    def test_expira_e_depende_do_hash_da_senha(self):
        t = 1_000_000.0
        codigo = security.codigo_redefinicao("a@b.com", "hash-1", agora=t)
        assert security.codigo_redefinicao_valido("a@b.com", "hash-1", codigo, agora=t)
        # na janela seguinte ainda vale (15 a 30 minutos no total)
        assert security.codigo_redefinicao_valido(
            "a@b.com", "hash-1", codigo, agora=t + security.JANELA_CODIGO_SEG
        )
        # depois disso expira
        assert not security.codigo_redefinicao_valido(
            "a@b.com", "hash-1", codigo, agora=t + 3 * security.JANELA_CODIGO_SEG
        )
        # outro hash de senha (senha trocada) invalida o código
        assert not security.codigo_redefinicao_valido("a@b.com", "hash-2", codigo, agora=t)

    def test_formato_e_vazio(self):
        codigo = security.codigo_redefinicao("a@b.com", "hash-1")
        assert re.fullmatch(r"[A-HJ-NP-Z2-9]{8}", codigo)
        assert not security.codigo_redefinicao_valido("a@b.com", "hash-1", "")
        assert not security.codigo_redefinicao_valido("a@b.com", "hash-1", None)


class TestAlterarSenha:
    def test_troca_com_a_senha_atual(self):
        usuario = auth.registrar("a@b.com", "senha-antiga-1")
        auth.alterar_senha(usuario.id, "senha-antiga-1", "senha-nova-22")
        auth.autenticar("a@b.com", "senha-nova-22")

    def test_senha_atual_errada(self):
        usuario = auth.registrar("a@b.com", "senha-antiga-1")
        with pytest.raises(ErroAutenticacao, match="atual está incorreta"):
            auth.alterar_senha(usuario.id, "errada-123", "senha-nova-22")
        auth.autenticar("a@b.com", "senha-antiga-1")

    def test_nova_curta_ou_igual_a_atual(self):
        usuario = auth.registrar("a@b.com", "senha-antiga-1")
        with pytest.raises(ErroAutenticacao, match="pelo menos 8"):
            auth.alterar_senha(usuario.id, "senha-antiga-1", "curta")
        with pytest.raises(ErroAutenticacao, match="diferente"):
            auth.alterar_senha(usuario.id, "senha-antiga-1", "senha-antiga-1")

    def test_limite_de_tentativas_com_senha_atual_errada(self):
        usuario = auth.registrar("a@b.com", "senha-antiga-1")
        for _ in range(auth.MAX_TENTATIVAS):
            with pytest.raises(ErroAutenticacao, match="incorreta"):
                auth.alterar_senha(usuario.id, "errada-123", "senha-nova-22")
        with pytest.raises(ErroAutenticacao, match="Muitas tentativas"):
            auth.alterar_senha(usuario.id, "senha-antiga-1", "senha-nova-22")

    def test_mantem_o_login_atual(self):
        usuario = auth.registrar("a@b.com", "senha-antiga-1")
        token = auth.criar_sessao(usuario.id)
        auth.alterar_senha(usuario.id, "senha-antiga-1", "senha-nova-22")
        assert auth.usuario_da_sessao(token).id == usuario.id


class TestEnvioDeEmail:
    @pytest.fixture(autouse=True)
    def _sem_config(self, monkeypatch):
        for nome in ("RESEND_API_KEY", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_PORT", "EMAIL_FROM"):
            monkeypatch.delenv(nome, raising=False)

    def test_sem_variaveis_nao_esta_configurado(self):
        assert not email_service.configurado()
        with pytest.raises(email_service.ErroEnvioEmail):
            email_service.enviar("a@b.com", "x", "y")

    def test_resend_envia_json_com_a_chave(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_teste")
        capturado = {}

        class Resposta:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def falso_urlopen(pedido, timeout):
            capturado["url"] = pedido.full_url
            capturado["auth"] = pedido.get_header("Authorization")
            capturado["corpo"] = pedido.data.decode()
            return Resposta()

        monkeypatch.setattr(email_service.urllib.request, "urlopen", falso_urlopen)
        assert email_service.configurado()
        email_service.enviar("a@b.com", "Assunto", "Texto")
        assert capturado["url"] == "https://api.resend.com/emails"
        assert capturado["auth"] == "Bearer re_teste"
        assert '"to": ["a@b.com"]' in capturado["corpo"]

    def test_resend_com_erro_vira_erro_de_envio(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_teste")

        def quebra(*_a, **_k):
            raise email_service.urllib.error.URLError("sem rede")

        monkeypatch.setattr(email_service.urllib.request, "urlopen", quebra)
        with pytest.raises(email_service.ErroEnvioEmail):
            email_service.enviar("a@b.com", "x", "y")

    def test_smtp_usa_starttls_e_login(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.exemplo.com")
        monkeypatch.setenv("SMTP_USER", "eu@exemplo.com")
        monkeypatch.setenv("SMTP_PASSWORD", "senha-de-app")
        chamadas = []

        class FalsoSMTP:
            def __init__(self, host, porta, timeout):
                chamadas.append(("conectar", host, porta))

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def starttls(self, context):
                chamadas.append(("starttls",))

            def login(self, usuario, senha):
                chamadas.append(("login", usuario))

            def send_message(self, mensagem):
                chamadas.append(("enviar", mensagem["To"], mensagem["From"]))

        monkeypatch.setattr(email_service.smtplib, "SMTP", FalsoSMTP)
        email_service.enviar("a@b.com", "Assunto", "Texto")
        assert chamadas == [
            ("conectar", "smtp.exemplo.com", 587),
            ("starttls",),
            ("login", "eu@exemplo.com"),
            ("enviar", "a@b.com", "eu@exemplo.com"),
        ]
