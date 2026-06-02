"""
prazos.py
Calcula prazos legislativos, dias úteis e detecta atrasos.
"""

from datetime import date, timedelta
from enum import Enum


# Feriados nacionais fixos (mês, dia)
FERIADOS_NACIONAIS = {
    (1, 1), (4, 21), (5, 1), (9, 7),
    (10, 12), (11, 2), (11, 15), (11, 20), (12, 25),
}

# Feriados municipais de Bayeux/PB (mês, dia) — ajuste conforme calendário
FERIADOS_MUNICIPAIS = {
    (6, 24),   # São João (Bayeux)
    (8, 15),   # Nossa Senhora da Assunção (padroeira)
    (6, 13),   # Santo Antônio (João Pessoa/região)
}


class StatusPrazo(Enum):
    NO_PRAZO     = "no_prazo"
    ATENCAO      = "atencao"       # ≤ 3 dias úteis restantes
    URGENTE      = "urgente"       # ≤ 1 dia útil restante
    ATRASADO     = "atrasado"
    SEM_PRAZO    = "sem_prazo"
    CONCLUIDO    = "concluido"


def eh_feriado(d: date) -> bool:
    return (d.month, d.day) in FERIADOS_NACIONAIS | FERIADOS_MUNICIPAIS


def eh_dia_util(d: date) -> bool:
    return d.weekday() < 5 and not eh_feriado(d)


def dias_uteis_entre(data_inicio: date, data_fim: date) -> int:
    """Conta dias úteis entre duas datas (inclusivo no início, exclusivo no fim)."""
    if data_inicio >= data_fim:
        return 0
    total = 0
    atual = data_inicio
    while atual < data_fim:
        if eh_dia_util(atual):
            total += 1
        atual += timedelta(days=1)
    return total


def adicionar_dias_uteis(data_inicio: date, dias: int) -> date:
    """Retorna a data após N dias úteis a partir de data_inicio."""
    atual = data_inicio
    contados = 0
    while contados < dias:
        atual += timedelta(days=1)
        if eh_dia_util(atual):
            contados += 1
    return atual


# ------------------------------------------------------------------
# Prazos padrão por tipo de matéria (em dias úteis)
# Ajuste conforme o Regimento Interno da Câmara de Bayeux
# ------------------------------------------------------------------
PRAZOS_POR_TIPO = {
    "PL":    20,   # Projeto de Lei
    "PLC":   20,   # Projeto de Lei Complementar
    "PDL":   10,   # Projeto de Decreto Legislativo
    "PR":    10,   # Projeto de Resolução
    "REQ":    5,   # Requerimento
    "IND":    5,   # Indicação
    "MOC":    5,   # Moção
    "REC":   15,   # Recurso
    # Padrão para tipos não mapeados
    "DEFAULT": 15,
}


def calcular_prazo(data_apresentacao_str: str, sigla_tipo: str) -> date:
    """Calcula a data de prazo com base na data de apresentação e tipo."""
    try:
        data = date.fromisoformat(data_apresentacao_str)
    except (ValueError, TypeError):
        data = date.today()
    dias = PRAZOS_POR_TIPO.get(sigla_tipo.upper(), PRAZOS_POR_TIPO["DEFAULT"])
    return adicionar_dias_uteis(data, dias)


def avaliar_prazo(prazo: date, concluido: bool = False) -> dict:
    """
    Retorna o status do prazo e quantos dias úteis restam (ou estão em atraso).
    """
    if concluido:
        return {"status": StatusPrazo.CONCLUIDO, "dias_restantes": None, "label": "Concluído"}

    hoje = date.today()

    if prazo is None:
        return {"status": StatusPrazo.SEM_PRAZO, "dias_restantes": None, "label": "Sem prazo definido"}

    if hoje > prazo:
        dias_atraso = dias_uteis_entre(prazo, hoje)
        return {
            "status": StatusPrazo.ATRASADO,
            "dias_restantes": -dias_atraso,
            "label": f"Atrasado {dias_atraso} dia(s) útil(eis)",
        }

    dias_rest = dias_uteis_entre(hoje, prazo)

    if dias_rest <= 1:
        status = StatusPrazo.URGENTE
        label = f"Urgente — vence em {dias_rest} dia útil"
    elif dias_rest <= 3:
        status = StatusPrazo.ATENCAO
        label = f"Atenção — {dias_rest} dias úteis"
    else:
        status = StatusPrazo.NO_PRAZO
        label = f"{dias_rest} dias úteis restantes"

    return {"status": status, "dias_restantes": dias_rest, "label": label}


# Mapeamento de StatusPrazo → status no ClickUp
STATUS_CLICKUP = {
    StatusPrazo.NO_PRAZO:  "Em andamento",
    StatusPrazo.ATENCAO:   "Aguardando",
    StatusPrazo.URGENTE:   "Atrasado",
    StatusPrazo.ATRASADO:  "Atrasado",
    StatusPrazo.SEM_PRAZO: "Em andamento",
    StatusPrazo.CONCLUIDO: "Concluído",
}


def deve_alertar(dias_restantes: int, dias_alerta: list[int]) -> bool:
    """Retorna True se hoje é um dos dias de alerta configurados."""
    if dias_restantes is None:
        return False
    return dias_restantes in dias_alerta
