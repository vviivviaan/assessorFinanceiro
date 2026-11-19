"""Envio de e-mail (usado só para o código de "esqueci minha senha").

Dois jeitos de configurar, por variáveis de ambiente (nenhuma é obrigatória: sem
elas o app funciona normalmente, só não oferece a recuperação por e-mail):

1. Resend (API por HTTPS, funciona no Render gratuito, que bloqueia SMTP):
       RESEND_API_KEY   chave da conta em resend.com
       EMAIL_FROM       remetente (padrão "vivIA <onboarding@resend.dev>"; com esse
                        remetente de teste o Resend só entrega para o e-mail dono da conta)

2. SMTP (uso local ou hospedagem que permita SMTP):
       SMTP_HOST, SMTP_PORT (padrão 587), SMTP_USER, SMTP_PASSWORD, EMAIL_FROM
       (no Gmail: use uma "senha de app", não a senha da conta)

Módulo puro: não importa Reflex nem toca o banco.
"""
import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage

TIMEOUT_SEG = 15
REMETENTE_PADRAO_RESEND = "vivIA <onboarding@resend.dev>"


class ErroEnvioEmail(Exception):
    """Falha ao entregar o e-mail (rede, credencial inválida, remetente recusado...)."""


def _remetente() -> str:
    padrao = REMETENTE_PADRAO_RESEND if os.getenv("RESEND_API_KEY") else os.getenv("SMTP_USER", "")
    return os.getenv("EMAIL_FROM") or padrao


def configurado() -> bool:
    if os.getenv("RESEND_API_KEY"):
        return True
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def _enviar_resend(para: str, assunto: str, texto: str) -> None:
    corpo = json.dumps(
        {"from": _remetente(), "to": [para], "subject": assunto, "text": texto}
    ).encode("utf-8")
    pedido = urllib.request.Request(
        "https://api.resend.com/emails",
        data=corpo,
        method="POST",
        headers={
            "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEG):
            pass
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ErroEnvioEmail(f"Resend recusou ou não respondeu: {erro}") from erro


def _enviar_smtp(para: str, assunto: str, texto: str) -> None:
    mensagem = EmailMessage()
    mensagem["From"] = _remetente()
    mensagem["To"] = para
    mensagem["Subject"] = assunto
    mensagem.set_content(texto)

    host = os.environ["SMTP_HOST"]
    porta = int(os.getenv("SMTP_PORT", "587"))
    try:
        if porta == 465:
            servidor = smtplib.SMTP_SSL(host, porta, timeout=TIMEOUT_SEG, context=ssl.create_default_context())
        else:
            servidor = smtplib.SMTP(host, porta, timeout=TIMEOUT_SEG)
        with servidor:
            if porta != 465:
                servidor.starttls(context=ssl.create_default_context())
            servidor.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            servidor.send_message(mensagem)
    except (smtplib.SMTPException, OSError, ValueError) as erro:
        raise ErroEnvioEmail(f"SMTP falhou: {erro}") from erro


def enviar(para: str, assunto: str, texto: str) -> None:
    """Envia um e-mail de texto simples. Levanta `ErroEnvioEmail` se não der."""
    if os.getenv("RESEND_API_KEY"):
        _enviar_resend(para, assunto, texto)
    elif configurado():
        _enviar_smtp(para, assunto, texto)
    else:
        raise ErroEnvioEmail("Nenhum serviço de e-mail configurado.")
