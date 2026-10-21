"""Testes de core/security.py: hash de senha, tokens e criptografia de chaves."""
import pytest
from cryptography.fernet import Fernet

from assessor_financeiro.core import security


@pytest.fixture(autouse=True)
def chave_mestra(monkeypatch):
    monkeypatch.setenv("VIVIA_SECRET_KEY", Fernet.generate_key().decode())
    security.limpar_cache_chave_mestra()
    yield
    security.limpar_cache_chave_mestra()


class TestSenha:
    def test_senha_correta_confere(self):
        assert security.verificar_senha("minha-senha-123", security.hash_senha("minha-senha-123"))

    def test_senha_errada_nao_confere(self):
        assert not security.verificar_senha("outra", security.hash_senha("minha-senha-123"))

    def test_hash_nao_contem_a_senha(self):
        assert "minha-senha-123" not in security.hash_senha("minha-senha-123")

    def test_mesma_senha_gera_hashes_diferentes(self):
        assert security.hash_senha("abc12345") != security.hash_senha("abc12345")

    @pytest.mark.parametrize("lixo", ["", "abc", "scrypt$1$2", "md5$a$b$c$d$e", "scrypt$x$8$1$zz$zz"])
    def test_hash_invalido_nunca_confere_nem_estoura(self, lixo):
        assert security.verificar_senha("qualquer", lixo) is False


class TestToken:
    def test_tokens_sao_unicos(self):
        assert security.gerar_token() != security.gerar_token()

    def test_hash_do_token_e_estavel_e_diferente_do_token(self):
        token = security.gerar_token()
        assert security.hash_token(token) == security.hash_token(token)
        assert security.hash_token(token) != token


class TestCriptografia:
    def test_cifra_e_decifra(self):
        cifrado = security.cifrar("gsk_minha_chave_secreta")
        assert "gsk_minha_chave_secreta" not in cifrado
        assert security.decifrar(cifrado) == "gsk_minha_chave_secreta"

    def test_chave_mestra_diferente_nao_decifra(self, monkeypatch):
        cifrado = security.cifrar("segredo")
        monkeypatch.setenv("VIVIA_SECRET_KEY", Fernet.generate_key().decode())
        security.limpar_cache_chave_mestra()
        assert security.decifrar(cifrado) is None

    def test_dado_corrompido_devolve_none(self):
        assert security.decifrar("isso-nao-e-fernet") is None

    def test_sem_env_cria_arquivo_da_chave_mestra_e_reusa(self, monkeypatch, tmp_path):
        monkeypatch.delenv("VIVIA_SECRET_KEY", raising=False)
        arquivo = tmp_path / "pasta" / "secret.key"
        monkeypatch.setenv("VIVIA_SECRET_FILE", str(arquivo))
        security.limpar_cache_chave_mestra()
        cifrado = security.cifrar("x" * 10)
        assert arquivo.exists()
        security.limpar_cache_chave_mestra()  # simula reiniciar o app
        assert security.decifrar(cifrado) == "x" * 10
