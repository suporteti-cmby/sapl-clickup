"""
setup_clickup.py
Executa UMA VEZ para criar toda a estrutura no ClickUp:
  Space → Folder → Lists por setor → Status personalizados

Uso:
    python setup_clickup.py --api-key pk_SEU_TOKEN --team-id SEU_TEAM_ID
"""

import argparse
import json
import sys
import requests

BASE = "https://api.clickup.com/api/v2"

SETORES = [
    {"nome": "Secretaria Legislativa", "env": "LIST_SECRETARIA"},
    {"nome": "Comissões",              "env": "LIST_COMISSOES"},
    {"nome": "Procuradoria Legislativa","env": "LIST_PROCURADORIA"},
    {"nome": "Gabinetes dos Vereadores","env": "LIST_GABINETES"},
    {"nome": "Presidência / Mesa Diretora","env": "LIST_MESA_DIRETORA"},
    {"nome": "Poder Executivo Municipal","env": "LIST_EXECUTIVO"},
]

STATUS_PERSONALIZADOS = [
    {"status": "Em andamento", "color": "#4A90E2", "type": "custom"},
    {"status": "Aguardando",   "color": "#F5A623", "type": "custom"},
    {"status": "Atrasado",     "color": "#D0021B", "type": "custom"},
    {"status": "Concluído",    "color": "#27AE60", "type": "closed"},
    {"status": "Arquivado",    "color": "#9B9B9B", "type": "closed"},
]


def headers(api_key):
    return {"Authorization": api_key, "Content-Type": "application/json"}


def criar_space(team_id, api_key):
    url = f"{BASE}/team/{team_id}/space"
    payload = {
        "name": "SAPL – Câmara de Bayeux",
        "multiple_assignees": True,
        "features": {
            "due_dates": {"enabled": True, "start_date": True, "remap_due_dates": True},
            "time_tracking": {"enabled": False},
            "tags": {"enabled": True},
            "time_estimates": {"enabled": False},
            "checklists": {"enabled": True},
            "custom_fields": {"enabled": True},
            "remap_dependencies": {"enabled": True},
            "dependency_warning": {"enabled": True},
            "portfolios": {"enabled": False},
        },
    }
    r = requests.post(url, json=payload, headers=headers(api_key))
    r.raise_for_status()
    space = r.json()
    print(f"  ✓ Space criado: {space['name']}  (id={space['id']})")
    return space["id"]


def criar_folder(space_id, api_key):
    url = f"{BASE}/space/{space_id}/folder"
    r = requests.post(url, json={"name": "Matérias Legislativas"}, headers=headers(api_key))
    r.raise_for_status()
    folder = r.json()
    print(f"  ✓ Folder criado: {folder['name']}  (id={folder['id']})")
    return folder["id"]


def criar_list(folder_id, nome_setor, api_key):
    url = f"{BASE}/folder/{folder_id}/list"
    payload = {
        "name": nome_setor,
        "content": f"Matérias legislativas — {nome_setor}",
    }
    r = requests.post(url, json=payload, headers=headers(api_key))
    r.raise_for_status()
    lst = r.json()
    print(f"    ✓ List criada: {lst['name']}  (id={lst['id']})")
    return lst["id"]


def criar_campos_customizados(list_id, api_key):
    """Cria campos personalizados em cada List para espelhar dados do SAPL."""
    campos = [
        {"name": "Número SAPL",        "type": "text"},
        {"name": "Tipo de matéria",     "type": "text"},
        {"name": "Ementa",              "type": "text"},
        {"name": "Última tramitação",   "type": "text"},
        {"name": "Localização atual",   "type": "text"},
        {"name": "Data protocolo",      "type": "date"},
        {"name": "Prazo final",         "type": "date"},
        {"name": "Link SAPL",           "type": "url"},
        {"name": "ID SAPL",             "type": "number"},
    ]
    url = f"{BASE}/list/{list_id}/field"
    criados = []
    for campo in campos:
        try:
            r = requests.post(url, json=campo, headers=headers(api_key))
            if r.status_code == 200:
                criados.append(campo["name"])
        except Exception:
            pass
    if criados:
        print(f"      ✓ Campos criados: {', '.join(criados)}")


def deletar_space(space_id, api_key):
    url = f"{BASE}/space/{space_id}"
    r = requests.delete(url, headers=headers(api_key))
    if r.status_code in (200, 204):
        print(f"  🗑 Space anterior deletado: {space_id}")
    else:
        print(f"  ⚠ Não foi possível deletar space {space_id}: {r.status_code}")


def main():
    parser = argparse.ArgumentParser(description="Configura estrutura ClickUp para SAPL")
    parser.add_argument("--api-key",  required=True, help="Chave de API do ClickUp (pk_...)")
    parser.add_argument("--team-id",  required=True, help="ID do Workspace/Team no ClickUp")
    parser.add_argument("--delete-space", default="", help="ID de space anterior para deletar antes de recriar")
    args = parser.parse_args()

    print("\n🔧 Configurando ClickUp para SAPL – Câmara de Bayeux\n")

    # 0. Deletar space anterior se informado
    if args.delete_space:
        print("0. Removendo estrutura anterior...")
        deletar_space(args.delete_space, args.api_key)

    # 1. Space
    print("1. Criando Space...")
    space_id = criar_space(args.team_id, args.api_key)

    # 2. Folder
    print("\n2. Criando Folder...")
    folder_id = criar_folder(space_id, args.api_key)

    # 3. Lists por setor
    print("\n3. Criando Lists por setor...")
    ids_gerados = {}
    for setor in SETORES:
        list_id = criar_list(folder_id, setor["nome"], args.api_key)
        criar_campos_customizados(list_id, args.api_key)
        ids_gerados[setor["env"]] = list_id

    # 4. Exibir .env para copiar
    print("\n" + "="*60)
    print("✅ Estrutura criada! Copie as linhas abaixo para seu .env:\n")
    print(f"CLICKUP_TEAM_ID={args.team_id}")
    for env_key, list_id in ids_gerados.items():
        print(f"{env_key}={list_id}")
    print("="*60 + "\n")

    # Salvar em arquivo para facilitar
    with open("ids_gerados.json", "w") as f:
        json.dump({"team_id": args.team_id, "lists": ids_gerados}, f, indent=2)
    print("💾 IDs salvos em ids_gerados.json\n")


if __name__ == "__main__":
    main()
