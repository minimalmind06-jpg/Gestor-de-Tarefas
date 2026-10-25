"""
Módulo de Base de Dados e Autenticação do [gestor_tarefas].
Garante isolamento estrito de dados por utilizador, registo de histórico
e segurança criptográfica com a biblioteca padrão (SQLite3 + hashlib).
"""

import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "gestor_tarefas.db"
LEGACY_JSON_PATH = Path(__file__).resolve().parent / "tarefas.json"
FORMATO_DATA = "%d/%m/%Y"


def obter_conexao():
    """Devolve uma ligação SQLite com row_factory configurada e chaves estrangeiras ativas."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def inicializar_bd():
    """Cria o esquema inicial da base de dados caso ainda não exista."""
    with obter_conexao() as conn:
        cursor = conn.cursor()

        # Tabela de Utilizadores
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS utilizadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );
        """)

        # Tabela de Sessões
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                token TEXT PRIMARY KEY,
                utilizador_id INTEGER NOT NULL,
                criado_em TEXT NOT NULL,
                FOREIGN KEY (utilizador_id) REFERENCES utilizadores(id) ON DELETE CASCADE
            );
        """)

        # Tabela de Tarefas (isolada por utilizador)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id TEXT PRIMARY KEY,
                utilizador_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                prazo TEXT NOT NULL DEFAULT '',
                concluida INTEGER NOT NULL DEFAULT 0,
                criada_em TEXT NOT NULL,
                atualizada_em TEXT NOT NULL,
                FOREIGN KEY (utilizador_id) REFERENCES utilizadores(id) ON DELETE CASCADE
            );
        """)

        # Tabela de Histórico de Ações
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                utilizador_id INTEGER NOT NULL,
                tipo_acao TEXT NOT NULL,
                descricao TEXT NOT NULL,
                detalhes TEXT,
                criado_em TEXT NOT NULL,
                FOREIGN KEY (utilizador_id) REFERENCES utilizadores(id) ON DELETE CASCADE
            );
        """)

        conn.commit()


# ----------------------------------------------------------------- Segurança
def _gerar_hash_palavra_passe(palavra_passe: str, salt: bytes) -> str:
    """Gera hash PBKDF2-HMAC-SHA256 seguro."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        palavra_passe.encode("utf-8"),
        salt,
        iterations=200_000
    ).hex()


def criar_utilizador(username: str, palavra_passe: str):
    """Regista um novo utilizador no [gestor_tarefas]."""
    username = username.strip()
    if not username:
        return None, "O nome de utilizador é obrigatório."
    if len(username) < 3:
        return None, "O nome de utilizador deve ter pelo menos 3 caracteres."
    if len(palavra_passe) < 4:
        return None, "A palavra-passe deve ter pelo menos 4 caracteres."

    salt = secrets.token_bytes(32)
    salt_hex = salt.hex()
    p_hash = _gerar_hash_palavra_passe(palavra_passe, salt)
    agora = datetime.now().isoformat(timespec="seconds")

    try:
        with obter_conexao() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO utilizadores (username, password_hash, salt, criado_em)
                VALUES (?, ?, ?, ?);
            """, (username, p_hash, salt_hex, agora))
            user_id = cursor.lastrowid

            # Registar no histórico
            cursor.execute("""
                INSERT INTO historico (utilizador_id, tipo_acao, descricao, detalhes, criado_em)
                VALUES (?, 'CONTA_CRIADA', 'Conta criada no [gestor_tarefas].', NULL, ?);
            """, (user_id, agora))

            # Se existia tarefas.json legada e for o primeiro utilizador, migrar
            cursor.execute("SELECT COUNT(*) AS total FROM utilizadores;")
            total_users = cursor.fetchone()["total"]
            if total_users == 1 and LEGACY_JSON_PATH.exists():
                _migrar_tarefas_legadas(conn, user_id)

            conn.commit()

            return {"id": user_id, "username": username, "criado_em": agora}, None
    except sqlite3.IntegrityError:
        return None, "Esse nome de utilizador já existe. Escolha outro."


def autenticar_utilizador(username: str, palavra_passe: str):
    """Verifica credenciais e autentica o utilizador."""
    username = username.strip()
    if not username or not palavra_passe:
        return None, "Preencha o nome de utilizador e a palavra-passe."

    with obter_conexao() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM utilizadores WHERE username = ? COLLATE NOCASE;", (username,))
        linha = cursor.fetchone()
        if not linha:
            return None, "Nome de utilizador ou palavra-passe incorretos."

        salt = bytes.fromhex(linha["salt"])
        hash_esperada = _gerar_hash_palavra_passe(palavra_passe, salt)
        if not secrets.compare_digest(hash_esperada, linha["password_hash"]):
            return None, "Nome de utilizador ou palavra-passe incorretos."

        user = {
            "id": linha["id"],
            "username": linha["username"],
            "criado_em": linha["criado_em"]
        }

        # Registar ação de login
        agora = datetime.now().isoformat(timespec="seconds")
        cursor.execute("""
            INSERT INTO historico (utilizador_id, tipo_acao, descricao, detalhes, criado_em)
            VALUES (?, 'SESSAO_INICIADA', 'Sessão iniciada na conta.', NULL, ?);
        """, (user["id"], agora))
        conn.commit()

        return user, None


def criar_sessao(utilizador_id: int) -> str:
    """Gera um token de sessão criptograficamente aleatório."""
    token = secrets.token_urlsafe(32)
    agora = datetime.now().isoformat(timespec="seconds")
    with obter_conexao() as conn:
        conn.execute("""
            INSERT INTO sessoes (token, utilizador_id, criado_em)
            VALUES (?, ?, ?);
        """, (token, utilizador_id, agora))
        conn.commit()
    return token


def validar_sessao(token: str):
    """Devolve os dados do utilizador associado à sessão se válida."""
    if not token:
        return None
    with obter_conexao() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.criado_em
            FROM sessoes s
            JOIN utilizadores u ON u.id = s.utilizador_id
            WHERE s.token = ?;
        """, (token,))
        linha = cursor.fetchone()
        if linha:
            return {"id": linha["id"], "username": linha["username"], "criado_em": linha["criado_em"]}
    return None


