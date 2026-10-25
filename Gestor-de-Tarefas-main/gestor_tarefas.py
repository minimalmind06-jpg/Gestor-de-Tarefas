#!/usr/bin/env python3
"""
=============================================================================
 [gestor_tarefas] · Versão Oficial Desktop & Web Local
=============================================================================
 - Interface moderna com paleta Bege, Cinzento e Branco
 - Autenticação segura por utilizador (Início de Sessão & Registo)
 - Base de dados SQLite local robusta com isolamento estrito de tarefas
 - Histórico e auditoria cronológica de todas as ações por conta
 - Gestão completa de tarefas: adicionar, editar, eliminar, concluir/reabrir,
   prazos no formato DD/MM/AAAA, indicadores de atraso e filtros rápidos.

 Requisitos: Python 3.8+ (Apenas biblioteca padrão, sem dependências externas)
 Executar:   python3 gestor_tarefas.py
=============================================================================
"""

import argparse
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Importar camada de dados
import database

BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon"
}


class GestorTarefasHTTPHandler(BaseHTTPRequestHandler):
    """Manipulador HTTP RESTful e servidor de ficheiros estáticos para o [gestor_tarefas]."""

    server_version = "gestor_tarefas/2.0"

    def log_message(self, format, *args):
        # Suprime logs verbosos de pedidos estáticos normais no terminal
        if self.path.startswith("/api/"):
            super().log_message(format, *args)

    # ------------------------------------------------------------- Helpers
    def _enviar_json(self, status_code: int, dados: dict):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(corpo)

    def _ler_json(self):
        try:
            comprimento = int(self.headers.get("Content-Length", 0))
            if comprimento == 0:
                return {}
            dados_brutos = self.rfile.read(comprimento)
            return json.loads(dados_brutos.decode("utf-8"))
        except Exception:
            return None

    def _obter_token_autenticacao(self):
        cabecalho = self.headers.get("Authorization", "")
        if cabecalho.startswith("Bearer "):
            return cabecalho[7:].strip()
        return None

    def _autenticar_pedido(self):
        token = self._obter_token_autenticacao()
        if not token:
            self._enviar_json(401, {"erro": "Sessão não fornecida. Inicie sessão para continuar."})
            return None
        utilizador = database.validar_sessao(token)
        if not utilizador:
            self._enviar_json(401, {"erro": "Sessão expirada ou inválida. Inicie sessão novamente."})
            return None
        return utilizador

    # ------------------------------------------------------------- GET
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        caminho = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # Rotas da API
        if caminho.startswith("/api/"):
            self._tratar_api_get(caminho, params)
            return

        # Servir Ficheiros Estáticos da UI
        self._servir_estatico(caminho)

    def _tratar_api_get(self, caminho: str, params: dict):
        if caminho == "/api/auth/me":
            user = self._autenticar_pedido()
            if user:
                self._enviar_json(200, {"utilizador": user})
            return

        if caminho == "/api/tasks":
            user = self._autenticar_pedido()
            if not user:
                return
            filtro = params.get("filtro", ["todas"])[0]
            todas = database.listar_tarefas(user["id"], filtro="todas")
            tarefas_filtradas = database.listar_tarefas(user["id"], filtro=filtro)

            total = len(todas)
            concluidas = sum(1 for t in todas if t["concluida"])
            pendentes = total - concluidas
            atrasadas = sum(1 for t in todas if t.get("estado_prazo") == "atraso")

            self._enviar_json(200, {
                "tarefas": tarefas_filtradas,
                "resumo": {
                    "total": total,
                    "concluidas": concluidas,
                    "pendentes": pendentes,
                    "atrasadas": atrasadas
                }
            })
            return

        if caminho == "/api/history":
            user = self._autenticar_pedido()
            if not user:
                return
            historico = database.listar_historico(user["id"])
            self._enviar_json(200, {"historico": historico})
            return

        self._enviar_json(404, {"erro": "Recurso não encontrado."})

    # ------------------------------------------------------------- POST
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        caminho = parsed.path
        dados = self._ler_json()
        if dados is None:
            self._enviar_json(400, {"erro": "Formato JSON inválido."})
            return

        # Autenticação: Registo
        if caminho == "/api/auth/register":
            username = dados.get("username", "")
            password = dados.get("password", "")
            user, erro = database.criar_utilizador(username, password)
            if erro:
                self._enviar_json(400, {"erro": erro})
                return
            token = database.criar_sessao(user["id"])
            self._enviar_json(201, {"token": token, "utilizador": user})
            return

        # Autenticação: Início de Sessão
        if caminho == "/api/auth/login":
            username = dados.get("username", "")
            password = dados.get("password", "")
            user, erro = database.autenticar_utilizador(username, password)
            if erro:
                self._enviar_json(401, {"erro": erro})
                return
            token = database.criar_sessao(user["id"])
            self._enviar_json(200, {"token": token, "utilizador": user})
            return

        # Autenticação: Terminar Sessão
        if caminho == "/api/auth/logout":
            token = self._obter_token_autenticacao()
            if token:
                database.terminar_sessao(token)
            self._enviar_json(200, {"sucesso": True})
            return

        # Tarefas: Criar Nova Tarefa
        if caminho == "/api/tasks":
            user = self._autenticar_pedido()
            if not user:
                return
            titulo = dados.get("titulo", "")
            prazo = dados.get("prazo", "")
            tarefa, erro = database.adicionar_tarefa(user["id"], titulo, prazo)
            if erro:
                self._enviar_json(400, {"erro": erro})
                return
            self._enviar_json(201, {"tarefa": tarefa})
            return

        # Tarefas: Alternar Conclusão
        match_toggle = re.match(r"^/api/tasks/([^/]+)/toggle$", caminho)
        if match_toggle:
            user = self._autenticar_pedido()
            if not user:
                return
            task_id = match_toggle.group(1)
            tarefa, erro = database.alternar_conclusao_tarefa(user["id"], task_id)
            if erro:
                self._enviar_json(400, {"erro": erro})
                return
            self._enviar_json(200, tarefa)
            return

        # Tarefas: Limpar Concluídas
        if caminho == "/api/tasks/clear-completed":
            user = self._autenticar_pedido()
            if not user:
                return
            removidas, erro = database.limpar_tarefas_concluidas(user["id"])
            if erro:
                self._enviar_json(400, {"erro": erro})
                return
            self._enviar_json(200, {"sucesso": True, "removidas": removidas})
            return

        self._enviar_json(404, {"erro": "Rota não encontrada."})

    # ------------------------------------------------------------- PUT
    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        caminho = parsed.path
        dados = self._ler_json()
        if dados is None:
            self._enviar_json(400, {"erro": "Formato JSON inválido."})
            return

        # Tarefas: Editar Tarefa Existente
        match_edit = re.match(r"^/api/tasks/([^/]+)$", caminho)
        if match_edit:
            user = self._autenticar_pedido()
            if not user:
                return
            task_id = match_edit.group(1)
            titulo = dados.get("titulo", "")
            prazo = dados.get("prazo", "")
            tarefa, erro = database.atualizar_tarefa(user["id"], task_id, titulo, prazo)
            if erro:
                self._enviar_json(400, {"erro": erro})
                return
            self._enviar_json(200, {"tarefa": tarefa})
            return

        self._enviar_json(404, {"erro": "Rota não encontrada."})

    # ------------------------------------------------------------- DELETE
    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        caminho = parsed.path

        # Tarefas: Eliminar Tarefa Específica
        match_delete = re.match(r"^/api/tasks/([^/]+)$", caminho)
        if match_delete:
            user = self._autenticar_pedido()
            if not user:
                return
            task_id = match_delete.group(1)
            sucesso, erro = database.eliminar_tarefa(user["id"], task_id)
            if erro:
                self._enviar_json(400, {"erro": erro})
                return
            self._enviar_json(200, {"sucesso": True})
            return

        self._enviar_json(404, {"erro": "Rota não encontrada."})

    # ------------------------------------------------------------- Estáticos
    def _servir_estatico(self, caminho: str):
        if caminho in ("", "/"):
            caminho = "/index.html"

        caminho_limpo = caminho.lstrip("/")
        ficheiro_alvo = (UI_DIR / caminho_limpo).resolve()

        # Segurança: verificar se o caminho não sai da pasta UI
        if not str(ficheiro_alvo).startswith(str(UI_DIR.resolve())) or not ficheiro_alvo.is_file():
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"404: Ficheiro nao encontrado no [gestor_tarefas].")
            return

        extensao = ficheiro_alvo.suffix.lower()
        content_type = MIME_TYPES.get(extensao, "application/octet-stream")

        try:
            with open(ficheiro_alvo, "rb") as f:
                conteudo = f.read()

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(conteudo)))
            self.end_headers()
            self.wfile.write(conteudo)
        except OSError:
            self.send_response(500)
            self.end_headers()


