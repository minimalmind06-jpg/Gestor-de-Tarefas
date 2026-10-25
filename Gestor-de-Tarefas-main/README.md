# [gestor_tarefas]

> Aplicação moderna de organização e gestão inteligente de tarefas para uso diário e lançamento público.

---

## 🎨 Identidade Visual & Design

O **[gestor_tarefas]** foi desenhado com uma estética cuidada, moderna e acolhedora:
- **Bege (`#F8F5EE`, `#F2ECE1`, `#6D513B`)**: Base quente, superfícies de destaque e botões com acabamento requintado.
- **Cinzento (`#2B2723`, `#635C54`, `#D8D0C5`)**: Tipografia de alto contraste para leitura confortável e separadores suaves.
- **Branco (`#FFFFFF`)**: Cartões e campos em relevo com sombras subtis e efeito de profundidade.

---

## ✨ Funcionalidades Principais

### 1. Autenticação e Multi-utilizador
- **Contas Isoladas**: Cada utilizador tem a sua conta com tarefas e histórico estritamente privados.
- **Início de Sessão & Registo**: Formulários integrados com validação instantânea.
- **Segurança Robusta**: Encriptação de palavras-passe com `**************` (200 000 iterações e *salts* criptográficos de 256 bits) sem dependências externas.
- **Gestão de Sessão**: Tokens de sessão aleatórios e opção de «Terminar Sessão».

### 2. Gestão Completa de Tarefas
- **Adição Rápida**: Campo de texto ágil com suporte para submissão através da tecla `Enter`.
- **Prazos (DD/MM/AAAA)**: Suporte para prazos opcionais com deteção automática de estado:
  - 🚨 **Em atraso**: Destacado a ferrugem/terracota com contagem de dias em atraso.
  - 📌 **Hoje / Amanhã**: Realce prioritário no topo da lista.
  - 📅 **Futuros**: Formatação uniforme em `DD/MM/AAAA`.
- **Concluir / Reabrir**: Alternância com um único clique ou tecla `Espaço`.
- **Edição Detalhada**: Modal intuitivo (ou duplo clique na tarefa) para alterar título e prazo.
- **Eliminação Segura**: Diálogo de confirmação para evitar perdas acidentais.
- **Filtros Ágeis**: Separadores rápidos para consultar tarefas **Todas**, **Pendentes** ou **Concluídas**.
- **Limpeza em Massa**: Botão «Limpar concluídas» com confirmação.
- **Resumo Dinâmico**: Indicador em tempo real (ex.: `3/5 concluídas · 1 em atraso`).

### 3. Histórico de Ações por Conta
- **Painel Lateral Dedicado**: Consulta em tempo real da cronologia de ações efetuadas na conta.
- **Registo Abrangente**:
  - Criação da conta e início de sessão;
  - Tarefas adicionadas, editadas, concluídas, reabertas e eliminadas;
  - Limpeza de tarefas em bloco.
- **Selos Temporais**: Apresentação clara de datas e horas em português (ex.: «Hoje às 14:32:10»).

---

## 🗄️ Estrutura do Projeto

```
Gestor-de-Tarefas-main/
├── gestor_tarefas.py   # Ponto de entrada oficial, servidor HTTP e API REST
├── database.py         # Camada de base de dados SQLite, autenticação e histórico
├── README.md           # Documentação oficial do produto
└── ui/                 # Interface gráfica moderna
    ├── index.html      # Estrutura semântica e acessível
    ├── style.css       # Design system (paleta bege, cinzento e branco)
    └── app.js          # Lógica reativa de interface e consumo da API
```

---

## 🛡️ Base de Dados e Persistência

- Ficheiro gerado automaticamente: `gestor_tarefas.db` (SQLite com modo WAL ativado para máxima integridade e desempenho concorrente).
- Migração automática: Se existir um ficheiro `tarefas.json` legado no diretório, as tarefas anteriores são importadas de forma transparente para a primeira conta criada.
