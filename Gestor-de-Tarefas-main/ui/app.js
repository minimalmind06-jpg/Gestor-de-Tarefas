/**
 * [gestor_tarefas] · Lógica Frontend da Aplicação
 * Gestão de Sessão, Operações de Tarefas, Filtros e Histórico em Tempo Real.
 */

(() => {
  "use strict";

  // Estado da Aplicação
  const state = {
    user: null,
    token: localStorage.getItem("gestor_tarefas_token") || null,
    tasks: [],
    filter: "todas", // "todas" | "pendentes" | "concluidas"
    history: [],
    pendingAction: null // Usado para confirmações em modal
  };

  // Elementos do DOM - Ecrãs
  const screens = {
    auth: document.getElementById("auth-screen"),
    main: document.getElementById("main-screen")
  };

  // Elementos do DOM - Autenticação
  const auth = {
    tabLogin: document.getElementById("tab-login"),
    tabRegister: document.getElementById("tab-register"),
    formLogin: document.getElementById("form-login"),
    formRegister: document.getElementById("form-register"),
    alert: document.getElementById("auth-alert"),
    loginUsername: document.getElementById("login-username"),
    loginPassword: document.getElementById("login-password"),
    registerUsername: document.getElementById("register-username"),
    registerPassword: document.getElementById("register-password"),
    registerPasswordConfirm: document.getElementById("register-password-confirm")
  };

  // Elementos do DOM - Barra de Navegação & Utilizador
  const nav = {
    avatar: document.getElementById("user-avatar"),
    displayName: document.getElementById("user-display-name"),
    btnLogout: document.getElementById("btn-logout"),
    btnOpenHistory: document.getElementById("btn-open-history")
  };

  // Elementos do DOM - Tarefas
  const taskUI = {
    formQuickAdd: document.getElementById("form-quick-add"),
    inputQuickTitle: document.getElementById("quick-title"),
    inputQuickPrazo: document.getElementById("quick-prazo"),
    tasksList: document.getElementById("tasks-list"),
    tasksEmpty: document.getElementById("tasks-empty"),
    statCompleted: document.getElementById("stat-completed"),
    statOverdue: document.getElementById("stat-overdue"),
    btnClearCompleted: document.getElementById("btn-clear-completed"),
    filterTabs: document.querySelectorAll(".filter-tab"),
    countAll: document.getElementById("count-all"),
    countPending: document.getElementById("count-pending"),
    countCompleted: document.getElementById("count-completed")
  };

  // Elementos do DOM - Modal de Edição
  const modalEdit = {
    backdrop: document.getElementById("modal-edit"),
    form: document.getElementById("form-edit"),
    idInput: document.getElementById("edit-id"),
    titleInput: document.getElementById("edit-title"),
    prazoInput: document.getElementById("edit-prazo"),
    closeBtn: document.getElementById("modal-edit-close"),
    cancelBtn: document.getElementById("modal-edit-cancel")
  };

  // Elementos do DOM - Modal de Confirmação
  const modalConfirm = {
    backdrop: document.getElementById("modal-confirm"),
    message: document.getElementById("modal-confirm-msg"),
    closeBtn: document.getElementById("modal-confirm-close"),
    cancelBtn: document.getElementById("modal-confirm-cancel"),
    okBtn: document.getElementById("modal-confirm-ok")
  };

  // Elementos do DOM - Gaveta de Histórico
  const drawerHistory = {
    backdrop: document.getElementById("drawer-history"),
    list: document.getElementById("history-list"),
    loading: document.getElementById("history-loading"),
    empty: document.getElementById("history-empty"),
    closeBtn: document.getElementById("drawer-history-close"),
    refreshBtn: document.getElementById("drawer-history-refresh")
  };

  // Elemento Toast
  const toastContainer = document.getElementById("toast-container");

  // ---------------------------------------------------------------- Comunicação API
  async function apiFetch(endpoint, options = {}) {
    options.headers = options.headers || {};
    options.headers["Content-Type"] = "application/json";

    if (state.token) {
      options.headers["Authorization"] = `Bearer ${state.token}`;
    }

    try {
      const res = await fetch(endpoint, options);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.erro || "Ocorreu um erro inesperado.");
      }
      return data;
    } catch (err) {
      throw err;
    }
  }

  // ---------------------------------------------------------------- Feedback / Toasts
  function showToast(message, type = "normal") {
    const toast = document.createElement("div");
    toast.className = `toast ${type === "error" ? "toast-error" : ""}`;
    toast.innerHTML = `<span>${escapeHTML(message)}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      toast.style.transition = "all 0.2s ease";
      setTimeout(() => toast.remove(), 200);
    }, 2800);
  }

  function showAuthAlert(message, type = "error") {
    auth.alert.className = `alert alert-${type}`;
    auth.alert.textContent = message;
    auth.alert.classList.remove("hidden");
  }

  function hideAuthAlert() {
    auth.alert.classList.add("hidden");
    auth.alert.textContent = "";
  }

  function escapeHTML(str) {
    if (!str) return "";
    return str.replace(/[&<>'"]/g, tag => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "'": "&#39;",
      '"': "&quot;"
    }[tag] || tag));
  }

  // ---------------------------------------------------------------- Autenticação & Sessão
  async function verificarSessaoInicial() {
    if (!state.token) {
      mostrarEcraAuth();
      return;
    }

    try {
      const res = await apiFetch("/api/auth/me");
      state.user = res.utilizador;
      mostrarEcraPrincipal();
      await carregarTarefas();
    } catch (err) {
      state.token = null;
      localStorage.removeItem("gestor_tarefas_token");
      mostrarEcraAuth();
    }
  }

  function mostrarEcraAuth() {
    screens.main.classList.add("hidden");
    screens.auth.classList.remove("hidden");
    hideAuthAlert();
    auth.loginUsername.focus();
  }

  function mostrarEcraPrincipal() {
    screens.auth.classList.add("hidden");
    screens.main.classList.remove("hidden");

    if (state.user) {
      const initial = (state.user.username || "U").charAt(0).toUpperCase();
      nav.avatar.textContent = initial;
      nav.displayName.textContent = state.user.username;
    }

    taskUI.inputQuickTitle.focus();
  }

  // Alternar abas de Início de Sessão / Registo
  auth.tabLogin.addEventListener("click", () => {
    auth.tabLogin.classList.add("active");
    auth.tabRegister.classList.remove("active");
    auth.formLogin.classList.remove("hidden");
    auth.formRegister.classList.add("hidden");
    hideAuthAlert();
    auth.loginUsername.focus();
  });

  auth.tabRegister.addEventListener("click", () => {
    auth.tabRegister.classList.add("active");
    auth.tabLogin.classList.remove("active");
    auth.formRegister.classList.remove("hidden");
    auth.formLogin.classList.add("hidden");
    hideAuthAlert();
    auth.registerUsername.focus();
  });

  // Submeter Início de Sessão
  auth.formLogin.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAuthAlert();

    const username = auth.loginUsername.value.trim();
    const password = auth.loginPassword.value;

    if (!username || !password) {
      showAuthAlert("Por favor, preencha o nome de utilizador e a palavra-passe.");
      return;
    }

    try {
      const res = await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password })
      });

      state.token = res.token;
      state.user = res.utilizador;
      localStorage.setItem("gestor_tarefas_token", state.token);

      auth.formLogin.reset();
      mostrarEcraPrincipal();
      showToast(`Sessão iniciada com sucesso. Bem-vindo, ${state.user.username}!`);
      await carregarTarefas();
    } catch (err) {
      showAuthAlert(err.message);
    }
  });

  // Submeter Registo de Conta
  auth.formRegister.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAuthAlert();

    const username = auth.registerUsername.value.trim();
    const password = auth.registerPassword.value;
    const confirm = auth.registerPasswordConfirm.value;

    if (!username || !password) {
      showAuthAlert("Preencha todos os campos obrigatórios.");
      return;
    }

    if (password !== confirm) {
      showAuthAlert("As palavras-passe introduzidas não coincidem.");
      return;
    }

    try {
      const res = await apiFetch("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password })
      });

      state.token = res.token;
      state.user = res.utilizador;
      localStorage.setItem("gestor_tarefas_token", state.token);

      auth.formRegister.reset();
      mostrarEcraPrincipal();
      showToast(`Conta criada com sucesso! Bem-vindo ao [gestor_tarefas], ${state.user.username}!`);
      await carregarTarefas();
    } catch (err) {
      showAuthAlert(err.message);
    }
  });

  // Terminar Sessão
  nav.btnLogout.addEventListener("click", async () => {
    abrirModalConfirmacao("Tens a certeza que pretendes terminar a sessão?", async () => {
      try {
        await apiFetch("/api/auth/logout", { method: "POST" });
      } catch (err) {
        // Ignorar se já expirou
      }
      state.token = null;
      state.user = null;
      state.tasks = [];
      localStorage.removeItem("gestor_tarefas_token");
      mostrarEcraAuth();
      showToast("Sessão terminada.");
    });
  });

  // ---------------------------------------------------------------- Tarefas
  async function carregarTarefas() {
    try {
      const res = await apiFetch(`/api/tasks?filtro=${state.filter}`);
      state.tasks = res.tarefas || [];
      renderizarTarefas();
      atualizarContadores(res.resumo);
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  function renderizarTarefas() {
    taskUI.tasksList.innerHTML = "";

    if (state.tasks.length === 0) {
      taskUI.tasksEmpty.classList.remove("hidden");
      const emptyDesc = document.getElementById("empty-desc");
      if (state.filter === "pendentes") {
        emptyDesc.textContent = "Fantástico! Não tens nenhuma tarefa pendente de momento.";
      } else if (state.filter === "concluidas") {
        emptyDesc.textContent = "Ainda não concluíste nenhuma tarefa.";
      } else {
        emptyDesc.textContent = "Adiciona a tua primeira tarefa no campo acima para começar a organizar o teu dia.";
      }
      return;
    }

    taskUI.tasksEmpty.classList.add("hidden");

    state.tasks.forEach(t => {
      const li = document.createElement("li");
      li.className = `task-item ${t.concluida ? "is-completed" : ""}`;
      li.dataset.id = t.id;

      // Badges de Prazo
      let prazoHtml = "";
      if (t.texto_prazo && t.texto_prazo !== "—") {
        const badgeClass = t.estado_prazo ? `prazo-badge ${t.estado_prazo}` : "prazo-badge";
        prazoHtml = `<span class="${badgeClass}">${escapeHTML(t.texto_prazo)}</span>`;
      }

      li.innerHTML = `
        <div class="task-main">
          <button class="task-checkbox-btn" type="button" aria-label="${t.concluida ? 'Marcar pendente' : 'Concluir'}">
            <svg class="check-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
          </button>
          <span class="task-title" title="Duplo clique para editar">${escapeHTML(t.titulo)}</span>
        </div>
        <div class="task-meta">
          ${prazoHtml}
          <div class="task-actions">
            <button class="task-btn-action edit" type="button" title="Editar tarefa">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
            </button>
            <button class="task-btn-action delete" type="button" title="Eliminar tarefa">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      `;

      // Eventos da Linha
      const chkBtn = li.querySelector(".task-checkbox-btn");
      chkBtn.addEventListener("click", () => alternarTarefa(t.id));

      const titleSpan = li.querySelector(".task-title");
      titleSpan.addEventListener("dblclick", () => abrirModalEdicao(t));

      const btnEdit = li.querySelector(".task-btn-action.edit");
      btnEdit.addEventListener("click", () => abrirModalEdicao(t));

      const btnDelete = li.querySelector(".task-btn-action.delete");
      btnDelete.addEventListener("click", () => confirmarEliminacaoTarefa(t));

      taskUI.tasksList.appendChild(li);
    });
  }

  function atualizarContadores(resumo) {
    if (!resumo) return;

    taskUI.countAll.textContent = resumo.total || 0;
    taskUI.countPending.textContent = resumo.pendentes || 0;
    taskUI.countCompleted.textContent = resumo.concluidas || 0;

    taskUI.statCompleted.textContent = `${resumo.concluidas}/${resumo.total} concluídas`;

    if (resumo.atrasadas > 0) {
      taskUI.statOverdue.textContent = `${resumo.atrasadas} em atraso`;
      taskUI.statOverdue.classList.remove("hidden");
    } else {
      taskUI.statOverdue.classList.add("hidden");
    }

    // Ativar/desativar botão de limpar concluídas
    taskUI.btnClearCompleted.disabled = (resumo.concluidas === 0);
  }

  // Adição Rápida
  taskUI.formQuickAdd.addEventListener("submit", async (e) => {
    e.preventDefault();

    const titulo = taskUI.inputQuickTitle.value.trim();
    const prazo = taskUI.inputQuickPrazo.value.trim();

    if (!titulo) return;

    try {
      await apiFetch("/api/tasks", {
        method: "POST",
        body: JSON.stringify({ titulo, prazo })
      });

      taskUI.inputQuickTitle.value = "";
      taskUI.inputQuickPrazo.value = "";
      taskUI.inputQuickTitle.focus();

      showToast("Tarefa adicionada com sucesso!");
      await carregarTarefas();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Alternar Conclusão
  async function alternarTarefa(taskId) {
    try {
      const res = await apiFetch(`/api/tasks/${taskId}/toggle`, { method: "POST" });
      await carregarTarefas();
      if (res.concluida) {
        showToast("Tarefa concluída!");
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // Filtragem
  taskUI.filterTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      taskUI.filterTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      state.filter = tab.dataset.filter;
      carregarTarefas();
    });
  });

  // ---------------------------------------------------------------- Modal de Edição
  function abrirModalEdicao(tarefa) {
    modalEdit.idInput.value = tarefa.id;
    modalEdit.titleInput.value = tarefa.titulo;

    // Converter prazo de ISO (AAAA-MM-DD) para DD/MM/AAAA se existir
    let prazoTexto = "";
    if (tarefa.prazo) {
      const partes = tarefa.prazo.split("-");
      if (partes.length === 3) {
        prazoTexto = `${partes[2]}/${partes[1]}/${partes[0]}`;
      } else {
        prazoTexto = tarefa.prazo;
      }
    }
    modalEdit.prazoInput.value = prazoTexto;

    modalEdit.backdrop.classList.remove("hidden");
    modalEdit.titleInput.focus();
  }

  function fecharModalEdicao() {
    modalEdit.backdrop.classList.add("hidden");
    modalEdit.form.reset();
  }

  modalEdit.closeBtn.addEventListener("click", fecharModalEdicao);
  modalEdit.cancelBtn.addEventListener("click", fecharModalEdicao);
  modalEdit.backdrop.addEventListener("click", (e) => {
    if (e.target === modalEdit.backdrop) fecharModalEdicao();
  });

  modalEdit.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = modalEdit.idInput.value;
    const titulo = modalEdit.titleInput.value.trim();
    const prazo = modalEdit.prazoInput.value.trim();

    if (!titulo) {
      showToast("O título da tarefa não pode estar vazio.", "error");
      return;
    }

    try {
      await apiFetch(`/api/tasks/${id}`, {
        method: "PUT",
        body: JSON.stringify({ titulo, prazo })
      });
      fecharModalEdicao();
      showToast("Tarefa atualizada com sucesso!");
      await carregarTarefas();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // ---------------------------------------------------------------- Modais de Confirmação
  function abrirModalConfirmacao(mensagem, onConfirm) {
    modalConfirm.message.textContent = mensagem;
    state.pendingAction = onConfirm;
    modalConfirm.backdrop.classList.remove("hidden");
    modalConfirm.okBtn.focus();
  }

  function fecharModalConfirmacao() {
    modalConfirm.backdrop.classList.add("hidden");
    state.pendingAction = null;
  }

  modalConfirm.closeBtn.addEventListener("click", fecharModalConfirmacao);
  modalConfirm.cancelBtn.addEventListener("click", fecharModalConfirmacao);
  modalConfirm.backdrop.addEventListener("click", (e) => {
    if (e.target === modalConfirm.backdrop) fecharModalConfirmacao();
  });

  modalConfirm.okBtn.addEventListener("click", async () => {
    if (typeof state.pendingAction === "function") {
      const action = state.pendingAction;
      fecharModalConfirmacao();
      await action();
    }
  });

  function confirmarEliminacaoTarefa(tarefa) {
    abrirModalConfirmacao(`Tens a certeza que pretendes eliminar a tarefa «${tarefa.titulo}»?`, async () => {
      try {
        await apiFetch(`/api/tasks/${tarefa.id}`, { method: "DELETE" });
        showToast("Tarefa eliminada.");
        await carregarTarefas();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // Limpar Concluídas
  taskUI.btnClearCompleted.addEventListener("click", () => {
    const total = state.tasks.filter(t => t.concluida).length;
    abrirModalConfirmacao(`Tens a certeza que pretendes eliminar todas as tarefas concluídas?`, async () => {
      try {
        const res = await apiFetch("/api/tasks/clear-completed", { method: "POST" });
        showToast(`${res.removidas} tarefa(s) concluída(s) eliminada(s).`);
        await carregarTarefas();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });

  // ---------------------------------------------------------------- Histórico de Ações
  async function abrirHistorico() {
    drawerHistory.backdrop.classList.remove("hidden");
    await carregarHistorico();
  }

  function fecharHistorico() {
    drawerHistory.backdrop.classList.add("hidden");
  }

  nav.btnOpenHistory.addEventListener("click", abrirHistorico);
  drawerHistory.closeBtn.addEventListener("click", fecharHistorico);
  drawerHistory.refreshBtn.addEventListener("click", carregarHistorico);
  drawerHistory.backdrop.addEventListener("click", (e) => {
    if (e.target === drawerHistory.backdrop) fecharHistorico();
  });

  async function carregarHistorico() {
    drawerHistory.loading.classList.remove("hidden");
    drawerHistory.empty.classList.add("hidden");
    drawerHistory.list.innerHTML = "";

    try {
      const res = await apiFetch("/api/history");
      drawerHistory.loading.classList.add("hidden");
      const logs = res.historico || [];

      if (logs.length === 0) {
        drawerHistory.empty.classList.remove("hidden");
        return;
      }

      logs.forEach(item => {
        const li = document.createElement("li");
        let itemClass = "history-item";
        let bulletIcon = "•";

        if (item.tipo_acao.includes("CRIADA") || item.tipo_acao === "CONTA_CRIADA") {
          itemClass += " created";
          bulletIcon = "+";
        } else if (item.tipo_acao.includes("CONCLUIDA")) {
          itemClass += " completed";
          bulletIcon = "✓";
        } else if (item.tipo_acao.includes("ELIMINADA") || item.tipo_acao.includes("LIMPAS")) {
          itemClass += " deleted";
          bulletIcon = "✕";
        } else if (item.tipo_acao.includes("EDITADA")) {
          bulletIcon = "✎";
        } else if (item.tipo_acao.includes("SESSAO")) {
          bulletIcon = "→";
        }

        li.className = itemClass;
        li.innerHTML = `
          <div class="history-bullet">${bulletIcon}</div>
          <div class="history-content">
            <p class="history-desc">${escapeHTML(item.descricao)}</p>
            <span class="history-time">${escapeHTML(item.criado_em_formatado)}</span>
          </div>
        `;
        drawerHistory.list.appendChild(li);
      });
    } catch (err) {
      drawerHistory.loading.classList.add("hidden");
      showToast("Não foi possível carregar o histórico: " + err.message, "error");
    }
  }

  // Teclas de Atalho Globais
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!modalEdit.backdrop.classList.contains("hidden")) fecharModalEdicao();
      if (!modalConfirm.backdrop.classList.contains("hidden")) fecharModalConfirmacao();
      if (!drawerHistory.backdrop.classList.contains("hidden")) fecharHistorico();
    }
  });

  // Inicialização
  verificarSessaoInicial();
})();