def encontrar_porta_livre(porta_inicial: int = 5050, max_tentativas: int = 50) -> int:
    """Encontra uma porta TCP local disponível para bind."""
    for porta in range(porta_inicial, porta_inicial + max_tentativas):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", porta))
                return porta
            except OSError:
                continue
    # Fallback para qualquer porta disponível atribuída pelo sistema operativo
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def abrir_navegador(url: str):
    """Abre a aplicação no navegador em modo desktop."""
    time.sleep(0.4)
    try:
        webbrowser.open(url, new=2)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="[gestor_tarefas] · Gestão Inteligente de Tarefas")
    parser.add_argument("--porta", type=int, default=None, help="Porta local para o servidor HTTP")
    parser.add_argument("--sem-navegador", action="store_true", help="Não abre automaticamente o navegador")
    args = parser.parse_args()

    # 1. Inicializar esquema da base de dados SQLite
    database.inicializar_bd()

    # 2. Configurar porta do servidor
    porta = args.porta if args.porta else encontrar_porta_livre(5050)
    endereco = ("127.0.0.1", porta)
    url = f"http://127.0.0.1:{porta}"

    # 3. Iniciar Servidor HTTP multithreaded
    servidor = ThreadingHTTPServer(endereco, GestorTarefasHTTPHandler)

    largura = 64
    print("=" * largura)
    print("  [gestor_tarefas] · Aplicação Desktop Oficial".center(largura))
    print("=" * largura)
    print(f"  Interface local:  {url}")
    print(f"  Base de dados:    {database.DB_PATH.name} (SQLite WAL)")
    print(f"  Paleta visual:    Bege, Cinzento e Branco")
    print(f"  Multi-utilizador: Ativo com histórico de ações por conta")
    print("-" * largura)
    print("  Prima Ctrl+C no terminal para encerrar a aplicação.")
    print("=" * largura)

    # 4. Abrir janela da aplicação
    if not args.sem_navegador:
        t = threading.Thread(target=abrir_navegador, args=(url,), daemon=True)
        t.start()

    # 5. Executar loop principal com encerramento gracioso
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n\nA encerrar o [gestor_tarefas] com segurança...")
    finally:
        servidor.server_close()
        print("Aplicação terminada com sucesso. Até à próxima!")


if __name__ == "__main__":
    main()