def terminar_sessao(token: str):
    """Remove a sessão indicada."""
    if not token:
        return
    with obter_conexao() as conn:
        conn.execute("DELETE FROM sessoes WHERE token = ?;", (token,))
        conn.commit()


# ----------------------------------------------------------------- Tarefas
def parse_prazo_iso(texto: str) -> str:
    """Converte 'DD/MM/AAAA' ou 'AAAA-MM-DD' para 'AAAA-MM-DD' ou string vazia."""
    texto = (texto or "").strip()
    if not texto:
        return ""
    if "-" in texto and len(texto) == 10:
        # Já está em YYYY-MM-DD
        datetime.strptime(texto, "%Y-%m-%d")
        return texto
    d = datetime.strptime(texto, FORMATO_DATA).date()
    return d.isoformat()


def listar_tarefas(utilizador_id: int, filtro: str = "todas"):
    """Lista tarefas do utilizador aplicando ordenação e filtros opcionais."""
    with obter_conexao() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, titulo, prazo, concluida, criada_em, atualizada_em
            FROM tarefas
            WHERE utilizador_id = ?
            ORDER BY concluida ASC, (prazo = '') ASC, prazo ASC, LOWER(titulo) ASC;
        """, (utilizador_id,))
        linhas = cursor.fetchall()

    tarefas = []
    hoje = date.today()
    for row in linhas:
        concluida = bool(row["concluida"])
        if filtro == "pendentes" and concluida:
            continue
        if filtro == "concluidas" and not concluida:
            continue

        prazo = row["prazo"] or ""
        estado_prazo = ""
        texto_prazo = "—"

        if prazo:
            try:
                d = date.fromisoformat(prazo)
                texto_formatado = d.strftime(FORMATO_DATA)
                if concluida:
                    texto_prazo = texto_formatado
                else:
                    dias = (d - hoje).days
                    if dias < 0:
                        estado_prazo = "atraso"
                        texto_prazo = f"{texto_formatado} (atrasada {-dias}d)"
                    elif dias == 0:
                        estado_prazo = "hoje"
                        texto_prazo = f"{texto_formatado} (hoje)"
                    elif dias == 1:
                        estado_prazo = "amanha"
                        texto_prazo = f"{texto_formatado} (amanhã)"
                    else:
                        texto_prazo = texto_formatado
            except ValueError:
                texto_prazo = prazo

        tarefas.append({
            "id": row["id"],
            "titulo": row["titulo"],
            "prazo": prazo,
            "concluida": concluida,
            "criada_em": row["criada_em"],
            "atualizada_em": row["atualizada_em"],
            "estado_prazo": estado_prazo,
            "texto_prazo": texto_prazo
        })

    return tarefas


def adicionar_tarefa(utilizador_id: int, titulo: str, prazo_texto: str = ""):
    """Cria uma nova tarefa e regista no histórico."""
    titulo = (titulo or "").strip()
    if not titulo:
        return None, "O título da tarefa não pode estar vazio."

    try:
        prazo_iso = parse_prazo_iso(prazo_texto)
    except ValueError:
        return None, "Formato de prazo inválido. Utilize DD/MM/AAAA."

    task_id = uuid.uuid4().hex
    agora = datetime.now().isoformat(timespec="seconds")

    with obter_conexao() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tarefas (id, utilizador_id, titulo, prazo, concluida, criada_em, atualizada_em)
            VALUES (?, ?, ?, ?, 0, ?, ?);
        """, (task_id, utilizador_id, titulo, prazo_iso, agora, agora))

        # Histórico
        desc = f"Adicionou a tarefa «{titulo}»"
        if prazo_iso:
            d_fmt = date.fromisoformat(prazo_iso).strftime(FORMATO_DATA)
            desc += f" com prazo para {d_fmt}."
        else:
            desc += " sem prazo."

        cursor.execute("""
            INSERT INTO historico (utilizador_id, tipo_acao, descricao, detalhes, criado_em)
            VALUES (?, 'TAREFA_CRIADA', ?, ?, ?);
        """, (utilizador_id, desc, json.dumps({"titulo": titulo, "prazo": prazo_iso}), agora))
        conn.commit()

    return {
        "id": task_id,
        "titulo": titulo,
        "prazo": prazo_iso,
        "concluida": False,
        "criada_em": agora,
        "atualizada_em": agora
    }, None


