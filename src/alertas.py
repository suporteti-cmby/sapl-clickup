"""
alertas.py
Envia notificações de prazos por e-mail e/ou Telegram.
"""

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
import requests

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# E-mail
# ------------------------------------------------------------------
class AlertaEmail:
    def __init__(self, smtp_host: str, smtp_port: int, usuario: str, senha: str):
        self.host = smtp_host
        self.port = smtp_port
        self.usuario = usuario
        self.senha = senha

    def enviar(self, destinatarios: list[str], assunto: str, corpo_html: str) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = assunto
            msg["From"] = self.usuario
            msg["To"] = ", ".join(destinatarios)
            msg.attach(MIMEText(corpo_html, "html", "utf-8"))

            with smtplib.SMTP(self.host, self.port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(self.usuario, self.senha)
                smtp.sendmail(self.usuario, destinatarios, msg.as_string())
            logger.info(f"E-mail enviado para {destinatarios}")
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar e-mail: {e}")
            return False

    def montar_html_alerta(self, materias_alerta: list[dict]) -> str:
        """Monta e-mail HTML com tabela de matérias em alerta."""
        linhas = ""
        for m in materias_alerta:
            cor = "#D0021B" if m["status"] == "Atrasado" else "#F5A623"
            linhas += f"""
            <tr>
              <td style="padding:8px;border-bottom:1px solid #eee">{m['titulo']}</td>
              <td style="padding:8px;border-bottom:1px solid #eee">{m['ementa'][:80]}...</td>
              <td style="padding:8px;border-bottom:1px solid #eee">{m['ultima_tramitacao']}</td>
              <td style="padding:8px;border-bottom:1px solid #eee">
                <span style="color:{cor};font-weight:bold">{m['label_prazo']}</span>
              </td>
              <td style="padding:8px;border-bottom:1px solid #eee">
                <a href="{m['url_sapl']}">Ver no SAPL</a>
              </td>
            </tr>"""

        return f"""
        <html><body style="font-family:Arial,sans-serif;color:#333">
        <h2 style="color:#1a1a2e">📋 Alertas de Tramitação — Câmara de Bayeux</h2>
        <p>{date.today().strftime('%d/%m/%Y')} — {len(materias_alerta)} matéria(s) requerem atenção:</p>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead>
            <tr style="background:#1a1a2e;color:white">
              <th style="padding:10px;text-align:left">Matéria</th>
              <th style="padding:10px;text-align:left">Ementa</th>
              <th style="padding:10px;text-align:left">Última tramitação</th>
              <th style="padding:10px;text-align:left">Prazo</th>
              <th style="padding:10px;text-align:left">Link</th>
            </tr>
          </thead>
          <tbody>{linhas}</tbody>
        </table>
        <hr/>
        <p style="font-size:11px;color:#999">
          Sistema SAPL-ClickUp — Câmara Municipal de Bayeux<br/>
          Este é um e-mail automático. Acesse o ClickUp para gerenciar as tarefas.
        </p>
        </body></html>"""


# ------------------------------------------------------------------
# Telegram
# ------------------------------------------------------------------
class AlertaTelegram:
    def __init__(self, bot_token: str, chat_id: str):
        self.token = bot_token
        self.chat_id = chat_id
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def enviar(self, mensagem: str) -> bool:
        try:
            r = requests.post(self.url, json={
                "chat_id": self.chat_id,
                "text": mensagem,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }, timeout=10)
            r.raise_for_status()
            logger.info("Alerta Telegram enviado.")
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar Telegram: {e}")
            return False

    def montar_mensagem(self, materias_alerta: list[dict]) -> str:
        hoje = date.today().strftime("%d/%m/%Y")
        linhas = [f"📋 <b>Alertas de Tramitação — {hoje}</b>\n"]
        for m in materias_alerta:
            emoji = "🔴" if m["status"] == "Atrasado" else "🟡"
            linhas.append(
                f"{emoji} <b>{m['titulo']}</b>\n"
                f"   {m['ementa'][:60]}...\n"
                f"   ⏱ {m['label_prazo']}\n"
                f"   🔗 <a href=\"{m['url_sapl']}\">Ver no SAPL</a>\n"
            )
        return "\n".join(linhas)


# ------------------------------------------------------------------
# Gerenciador unificado
# ------------------------------------------------------------------
class GerenciadorAlertas:
    def __init__(
        self,
        email: Optional[AlertaEmail] = None,
        telegram: Optional[AlertaTelegram] = None,
        destinatarios_email: list[str] = None,
    ):
        self.email = email
        self.telegram = telegram
        self.destinatarios = destinatarios_email or []

    def disparar(self, materias_alerta: list[dict]) -> None:
        if not materias_alerta:
            logger.info("Nenhuma matéria em alerta hoje.")
            return

        atrasadas = [m for m in materias_alerta if m["status"] == "Atrasado"]
        urgentes   = [m for m in materias_alerta if m["status"] == "Urgente"]
        atencao    = [m for m in materias_alerta if m["status"] not in ("Atrasado", "Urgente")]

        logger.info(f"Disparando alertas: {len(atrasadas)} atrasadas, "
                    f"{len(urgentes)} urgentes, {len(atencao)} atenção")

        if self.email and self.destinatarios:
            html = self.email.montar_html_alerta(materias_alerta)
            assunto = f"[SAPL Bayeux] {len(materias_alerta)} matéria(s) requerem atenção — {date.today().strftime('%d/%m/%Y')}"
            self.email.enviar(self.destinatarios, assunto, html)

        if self.telegram:
            msg = self.telegram.montar_mensagem(materias_alerta)
            self.telegram.enviar(msg)
