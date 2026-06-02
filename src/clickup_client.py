"""
clickup_client.py
Cria, atualiza e busca tarefas no ClickUp via API v2.
"""

import logging
from datetime import date, datetime
from typing import Optional
import requests

logger = logging.getLogger(__name__)

BASE = "https://api.clickup.com/api/v2"


class ClickUpClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": api_key,
            "Content-Type": "application/json",
        })

    def _get(self, endpoint: str, params: dict = None) -> dict:
        r = self.session.get(f"{BASE}/{endpoint}", params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def _post(self, endpoint: str, payload: dict) -> dict:
        r = self.session.post(f"{BASE}/{endpoint}", json=payload, timeout=20)
        r.raise_for_status()
        return r.json()

    def _put(self, endpoint: str, payload: dict) -> dict:
        r = self.session.put(f"{BASE}/{endpoint}", json=payload, timeout=20)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Workspaces / Teams
    # ------------------------------------------------------------------
    def listar_teams(self) -> list[dict]:
        return self._get("team").get("teams", [])

    # ------------------------------------------------------------------
    # Busca de tarefas existentes (para evitar duplicatas)
    # ------------------------------------------------------------------
    def buscar_tarefa_por_sapl_id(self, list_id: str, sapl_id: int) -> Optional[dict]:
        """Busca tarefa na list usando campo customizado 'ID SAPL'."""
        try:
            data = self._get(f"list/{list_id}/task", params={
                "custom_fields": f'[{{"field_name":"ID SAPL","value":"{sapl_id}"}}]',
                "page": 0,
            })
            tarefas = data.get("tasks", [])
            # Verificação adicional pelo nome (fallback)
            for t in tarefas:
                for cf in t.get("custom_fields", []):
                    if cf.get("name") == "ID SAPL" and str(cf.get("value")) == str(sapl_id):
                        return t
        except Exception:
            pass
        return None

    def buscar_tarefas_da_list(self, list_id: str, incluir_fechadas: bool = False) -> list[dict]:
        """Retorna todas as tarefas de uma list (paginado)."""
        tarefas = []
        pagina = 0
        while True:
            data = self._get(f"list/{list_id}/task", params={
                "page": pagina,
                "include_closed": str(incluir_fechadas).lower(),
            })
            lote = data.get("tasks", [])
            tarefas.extend(lote)
            if not lote or data.get("last_page", True):
                break
            pagina += 1
        return tarefas

    # ------------------------------------------------------------------
    # Criar tarefa
    # ------------------------------------------------------------------
    def criar_tarefa(
        self,
        list_id: str,
        titulo: str,
        descricao: str,
        status: str,
        prazo: Optional[date],
        tags: list[str] = None,
        campos_customizados: list[dict] = None,
    ) -> dict:
        """Cria nova tarefa no ClickUp."""
        payload = {
            "name": titulo,
            "description": descricao,
            "status": status,
            "tags": tags or [],
        }
        if prazo:
            # ClickUp espera timestamp em milissegundos
            ts = int(datetime.combine(prazo, datetime.min.time()).timestamp() * 1000)
            payload["due_date"] = ts
            payload["due_date_time"] = False

        if campos_customizados:
            payload["custom_fields"] = campos_customizados

        tarefa = self._post(f"list/{list_id}/task", payload)
        logger.info(f"  + Tarefa criada: {titulo}  (id={tarefa.get('id')})")
        return tarefa

    # ------------------------------------------------------------------
    # Atualizar tarefa
    # ------------------------------------------------------------------
    def atualizar_tarefa(
        self,
        task_id: str,
        status: str = None,
        prazo: date = None,
        descricao: str = None,
    ) -> dict:
        """Atualiza campos de uma tarefa existente."""
        payload = {}
        if status:
            payload["status"] = status
        if prazo:
            ts = int(datetime.combine(prazo, datetime.min.time()).timestamp() * 1000)
            payload["due_date"] = ts
        if descricao:
            payload["description"] = descricao

        if not payload:
            return {}

        tarefa = self._put(f"task/{task_id}", payload)
        logger.info(f"  ↻ Tarefa atualizada: {task_id}  status={status}")
        return tarefa

    def atualizar_campo_customizado(self, task_id: str, field_id: str, value) -> dict:
        """Atualiza um campo customizado específico de uma tarefa."""
        return self._post(f"task/{task_id}/field/{field_id}", {"value": value})

    # ------------------------------------------------------------------
    # Comentários (log de tramitação)
    # ------------------------------------------------------------------
    def adicionar_comentario(self, task_id: str, texto: str) -> dict:
        return self._post(f"task/{task_id}/comment", {
            "comment_text": texto,
            "notify_all": False,
        })

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------
    def montar_campos_sapl(
        self,
        numero_sapl: str,
        tipo: str,
        ementa: str,
        ultima_tramitacao: str,
        localizacao: str,
        data_protocolo: Optional[date],
        prazo_final: Optional[date],
        url_sapl: str,
        sapl_id: int,
        ids_campos: dict,     # {"ID SAPL": "campo_id_clickup", ...}
    ) -> list[dict]:
        """Monta lista de campos customizados no formato esperado pelo ClickUp."""
        mapa = {
            "Número SAPL":       numero_sapl,
            "Tipo de matéria":   tipo,
            "Ementa":            ementa[:500] if ementa else "",
            "Última tramitação": ultima_tramitacao,
            "Localização atual": localizacao,
            "Link SAPL":         url_sapl,
            "ID SAPL":           sapl_id,
        }
        campos = []
        for nome, valor in mapa.items():
            field_id = ids_campos.get(nome)
            if field_id and valor is not None:
                campos.append({"id": field_id, "value": valor})

        # Campos de data (timestamp ms)
        for nome_campo, data_val in [("Data protocolo", data_protocolo), ("Prazo final", prazo_final)]:
            field_id = ids_campos.get(nome_campo)
            if field_id and data_val:
                ts = int(datetime.combine(data_val, datetime.min.time()).timestamp() * 1000)
                campos.append({"id": field_id, "value": ts})

        return campos

    def obter_ids_campos(self, list_id: str) -> dict:
        """Retorna dicionário {nome_campo: id_campo} para uma list."""
        data = self._get(f"list/{list_id}/field")
        return {f["name"]: f["id"] for f in data.get("fields", [])}