def atualizar_tarefa(utilizador_id: int, task_id: str, novo_titulo: str, novo_prazo_texto: str):
    """Atualiza título e prazo de uma tarefa existente."""
    novo_titulo = (novo_titulo or "").strip()
    if not novo_titulo:
        return None, "O título da tarefa não pode estar vazio."

    try:
        novo_prazo_iso = parse_prazo_iso(novo_prazo_texto)
    except ValueError:
        return None, "Formato de prazo inválido. Utilize DD/MM/AAAA."

    agora = datetime.now().isoformat(timespec="seconds")

    with obter_conexao() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tarefas WHERE id = ? AND utilizador_id = ?;", (task_id, utilizador_id))
        antiga = cursor.fetchone()
        if not antiga:
            return None, "Tarefa não encontrada."

        cursor.execute("""
            UPDATE tarefas
            SET titulo = ?, prazo = ?, atualizada_em = ?
            WHERE id = ? AND utilizador_id = ?;
        """, (novo_titulo, novo_prazo_iso, agora, task_id, utilizador_id))

        mudancas = []
        if antiga["titulo"] != novo_titulo:
            mudancas.append(f"título alterado para «{novo_titulo}»")
        if antiga["prazo"] != novo_prazo_iso:
            if novo_prazo_iso:
                d_fmt = date.fromisoformat(novo_prazo_iso).strftime(FORMATO_DATA)
                mudancas.append(f"prazo definido para {d_fmt}")
            else:
                mudancas.append("prazo removido")

        desc = f"Editou a tarefa «{novo_titulo}»"
        if mudancas:
            desc += f" ({', '.join(mudancas)})."
        else:
            desc += "."

        cursor.execute("""
            INSERT INTO historico (utilizador_id, tipo_acao, descricao, detalhes, criado_em)
            VALUES (?, 'TAREFA_EDITADA', ?, ?, ?);
        """, (utilizador_id, desc, json.dumps({
            "titulo_anterior": antiga["titulo"],
            "titulo_novo": novo_titulo,
            "prazo_anterior": antiga["prazo"],
            "prazo_novo": novo_prazo_iso
        }), agora))
        conn.commit()

    return {"id": task_id, "titulo": novo_titulo, "prazo": novo_prazo_iso}, None


def alternar_conclusao_tarefa(utilizador_id: int, task_id: str):
    """Alterna o estado de conclusão (concluída / reaberta) da tarefa."""
    agora = datetime.now().isoformat(timespec="seconds")

    with obter_conexao() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tarefas WHERE id = ? AND utilizador_id = ?;", (task_id, utilizador_id))
        tarefa = cursor.fetchone()
        if not tarefa:
            return None, "Tarefa não encontrada."

        novo_estado = 0 if tarefa["concluida"] else 1
        cursor.execute("""
            UPDATE tarefas
            SET concluida = ?, atualizada_em = ?
            WHERE id = ? AND utilizador_id = ?;
        """, (novo_estado, agora, task_id, utilizador_id))

        if novo_estado == 1:
            tipo = "TAREFA_CONCLUIDA"
            desc = f"Concluiu a tarefa «{tarefa['titulo']}»."
        else:
            tipo = "TAREFA_REABERTA"
            desc = f"Reabriu a tarefa «{tarefa['titulo']}» (pendente)."

        cursor.execute("""
            INSERT INTO historico (utilizador_id, tipo_acao, descricao, detalhes, criado_em)
            VALUES (?, ?, ?, ?, ?);
        """, (utilizador_id, tipo, desc, json.dumps({"titulo": tarefa["titulo"], "concluida": bool(novo_estado)}), agora))
        conn.commit()

    return {"id": task_id, "concluida": bool(novo_estado)}, None


