#!/usr/bin/env python3
"""
Gestor de Tarefas
-----------------
- Adicionar, editar e eliminar tarefas
- Definir prazos (DD/MM/AAAA)
- Marcar tarefas como concluídas
- Guarda tudo automaticamente em tarefas.json (junto a este ficheiro)

Requisitos: Python 3.8+ (usa apenas a biblioteca padrão, tkinter incluído)
Executar:   python gestor_tarefas.py
"""

import json
import os
import tempfile
import tkinter as tk
import uuid
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk

# ---------------------------------------------------------------- Paleta
BEGE = "#EFE6D5"          # fundo principal
BEGE_CLARO = "#F8F3E8"    # campos / linhas
BEGE_ESCURO = "#E0D3BB"   # cabeçalhos / realces
CINZA = "#8C8780"         # texto secundário / concluídas
CINZA_CLARO = "#D6D1C8"   # bordas
CASTANHO = "#6B4423"      # botões / destaque
CASTANHO_ESCURO = "#4A2F1B"  # texto principal
CASTANHO_HOVER = "#835733"
FERRUGEM = "#9A4A2A"      # tarefas em atraso (tom castanho avermelhado)

FICHEIRO = Path(__file__).resolve().parent / "tarefas.json"
FORMATO_DATA = "%d/%m/%Y"


