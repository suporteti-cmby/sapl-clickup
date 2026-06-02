"""
sync.py
Script principal de sincronização SAPL → ClickUp.
Pode ser executado diretamente ou via agendador (cron / APScheduler).

Uso:
    python sync.py                    # roda uma vez
    python sync.py --modo daemon      # roda em loop contínuo
    python sync.py --apenas-alertas   # só verifica prazos, sem sync completa
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from sapl_client import SAPLClient
from clickup_client import ClickUpClient
from prazos import (
    calcular_prazo, avaliar_prazo, STATUS_CLICKUP,
    deve_alertar, StatusPrazo,
)
from alertas import AlertaEmail, AlertaTelegram, GerenciadorAlertas

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("../logs/sync.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Carregar configurações
# ------------------------------------------------------------------
load_dotenv(dotenv_path=Path(__file__).parent.parent / "config" / ".env")

CLICKUP_API_KEY = os.getenv("CLICKUP_API_KEY", "")
SAPL_BASE_URL   = os.getenv("SAPL_BASE_URL", "https://sapl.bayeux.pb.leg.br")
SYNC_INTERVAL   = int(os.getenv("SYNC_INTERVAL_MINUTES", "30"))
ALERTAR_DIAS    = [int(d) for d in os.getenv("ALERTAR_DIAS_ANTES", "7,3,1").split(",")]

# Mapeamento setor → list_id no ClickUp
# Carregado do .env ou do arquivo ids_gerados.json
def carregar_listas() -> dict:
    ids_file = Path(__file__).parent.parent / "config" / "ids_gerados.json"
    if ids_file.exists():
        with open(ids_file) as f:
            data = json.load(f)
            return data.get("lists", {})

    return {
        "LIST_SECRETARIA":   os.getenv("LIST_SECRETARIA", ""),
        "LIST_COMISSOES":    os.getenv("LIST_COMISSOES", ""),
        "LIST_PROCURADORIA": os.getenv("LIST_PROCURADORIA", ""),
        "LIST_GABINETES":    os.getenv("LIST_GABINETES", ""),
        "LIST_MESA_DIRETORA":os.getenv("LIST_MESA_DIRETORA", ""),
        "LIST_EXECUTIVO":    os.getenv("LIST_EXECUTIVO", ""),
    }

# Regra de qual setor recebe cada tipo de matéria
# Ajuste conforme o regimento interno da Câmara de Bayeux
TIPO_PARA_SETOR = {
    "PL":   "LIST_SECRETARIA",
    "PLC":  "LIST_SECRETARIA",
    "PDL":  "LIST_SECRETARIA",
    "PR":   "LIST_SECRETARIA",
    "REQ":  "LIST_SECRETARIA",
    "IND":  "LIST_GABINETES",
    "MOC":  "LIST_GABINETES",
    # Padrão
    "DEFAULT": "LIST_SECRETARIA",
}


def resolver_list_id(tipo_sigla: str, listas: dict) -> str:
    chave = TIPO_PARA_SETOR.get(tipo_sigla.upper(), TIPO_PARA_SETOR["DEFAULT"])
    return listas.get(chave, "")


def montar_descricao(materia: dict, tramitacao: dict, prazo_info: dict) -> str:
    """Monta o corpo da tarefa no ClickUp."""
    linhas = [
        f"**Matéria:** {materia['titulo']}",
        f"**Tipo:** {materia['tipo_descricao']}",
        f"**Ementa:** {materia['ementa']}",
        "",
        f"**Data de apresentação:** {materia['data_apresentacao'] or 'N/D'}",
        f"**Prazo:** {prazo_info['label']}",
        "",
        "**Última tramitação:**",
    ]
    if tramitacao:
        linhas += [
            f"- Data: {tramitacao.get('data_tramitacao', 'N/D')}",
            f"- Unidade: {tramitacao.get('unidade_tramitacao_destino', {}).get('comissao', {}).get('nome', '') or tramitacao.get('unidade_tramitacao_destino', {}).get('orgao', {}).get('nome', '') or 'N/D'}",
            f"- Status: {tramitacao.get('status', {}).get('descricao', 'N/D') if isinstance(tramitacao.get('status'), dict) else 'N/D'}",
            f"- Turno: {tramitacao.get('turno', 'N/D')}",
        ]
    linhas += ["", f"🔗 [Ver no SAPL]({materia['url_sapl']})"]
    return "\n".join(linhas)


# ------------------------------------------------------------------
# Sincronização principal
# ------------------------------------------------------------------
def sincronizar():
    logger.info("=" * 60)
    logger.info("Iniciando sincronização SAPL → ClickUp")
    logger.info("=" * 60)

    if not CLICKUP_API_KEY:
        logger.error("CLICKUP_API_KEY não configurada. Abortando.")
        return

    sapl = SAPLClient(SAPL_BASE_URL)
    clickup = ClickUpClient(CLICKUP_API_KEY)
    listas = carregar_listas()

    # Cache de IDs de campos por list
    cache_campos: dict[str, dict] = {}

    # Coletar matérias para alerta
    materias_para_alertar = []

    # 1. Buscar todas as matérias ativas do SAPL
    logger.info("Buscando matérias em tramitação no SAPL...")
    try:
        materias_brutas = sapl.listar_todas_materias_ativas()
    except Exception as e:
        logger.error(f"Falha ao consultar SAPL: {e}")
        return

    logger.info(f"Total: {len(materias_brutas)} matéria(s) encontrada(s)")

    criadas = 0
    atualizadas = 0
    erros = 0

    for materia_bruta in materias_brutas:
        try:
            materia = sapl.normalizar_materia(materia_bruta)
            sapl_id = materia["id"]
            tipo_sigla = materia["tipo_nome"] or "DEFAULT"

            # Resolver qual list recebe essa matéria
            list_id = resolver_list_id(tipo_sigla, listas)
            if not list_id:
                logger.warning(f"  List não configurada para tipo {tipo_sigla}, pulando {materia['titulo']}")
                continue

            # Buscar última tramitação
            tram = sapl.ultima_tramitacao(sapl_id)

            # Calcular prazo
            prazo_date = calcular_prazo(materia["data_apresentacao"] or date.today().isoformat(), tipo_sigla)
            prazo_info = avaliar_prazo(prazo_date, concluido=not materia["em_tramitacao"])
            status_clickup = STATUS_CLICKUP[prazo_info["status"]]

            # Descrição da tarefa
            descricao = montar_descricao(materia, tram, prazo_info)

            # Tags
            tags = [tipo_sigla, str(materia["ano"])]
            if prazo_info["status"] == StatusPrazo.ATRASADO:
                tags.append("atrasado")
            elif prazo_info["status"] in (StatusPrazo.URGENTE, StatusPrazo.ATENCAO):
                tags.append("atenção")

            # Cache de campos da list
            if list_id not in cache_campos:
                cache_campos[list_id] = clickup.obter_ids_campos(list_id)
            ids_campos = cache_campos[list_id]

            # Montar campos customizados
            localizacao = ""
            ultima_tram_texto = ""
            if tram:
                dest = tram.get("unidade_tramitacao_destino", {})
                if isinstance(dest, dict):
                    localizacao = (
                        dest.get("comissao", {}).get("nome", "")
                        or dest.get("orgao", {}).get("nome", "")
                        or dest.get("parlamentar", {}).get("nome_parlamentar", "")
                        or ""
                    )
                status_tram = tram.get("status", {})
                ultima_tram_texto = status_tram.get("descricao", "") if isinstance(status_tram, dict) else ""

            campos = clickup.montar_campos_sapl(
                numero_sapl=f"{materia['numero']}/{materia['ano']}",
                tipo=f"{tipo_sigla} — {materia['tipo_descricao']}",
                ementa=materia["ementa"],
                ultima_tramitacao=ultima_tram_texto,
                localizacao=localizacao,
                data_protocolo=date.fromisoformat(materia["data_apresentacao"]) if materia["data_apresentacao"] else None,
                prazo_final=prazo_date,
                url_sapl=materia["url_sapl"],
                sapl_id=sapl_id,
                ids_campos=ids_campos,
            )

            # Verificar se tarefa já existe
            tarefa_existente = clickup.buscar_tarefa_por_sapl_id(list_id, sapl_id)

            if tarefa_existente:
                # Atualizar status e prazo
                clickup.atualizar_tarefa(
                    task_id=tarefa_existente["id"],
                    status=status_clickup,
                    prazo=prazo_date,
                    descricao=descricao,
                )
                # Adicionar comentário se tramitação mudou
                status_anterior = tarefa_existente.get("status", {}).get("status", "")
                if status_clickup != status_anterior:
                    clickup.adicionar_comentario(
                        tarefa_existente["id"],
                        f"🔄 Status atualizado: **{status_anterior}** → **{status_clickup}**\n{prazo_info['label']}",
                    )
                atualizadas += 1
            else:
                # Criar nova tarefa
                clickup.criar_tarefa(
                    list_id=list_id,
                    titulo=materia["titulo"],
                    descricao=descricao,
                    status=status_clickup,
                    prazo=prazo_date,
                    tags=tags,
                    campos_customizados=campos,
                )
                criadas += 1

            # Verificar se deve disparar alerta
            if deve_alertar(prazo_info.get("dias_restantes"), ALERTAR_DIAS):
                materias_para_alertar.append({
                    "titulo": materia["titulo"],
                    "ementa": materia["ementa"],
                    "status": prazo_info["status"].value,
                    "label_prazo": prazo_info["label"],
                    "ultima_tramitacao": ultima_tram_texto,
                    "url_sapl": materia["url_sapl"],
                })

        except Exception as e:
            logger.error(f"Erro ao processar matéria {materia_bruta.get('id', '?')}: {e}", exc_info=True)
            erros += 1
            continue

    logger.info(f"\nSincronização concluída:")
    logger.info(f"  ✓ Criadas:    {criadas}")
    logger.info(f"  ↻ Atualizadas:{atualizadas}")
    logger.info(f"  ✗ Erros:      {erros}")
    logger.info(f"  🔔 Alertas:   {len(materias_para_alertar)}")

    # Disparar alertas
    if materias_para_alertar:
        _disparar_alertas(materias_para_alertar)


def _disparar_alertas(materias: list[dict]):
    email_cfg = None
    if all(os.getenv(k) for k in ["SMTP_HOST", "SMTP_USER", "SMTP_PASS"]):
        email_cfg = AlertaEmail(
            smtp_host=os.getenv("SMTP_HOST"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            usuario=os.getenv("SMTP_USER"),
            senha=os.getenv("SMTP_PASS"),
        )

    telegram_cfg = None
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        telegram_cfg = AlertaTelegram(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        )

    destinatarios = [e.strip() for e in os.getenv("DESTINATARIOS_EMAIL", "").split(",") if e.strip()]

    gerenciador = GerenciadorAlertas(
        email=email_cfg,
        telegram=telegram_cfg,
        destinatarios_email=destinatarios,
    )
    gerenciador.disparar(materias)


# ------------------------------------------------------------------
# Entrada
# ------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sincronizador SAPL → ClickUp")
    parser.add_argument("--modo", choices=["unico", "daemon"], default="unico",
                        help="unico: roda uma vez; daemon: loop contínuo")
    parser.add_argument("--apenas-alertas", action="store_true",
                        help="Só verifica prazos e envia alertas, sem criar/atualizar tarefas")
    args = parser.parse_args()

    if args.modo == "daemon":
        logger.info(f"Modo daemon: sincronizando a cada {SYNC_INTERVAL} minutos")
        while True:
            sincronizar()
            logger.info(f"Aguardando {SYNC_INTERVAL} min para próxima sincronização...")
            time.sleep(SYNC_INTERVAL * 60)
    else:
        sincronizar()