def eliminar_tarefa(utilizador_id: int, task_id: str):
    """Elimina permanentemente a tarefa do utilizador e regista no histórico."""
    agora = datetime.now().isoformat(timespec="seconds")

    with obter_conexao() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tarefas WHERE id = ? AND utilizador_id = ?;", (task_id, utilizador_id))
        tarefa = cursor.fetchone()
        if not tarefa:
            return False, "Tarefa não encontrada."

        cursor.execute("DELETE FROM tarefas WHERE id = ? AND utilizador_id = ?;", (task_id, utilizador_id))

        desc = f"Eliminou a tarefa «{tarefa['titulo']}»."
        cursor.execute("""
            INSERT INTO historico (utilizador_id, tipo_acao, descricao, detalhes, criado_em)
            VALUES (?, 'TAREFA_ELIMINADA', ?, ?, ?);
        """, (utilizador_id, desc, json.dumps({"titulo": tarefa["titulo"]}), agora))
        conn.commit()

    return True, None


def limpar_tarefas_concluidas(utilizador_id: int):
    """Remove todas as tarefas marcadas como concluídas pelo utilizador."""
    agora = datetime.now().isoformat(timespec="seconds")

    with obter_conexao() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, titulo FROM tarefas WHERE utilizador_id = ? AND concluida = 1;", (utilizador_id,))
        concluidas = cursor.fetchall()
        total = len(concluidas)

        if total == 0:
            return 0, None

        titulos = [row["titulo"] for row in concluidas]
        cursor.execute("DELETE FROM tarefas WHERE utilizador_id = ? AND concluida = 1;", (utilizador_id,))

        desc = f"Limpou {total} tarefa(s) concluída(s)."
        cursor.execute("""
            INSERT INTO historico (utilizador_id, tipo_acao, descricao, detalhes, criado_em)
            VALUES (?, 'CONCLUIDAS_LIMPAS', ?, ?, ?);
        """, (utilizador_id, desc, json.dumps({"quantidade": total, "titulos": titulos}), agora))
        conn.commit()

    return total, None


# ----------------------------------------------------------------- Histórico
def listar_historico(utilizador_id: int, limite: int = 150):
    """Devolve a cronologia de ações do utilizador autenticado."""
    with obter_conexao() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, tipo_acao, descricao, detalhes, criado_em
            FROM historico
            WHERE utilizador_id = ?
            ORDER BY id DESC
            LIMIT ?;
        """, (utilizador_id, limite))
        linhas = cursor.fetchall()

    historico = []
    hoje_iso = date.today().isoformat()
    for row in linhas:
        criado_em = row["criado_em"]
        data_formatada = criado_em
        try:
            dt = datetime.fromisoformat(criado_em)
            if dt.date().isoformat() == hoje_iso:
                data_formatada = f"Hoje às {dt.strftime('%H:%M:%S')}"
            else:
                data_formatada = dt.strftime("%d/%m/%Y às %H:%M:%S")
        except ValueError:
            pass

        historico.append({
            "id": row["id"],
            "tipo_acao": row["tipo_acao"],
            "descricao": row["descricao"],
            "detalhes": row["detalhes"],
            "criado_em": criado_em,
            "criado_em_formatado": data_formatada
        })

    return historico


# ----------------------------------------------------------------- Migração
def _migrar_tarefas_legadas(conn, user_id: int):
    """Migra dados de ficheiro tarefas.json se existir na pasta."""
    if not LEGACY_JSON_PATH.exists():
        return
    try:
        with open(LEGACY_JSON_PATH, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, list) and dados:
            cursor = conn.cursor()
            agora = datetime.now().isoformat(timespec="seconds")
            for t in dados:
                tid = t.get("id") or uuid.uuid4().hex
                titulo = t.get("titulo", "").strip()
                if not titulo:
                    continue
                prazo = t.get("prazo", "")
                concluida = 1 if t.get("concluida") else 0
                criada_em = t.get("criada_em") or agora
                cursor.execute("""
                    INSERT OR IGNORE INTO tarefas (id, utilizador_id, titulo, prazo, concluida, criada_em, atualizada_em)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (tid, user_id, titulo, prazo, concluida, criada_em, agora))
            cursor.execute("""
                INSERT INTO historico (utilizador_id, tipo_acao, descricao, detalhes, criado_em)
                VALUES (?, 'MIGRACAO', 'Migração de tarefas anteriores do ficheiro tarefas.json.', NULL, ?);
            """, (user_id, agora))
    except Exception:
        pass
