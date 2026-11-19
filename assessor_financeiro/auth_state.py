"""Login e chaves de API por usuário (Fase 5), como *mixin* do estado principal.

Fica separado de `state.py` só para manter cada arquivo com um assunto; em
tempo de execução tudo isso é parte de `AdvisorState` (o mixin é copiado pra
dentro dele), então a UI acessa tudo por `AdvisorState.<nome>`.

ATENÇÃO: variáveis de estado do Reflex são enviadas ao navegador. Por isso
aqui só entram dados que a própria usuária digitou ou que já são seguros pra
exibir (e-mail, chave MASCARADA). Chaves de API decifradas nunca ficam no
estado — são lidas do banco na hora de chamar o LLM (`_chaves_decifradas`).
"""
import asyncio

import reflex as rx

from assessor_financeiro.core import auth_service
from assessor_financeiro.core.auth_service import ErroAutenticacao


class AuthMixin(rx.State, mixin=True):
    # Token do login (fica no localStorage do navegador; no banco só o hash).
    token_login: str = rx.LocalStorage("", name="vivia_token")

    usuario_id: int = 0
    usuario_email: str = ""

    # "entrar", "criar", "esqueci" (pede o código por e-mail) ou "redefinir" (código + senha nova)
    auth_modo: str = "entrar"
    auth_email: str = ""
    auth_senha: str = ""
    auth_erro: str = ""
    auth_info: str = ""
    auth_codigo: str = ""
    auth_senha_nova: str = ""

    # Alterar senha (dentro das Configurações)
    cfg_senha_atual: str = ""
    cfg_senha_nova: str = ""
    cfg_senha_msg: str = ""
    cfg_senha_ok: bool = False

    mostrar_config: bool = False
    chaves_ui: list[dict[str, str]] = []
    novas_chaves: dict[str, str] = {}
    config_msg: str = ""

    @rx.var
    def logado(self) -> bool:
        return self.usuario_id > 0

    # --- Setters dos formulários ---

    def set_auth_email(self, valor: str):
        self.auth_email = valor

    def set_auth_senha(self, valor: str):
        self.auth_senha = valor

    def set_auth_codigo(self, valor: str):
        self.auth_codigo = valor

    def set_auth_senha_nova(self, valor: str):
        self.auth_senha_nova = valor

    def alternar_auth_modo(self):
        self.auth_modo = "criar" if self.auth_modo == "entrar" else "entrar"
        self.auth_erro = ""
        self.auth_info = ""

    # --- Esqueci minha senha ---

    def ir_para_esqueci_senha(self):
        self.auth_modo = "esqueci"
        self.auth_erro = ""
        self.auth_info = ""
        self.auth_senha = ""

    def voltar_para_login(self):
        self.auth_modo = "entrar"
        self.auth_erro = ""
        self.auth_info = ""
        self.auth_codigo = ""
        self.auth_senha_nova = ""

    def ir_para_codigo_recebido(self):
        """Quem já tem o código (pediu há pouco) vai direto para a tela de senha nova."""
        self.auth_modo = "redefinir"
        self.auth_erro = ""

    async def enviar_codigo_redefinicao(self):
        """Botão 'Enviar código' (e-mail digitado na tela de recuperação)."""
        try:
            await asyncio.to_thread(auth_service.solicitar_redefinicao, self.auth_email)
        except ErroAutenticacao as erro:
            self.auth_erro = str(erro)
            return
        self.auth_erro = ""
        self.auth_codigo = ""
        self.auth_senha_nova = ""
        self.auth_info = (
            "Se esse e-mail tiver uma conta, enviamos um código. "
            "Ele pode demorar um pouco e cair no spam."
        )
        self.auth_modo = "redefinir"

    async def confirmar_redefinicao(self):
        """Botão 'Salvar nova senha' (código recebido + senha nova)."""
        try:
            await asyncio.to_thread(
                auth_service.redefinir_senha,
                self.auth_email,
                self.auth_codigo,
                self.auth_senha_nova,
            )
        except ErroAutenticacao as erro:
            self.auth_erro = str(erro)
            return
        self.auth_codigo = ""
        self.auth_senha_nova = ""
        self.auth_senha = ""
        self.auth_erro = ""
        self.auth_modo = "entrar"
        self.auth_info = "Senha atualizada! Entre com a nova senha."

    # --- Login / cadastro / sair ---

    def _definir_usuario(self, usuario):
        self.usuario_id = usuario.id
        self.usuario_email = usuario.email

    def _restaurar_login(self) -> bool:
        """Retoma o login a partir do token guardado no navegador."""
        usuario = auth_service.usuario_da_sessao(self.token_login)
        if usuario is None:
            self.token_login = ""
            return False
        self._definir_usuario(usuario)
        return True

    def enviar_auth(self):
        """Botão 'Entrar' / 'Criar conta' da tela de login."""
        try:
            if self.auth_modo == "criar":
                usuario = auth_service.registrar(self.auth_email, self.auth_senha)
            else:
                usuario = auth_service.autenticar(self.auth_email, self.auth_senha)
        except ErroAutenticacao as erro:
            self.auth_erro = str(erro)
            self.auth_senha = ""
            return

        self.token_login = auth_service.criar_sessao(usuario.id)
        self._definir_usuario(usuario)
        self.auth_senha = ""
        self.auth_erro = ""
        self._pos_login()

    def sair(self):
        """Encerra o login neste navegador e volta pra tela de entrada."""
        auth_service.encerrar_sessao(self.token_login)
        self.token_login = ""
        self.usuario_id = 0
        self.usuario_email = ""
        self.mostrar_config = False
        self.novas_chaves = {}
        self._limpar_campos_senha_config()
        self._limpar_dados_em_memoria()

    # --- Configurações: chaves de API ---

    def _limpar_campos_senha_config(self):
        self.cfg_senha_atual = ""
        self.cfg_senha_nova = ""
        self.cfg_senha_msg = ""
        self.cfg_senha_ok = False

    def abrir_config(self):
        if self.usuario_id <= 0:
            return
        self.config_msg = ""
        self.novas_chaves = {}
        self._limpar_campos_senha_config()
        self.chaves_ui = auth_service.chaves_mascaradas(self.usuario_id)
        self.mostrar_config = True

    def fechar_config(self):
        self.mostrar_config = False
        self.novas_chaves = {}
        self._limpar_campos_senha_config()

    def set_cfg_senha_atual(self, valor: str):
        self.cfg_senha_atual = valor

    def set_cfg_senha_nova(self, valor: str):
        self.cfg_senha_nova = valor

    async def alterar_senha_conta(self):
        """Botão 'Alterar senha' das Configurações (exige a senha atual)."""
        if self.usuario_id <= 0:
            return
        try:
            await asyncio.to_thread(
                auth_service.alterar_senha,
                self.usuario_id,
                self.cfg_senha_atual,
                self.cfg_senha_nova,
            )
        except ErroAutenticacao as erro:
            self.cfg_senha_ok = False
            self.cfg_senha_msg = str(erro)
            return
        self.cfg_senha_atual = ""
        self.cfg_senha_nova = ""
        self.cfg_senha_ok = True
        self.cfg_senha_msg = "Senha alterada."

    def set_config_aberta(self, aberta: bool):
        if aberta:
            self.abrir_config()
        else:
            self.fechar_config()

    def set_nova_chave(self, provedor: str, valor: str):
        self.novas_chaves = {**self.novas_chaves, provedor: valor}

    def salvar_chave_provedor(self, provedor: str):
        if self.usuario_id <= 0:
            return
        try:
            auth_service.salvar_chave(
                self.usuario_id, provedor, self.novas_chaves.get(provedor, "")
            )
        except ErroAutenticacao as erro:
            self.config_msg = str(erro)
            return
        self.novas_chaves = {k: v for k, v in self.novas_chaves.items() if k != provedor}
        self.chaves_ui = auth_service.chaves_mascaradas(self.usuario_id)
        self.config_msg = "Chave salva (criptografada)."

    def remover_chave_provedor(self, provedor: str):
        if self.usuario_id <= 0:
            return
        auth_service.remover_chave(self.usuario_id, provedor)
        self.chaves_ui = auth_service.chaves_mascaradas(self.usuario_id)
        self.config_msg = "Chave removida."

    def _chaves_decifradas(self) -> dict[str, str]:
        """Chaves do usuário logado, decifradas — só pra repassar ao agente."""
        if self.usuario_id <= 0:
            return {}
        return auth_service.chaves_decifradas(self.usuario_id)