# ---------------------------------------------------------------- Dados
def carregar_tarefas():
    if not FICHEIRO.exists():
        return []
    try:
        with open(FICHEIRO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def guardar_tarefas(tarefas):
    """Escrita atómica: evita corromper o ficheiro se a app fechar a meio."""
    try:
        fd, tmp = tempfile.mkstemp(dir=FICHEIRO.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(tarefas, f, ensure_ascii=False, indent=2)
        os.replace(tmp, FICHEIRO)
    except OSError as e:
        messagebox.showerror("Erro ao guardar", f"Não foi possível guardar:\n{e}")


def parse_data(texto):
    """Devolve date ou None (vazio). Lança ValueError se inválida."""
    texto = texto.strip()
    if not texto:
        return None
    return datetime.strptime(texto, FORMATO_DATA).date()


# ---------------------------------------------------------------- Diálogo
class DialogoTarefa(tk.Toplevel):
    """Janela para criar/editar uma tarefa."""

    def __init__(self, pai, titulo_janela, titulo="", prazo=""):
        super().__init__(pai, bg=BEGE)
        self.title(titulo_janela)
        self.resultado = None
        self.resizable(False, False)
        self.transient(pai)

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text="Tarefa").grid(row=0, column=0, sticky="w")
        self.e_titulo = ttk.Entry(corpo, width=40)
        self.e_titulo.grid(row=1, column=0, pady=(2, 12), sticky="ew")
        self.e_titulo.insert(0, titulo)

        ttk.Label(corpo, text="Prazo (DD/MM/AAAA, opcional)").grid(row=2, column=0, sticky="w")
        self.e_prazo = ttk.Entry(corpo, width=20)
        self.e_prazo.grid(row=3, column=0, pady=(2, 16), sticky="w")
        self.e_prazo.insert(0, prazo)

        botoes = ttk.Frame(corpo)
        botoes.grid(row=4, column=0, sticky="e")
        ttk.Button(botoes, text="Cancelar", style="Sec.TButton",
                   command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(botoes, text="Guardar", command=self._ok).pack(side="right")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.e_titulo.focus_set()
        self.grab_set()
        self.wait_window()

    def _ok(self):
        titulo = self.e_titulo.get().strip()
        if not titulo:
            messagebox.showwarning("Aviso", "Escreva o nome da tarefa.", parent=self)
            return
        try:
            prazo = parse_data(self.e_prazo.get())
        except ValueError:
            messagebox.showwarning("Data inválida",
                                   "Use o formato DD/MM/AAAA (ex.: 31/12/2026).",
                                   parent=self)
            return
        self.resultado = (titulo, prazo.isoformat() if prazo else "")
        self.destroy()


# ---------------------------------------------------------------- App
class GestorTarefas(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestor de Tarefas")
        self.geometry("780x560")
        self.minsize(640, 440)
        self.configure(bg=BEGE)

        self.tarefas = carregar_tarefas()
        self.filtro = tk.StringVar(value="todas")

        self._estilos()
        self._construir()
        self._atualizar()
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    # ------------------------------------------------------------ estilos
    def _estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BEGE, foreground=CASTANHO_ESCURO,
                    font=("Segoe UI", 10))
        s.configure("TFrame", background=BEGE)
        s.configure("TLabel", background=BEGE, foreground=CASTANHO_ESCURO)
        s.configure("Titulo.TLabel", font=("Georgia", 22, "bold"), foreground=CASTANHO)
        s.configure("Info.TLabel", foreground=CINZA)

        s.configure("TEntry", fieldbackground=BEGE_CLARO, bordercolor=CINZA_CLARO,
                    lightcolor=CINZA_CLARO, darkcolor=CINZA_CLARO, padding=6)
        s.map("TEntry", bordercolor=[("focus", CASTANHO)])

        s.configure("TButton", background=CASTANHO, foreground=BEGE_CLARO,
                    borderwidth=0, padding=(14, 7), font=("Segoe UI", 10, "bold"))
        s.map("TButton", background=[("active", CASTANHO_HOVER)])
        s.configure("Sec.TButton", background=CINZA, foreground=BEGE_CLARO)
        s.map("Sec.TButton", background=[("active", "#77726B")])

        s.configure("TRadiobutton", background=BEGE, foreground=CASTANHO_ESCURO)
        s.map("TRadiobutton", background=[("active", BEGE)],
              foreground=[("selected", CASTANHO)])

        s.configure("Treeview", background=BEGE_CLARO, fieldbackground=BEGE_CLARO,
                    foreground=CASTANHO_ESCURO, rowheight=34, borderwidth=0,
                    font=("Segoe UI", 11))
        s.map("Treeview", background=[("selected", BEGE_ESCURO)],
              foreground=[("selected", CASTANHO_ESCURO)])
        s.configure("Treeview.Heading", background=BEGE_ESCURO,
                    foreground=CASTANHO, relief="flat", padding=8,
                    font=("Segoe UI", 10, "bold"))
        s.map("Treeview.Heading", background=[("active", BEGE_ESCURO)])
        s.configure("Vertical.TScrollbar", background=CINZA_CLARO,
                    troughcolor=BEGE, bordercolor=BEGE, arrowcolor=CASTANHO)

    # ------------------------------------------------------------ interface
    def _construir(self):
        topo = ttk.Frame(self, padding=(24, 20, 24, 8))
        topo.pack(fill="x")
        ttk.Label(topo, text="As minhas tarefas", style="Titulo.TLabel").pack(side="left")
        self.lbl_resumo = ttk.Label(topo, style="Info.TLabel")
        self.lbl_resumo.pack(side="right")

        # Linha de adição rápida
        add = ttk.Frame(self, padding=(24, 6))
        add.pack(fill="x")
        self.e_novo = ttk.Entry(add)
        self.e_novo.pack(side="left", fill="x", expand=True)
        self.e_novo.bind("<Return>", lambda e: self._adicionar_rapido())
        self.e_prazo = ttk.Entry(add, width=12)
        self.e_prazo.pack(side="left", padx=8)
        self.e_prazo.bind("<Return>", lambda e: self._adicionar_rapido())
        ttk.Button(add, text="+ Adicionar", command=self._adicionar_rapido).pack(side="left")
        ttk.Label(self, text="Prazo no formato DD/MM/AAAA (opcional)",
                  style="Info.TLabel", padding=(24, 0)).pack(anchor="e")

        # Filtros
        filtros = ttk.Frame(self, padding=(24, 10, 24, 4))
        filtros.pack(fill="x")
        for texto, valor in (("Todas", "todas"), ("Pendentes", "pendentes"),
                             ("Concluídas", "concluidas")):
            ttk.Radiobutton(filtros, text=texto, value=valor, variable=self.filtro,
                            command=self._atualizar).pack(side="left", padx=(0, 16))

        # Lista
        meio = ttk.Frame(self, padding=(24, 6))
        meio.pack(fill="both", expand=True)
        colunas = ("estado", "titulo", "prazo")
        self.arvore = ttk.Treeview(meio, columns=colunas, show="headings",
                                   selectmode="browse")
        self.arvore.heading("estado", text="")
        self.arvore.heading("titulo", text="Tarefa")
        self.arvore.heading("prazo", text="Prazo")
        self.arvore.column("estado", width=44, anchor="center", stretch=False)
        self.arvore.column("titulo", width=440)
        self.arvore.column("prazo", width=170, anchor="center", stretch=False)
        self.arvore.tag_configure("concluida", foreground=CINZA)
        self.arvore.tag_configure("atraso", foreground=FERRUGEM)
        self.arvore.tag_configure("hoje", foreground=CASTANHO,
                                  font=("Segoe UI", 11, "bold"))
        barra = ttk.Scrollbar(meio, orient="vertical", command=self.arvore.yview)
        self.arvore.configure(yscrollcommand=barra.set)
        self.arvore.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

        self.arvore.bind("<Double-1>", lambda e: self._editar())
        self.arvore.bind("<Button-1>", self._clique)
        self.arvore.bind("<space>", lambda e: self._alternar())
        self.arvore.bind("<Delete>", lambda e: self._eliminar())

        # Ações
        baixo = ttk.Frame(self, padding=(24, 10, 24, 20))
        baixo.pack(fill="x")
        ttk.Button(baixo, text="✔ Concluir / Reabrir", command=self._alternar).pack(side="left")
        ttk.Button(baixo, text="Editar", style="Sec.TButton",
                   command=self._editar).pack(side="left", padx=8)
        ttk.Button(baixo, text="Eliminar", style="Sec.TButton",
                   command=self._eliminar).pack(side="left")
        ttk.Button(baixo, text="Limpar concluídas", style="Sec.TButton",
                   command=self._limpar_concluidas).pack(side="right")

    # ------------------------------------------------------------ lógica
    def _persistir(self):
        guardar_tarefas(self.tarefas)  # guardar automático em cada alteração
        self._atualizar()

    def _chave_ordem(self, t):
        # pendentes primeiro; depois por prazo (sem prazo no fim)
        return (t["concluida"], t["prazo"] == "", t["prazo"], t["titulo"].lower())

    def _estado_prazo(self, t):
        if t["concluida"] or not t["prazo"]:
            return ""
        d = date.fromisoformat(t["prazo"])
        hoje = date.today()
        if d < hoje:
            return "atraso"
        if d == hoje:
            return "hoje"
        return ""

    def _texto_prazo(self, t):
        if not t["prazo"]:
            return "—"
        d = date.fromisoformat(t["prazo"])
        txt = d.strftime(FORMATO_DATA)
        if t["concluida"]:
            return txt
        dias = (d - date.today()).days
        if dias < 0:
            return f"{txt}  (atrasada {-dias}d)"
        if dias == 0:
            return f"{txt}  (hoje)"
        if dias == 1:
            return f"{txt}  (amanhã)"
        return txt

    def _atualizar(self):
        selecionada = self.arvore.focus()
        self.arvore.delete(*self.arvore.get_children())

        f = self.filtro.get()
        for t in sorted(self.tarefas, key=self._chave_ordem):
            if f == "pendentes" and t["concluida"]:
                continue
            if f == "concluidas" and not t["concluida"]:
                continue
            tags = ("concluida",) if t["concluida"] else ((self._estado_prazo(t),) if self._estado_prazo(t) else ())
            self.arvore.insert("", "end", iid=t["id"], tags=tags,
                               values=("☑" if t["concluida"] else "☐",
                                       t["titulo"], self._texto_prazo(t)))

        if selecionada and self.arvore.exists(selecionada):
            self.arvore.selection_set(selecionada)
            self.arvore.focus(selecionada)

        total = len(self.tarefas)
        feitas = sum(t["concluida"] for t in self.tarefas)
        atrasadas = sum(self._estado_prazo(t) == "atraso" for t in self.tarefas)
        resumo = f"{feitas}/{total} concluídas"
        if atrasadas:
            resumo += f"  ·  {atrasadas} em atraso"
        self.lbl_resumo.config(text=resumo)

    def _tarefa_selecionada(self):
        iid = self.arvore.focus()
        if not iid:
            messagebox.showinfo("Sem seleção", "Selecione primeiro uma tarefa.")
            return None
        return next((t for t in self.tarefas if t["id"] == iid), None)

    def _adicionar_rapido(self):
        titulo = self.e_novo.get().strip()
        if not titulo:
            return
        try:
            prazo = parse_data(self.e_prazo.get())
        except ValueError:
            messagebox.showwarning("Data inválida",
                                   "Use o formato DD/MM/AAAA (ex.: 31/12/2026).")
            return
        self.tarefas.append({
            "id": uuid.uuid4().hex,
            "titulo": titulo,
            "prazo": prazo.isoformat() if prazo else "",
            "concluida": False,
            "criada_em": datetime.now().isoformat(timespec="seconds"),
        })
        self.e_novo.delete(0, "end")
        self.e_prazo.delete(0, "end")
        self._persistir()
        self.e_novo.focus_set()

    def _alternar(self):
        t = self._tarefa_selecionada()
        if t:
            t["concluida"] = not t["concluida"]
            self._persistir()

    def _editar(self):
        t = self._tarefa_selecionada()
        if not t:
            return
        prazo = date.fromisoformat(t["prazo"]).strftime(FORMATO_DATA) if t["prazo"] else ""
        dlg = DialogoTarefa(self, "Editar tarefa", t["titulo"], prazo)
        if dlg.resultado:
            t["titulo"], t["prazo"] = dlg.resultado
            self._persistir()

    def _eliminar(self):
        t = self._tarefa_selecionada()
        if t and messagebox.askyesno("Eliminar", f"Eliminar a tarefa «{t['titulo']}»?"):
            self.tarefas.remove(t)
            self._persistir()

    def _limpar_concluidas(self):
        n = sum(t["concluida"] for t in self.tarefas)
        if n and messagebox.askyesno("Limpar", f"Eliminar {n} tarefa(s) concluída(s)?"):
            self.tarefas = [t for t in self.tarefas if not t["concluida"]]
            self._persistir()

    def _clique(self, evento):
        """Clicar na caixa ☐/☑ alterna o estado."""
        if self.arvore.identify_region(evento.x, evento.y) == "cell" \
                and self.arvore.identify_column(evento.x) == "#1":
            iid = self.arvore.identify_row(evento.y)
            if iid:
                self.arvore.focus(iid)
                self.arvore.selection_set(iid)
                self._alternar()
                return "break"

    def _fechar(self):
        guardar_tarefas(self.tarefas)
        self.destroy()


if __name__ == "__main__":
    GestorTarefas().mainloop()
