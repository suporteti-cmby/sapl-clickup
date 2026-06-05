"""
sapl_client.py
Acessa a API REST pública do SAPL de Bayeux e retorna dados normalizados.
"""

import logging
from datetime import datetime, date
from typing import Optional
import requests

logger = logging.getLogger(__name__)

SAPL_BASE = "https://sapl.bayeux.pb.leg.br"


class SAPLClient:
    def __init__(self, base_url: str = SAPL_BASE, timeout: int = 60):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "SAPL-ClickUp-Integração/1.0 (Câmara Bayeux)",
        })

    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.base}/api/{endpoint.lstrip('/')}"
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP {e.response.status_code} em {url}: {e}")
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"Sem conexão com SAPL: {url}")
            raise
        except requests.exceptions.Timeout:
            logger.error(f"Timeout ao acessar SAPL: {url}")
            raise

    # ------------------------------------------------------------------
    # Matérias legislativas
    # ------------------------------------------------------------------
    def listar_materias(
        self,
        ano: int = None,
        tipo: int = None,
        em_tramitacao: bool = True,
        pagina: int = 1,
    ) -> dict:
        """Retorna lista paginada de matérias legislativas."""
        params = {"page": pagina}
        if ano:
            params["ano"] = ano
        if tipo:
            params["tipo_materia"] = tipo
        # Filtro em_tramitacao removido da query — causa erro 500 no SAPL de Bayeux
        # A filtragem é feita localmente em listar_todas_materias_ativas
        return self._get("materia/materialegislativa/", params)

    def obter_materia(self, materia_id: int) -> dict:
        """Retorna detalhes de uma matéria específica."""
        return self._get(f"materia/materialegislativa/{materia_id}/")

    def listar_todas_materias_ativas(self) -> list[dict]:
        """Percorre todas as páginas e retorna todas as matérias em tramitação."""
        import time
        materias = []
        pagina = 1
        while True:
            # Tenta até 3 vezes por página em caso de timeout
            for tentativa in range(3):
                try:
                    data = self.listar_materias(pagina=pagina)
                    break
                except Exception as e:
                    if tentativa < 2:
                        logger.warning(f"  Tentativa {tentativa+1} falhou na página {pagina}, aguardando 5s...")
                        time.sleep(5)
                    else:
                        logger.error(f"  Página {pagina} falhou após 3 tentativas: {e}")
                        data = {"results": [], "next": None}
            resultados = data.get("results", [])
            # Filtra localmente pois o filtro na query causa erro 500 no SAPL de Bayeux
            ativas = [m for m in resultados if m.get("em_tramitacao", False)]
            materias.extend(ativas)
            logger.info(f"  SAPL: página {pagina} — {len(ativas)} matérias em tramitação (de {len(resultados)})")
            if not data.get("next"):
                break
            pagina += 1
            time.sleep(1)  # Pausa entre páginas para não sobrecarregar o servidor
        logger.info(f"Total de matérias ativas: {len(materias)}")
        return materias

    # ------------------------------------------------------------------
    # Tramitações
    # ------------------------------------------------------------------
    def listar_tramitacoes(self, materia_id: int) -> list[dict]:
        """Retorna todo o histórico de tramitações de uma matéria."""
        data = self._get(
            "materia/tramitacao/",
            params={"materia": materia_id, "page_size": 100},
        )
        return data.get("results", [])

    def ultima_tramitacao(self, materia_id: int) -> Optional[dict]:
        """Retorna apenas a tramitação mais recente."""
        tramitacoes = self.listar_tramitacoes(materia_id)
        if not tramitacoes:
            return None
        # Ordena por data_tramitacao decrescente
        return sorted(
            tramitacoes,
            key=lambda t: t.get("data_tramitacao", "1900-01-01"),
            reverse=True,
        )[0]

    # ------------------------------------------------------------------
    # Tipos de matéria
    # ------------------------------------------------------------------
    def listar_tipos_materia(self) -> list[dict]:
        data = self._get("materia/tipomateria/")
        return data.get("results", [])

    # ------------------------------------------------------------------
    # Sessões plenárias
    # ------------------------------------------------------------------
    def listar_sessoes(self, ano: int = None) -> list[dict]:
        params = {}
        if ano:
            params["data_inicio__year"] = ano
        data = self._get("sessao/sessaoplenaria/", params)
        return data.get("results", [])

    def proximas_sessoes(self) -> list[dict]:
        """Retorna sessões agendadas a partir de hoje."""
        hoje = date.today().isoformat()
        data = self._get(
            "sessao/sessaoplenaria/",
            params={"data_inicio__gte": hoje, "page_size": 20},
        )
        return data.get("results", [])

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------
    def montar_url_materia(self, materia_id: int) -> str:
        return f"{self.base}/materia/{materia_id}"

    def normalizar_materia(self, m: dict) -> dict:
        """Transforma os dados brutos da API em um dicionário padronizado."""
        return {
            "id": m.get("id"),
            "numero": m.get("numero"),
            "ano": m.get("ano"),
            "tipo_id": m.get("tipo", {}).get("id") if isinstance(m.get("tipo"), dict) else m.get("tipo"),
            "tipo_nome": m.get("tipo", {}).get("sigla", "") if isinstance(m.get("tipo"), dict) else "",
            "tipo_descricao": m.get("tipo", {}).get("descricao", "") if isinstance(m.get("tipo"), dict) else "",
            "ementa": (m.get("ementa") or "")[:500],
            "data_apresentacao": m.get("data_apresentacao"),
            "em_tramitacao": m.get("em_tramitacao", True),
            "autores": m.get("autoria", []),
            "url_sapl": self.montar_url_materia(m.get("id")),
            "titulo": f"{m.get('tipo', {}).get('sigla', 'MAT') if isinstance(m.get('tipo'), dict) else 'MAT'} "
                      f"{m.get('numero', '?')}/{m.get('ano', '?')}",
        }
