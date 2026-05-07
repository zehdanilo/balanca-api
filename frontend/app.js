(function () {
  const ADMIN_PASSWORD = "M3dic@o";

  const PRODUCT_LABELS = {
    GLP: "GLP",
    QUIMICOS: "QUÍMICOS",
    BORRA: "BORRA",
  };

  const emptyTicket = {
    id: null,
    ticket_code: "",
    status: "ABERTO",
    placa_cavalo: "",
    placa_tanque: "",
    motorista: "",
    fornecedor_cliente: "",
    transportadora: "",
    produto: "",
    especificacao_quimico: "",
    destino_procedencia: "",
    tara: null,
    num_agendamento: "",
    lacre: "",
    observacao: "",
    peso_inicial: null,
    peso_final: null,
    peso_liquido: null,
    pesagens: [],
  };

  const state = {
    tickets: [],
    activeTicket: null,
    search: "",
    status: "",
    date: "",
    saveTimer: null,
    ticketCreatePromise: null,
    operationSeq: 0,
    weighingInFlight: false,
    deletingWeighingId: null,
    adminUnlocked: false,
    adminPassword: "",
    currentUser: { username: "Balança", email: "Balança" },
    operatorLookupAttempted: false,
    operatorLookupPromise: null,
    catalogs: {
      horsePlates: [],
      tankPlates: [],
      drivers: [],
      transporters: [],
      customers: [],
      chemicalSpecs: [],
      destinations: [],
    },
    searchTouched: false,
    dialogResolver: null,
    toastSeq: 0,
    ticketsRequestSeq: 0,
  };

  const els = {
    listView: document.getElementById("list-view"),
    operationView: document.getElementById("operation-view"),
    startTicket: document.getElementById("start-ticket"),
    ticketDate: document.getElementById("ticket-date"),
    ticketSearch: document.getElementById("ticket-search"),
    statusFilter: document.getElementById("status-filter"),
    horsePlatesList: document.getElementById("horse-plates-list"),
    tankPlatesList: document.getElementById("tank-plates-list"),
    driversList: document.getElementById("drivers-list"),
    transportersList: document.getElementById("transporters-list"),
    ticketsBody: document.getElementById("tickets-body"),
    emptyTable: document.getElementById("empty-table"),
    adminLock: document.getElementById("admin-lock"),
    currentUserEmail: document.getElementById("current-user-email"),
    backToList: document.getElementById("back-to-list"),
    openPdf: document.getElementById("open-pdf"),
    ticketForm: document.getElementById("ticket-form"),
    quimicoField: document.getElementById("quimico-field"),
    lacresList: document.getElementById("lacres-list"),
    operationStatus: document.getElementById("operation-status"),
    operationTitle: document.getElementById("operation-title"),
    ticketCode: document.getElementById("ticket-code"),
    addWeighing: document.getElementById("add-weighing"),
    closeTicket: document.getElementById("close-ticket"),
    actionMessage: document.getElementById("action-message"),
    pesoInicial: document.getElementById("peso-inicial"),
    pesoFinal: document.getElementById("peso-final"),
    pesoLiquido: document.getElementById("peso-liquido"),
    weighingTimeline: document.getElementById("weighing-timeline"),
    adminModal: document.getElementById("admin-modal"),
    adminPassword: document.getElementById("admin-password"),
    adminCancel: document.getElementById("admin-cancel"),
    adminConfirm: document.getElementById("admin-confirm"),
    appModal: document.getElementById("app-modal"),
    appModalTitle: document.getElementById("app-modal-title"),
    appModalMessage: document.getElementById("app-modal-message"),
    appModalCancel: document.getElementById("app-modal-cancel"),
    appModalConfirm: document.getElementById("app-modal-confirm"),
    toastStack: document.getElementById("toast-stack"),
  };

  function field(id) {
    return document.getElementById(id);
  }

  function requestHeaders(adminPassword) {
    const headers = {
      Accept: "application/json",
      "Content-Type": "application/json",
    };

    if (adminPassword) {
      headers["X-Admin-Password"] = adminPassword;
    }

    return headers;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers: {
        ...requestHeaders(options.adminPassword || (state.adminUnlocked ? state.adminPassword : "")),
        ...(options.headers || {}),
      },
    });

    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload?.ok) {
      const message = payload?.error?.message || `Falha na API (${response.status}).`;
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }

    return payload.data;
  }

  function toastVariant(text, isError) {
    if (isError) return "error";
    if (/registrando|encerrando|abrindo|carregando|criando/i.test(text)) return "info";
    return "success";
  }

  function toastTitle(variant) {
    return {
      success: "Operação confirmada",
      error: "Atenção",
      info: "Processando",
    }[variant] || "Aviso";
  }

  function showToast(message, variant = "success", title = toastTitle(variant)) {
    if (!message) return;

    const toast = document.createElement("article");
    const id = `toast-${state.toastSeq += 1}`;
    toast.id = id;
    toast.className = `toast toast-${variant}`;
    toast.setAttribute("role", "status");

    const content = document.createElement("div");
    const heading = document.createElement("strong");
    const body = document.createElement("p");
    const closeButton = document.createElement("button");
    heading.textContent = title;
    body.textContent = message;
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", "Fechar aviso");
    closeButton.textContent = "x";
    content.append(heading, body);
    toast.append(content, closeButton);

    const close = () => {
      toast.remove();
    };
    closeButton.addEventListener("click", close);
    els.toastStack.prepend(toast);
    setTimeout(close, variant === "error" ? 5200 : 3600);
  }

  function setMessage(text, isError) {
    els.actionMessage.textContent = text || "";
    if (text) {
      const variant = toastVariant(text, isError);
      showToast(text, variant);
    }
  }

  function resolveAppModal(accepted) {
    if (!state.dialogResolver) return;
    const resolver = state.dialogResolver;
    state.dialogResolver = null;
    els.appModal.classList.add("hidden");
    resolver(Boolean(accepted));
  }

  function openAppModal({ title, message, confirmText = "Confirmar", cancelText = "Cancelar", showCancel = true, danger = false }) {
    if (state.dialogResolver) {
      resolveAppModal(false);
    }

    els.appModalTitle.textContent = title;
    els.appModalMessage.textContent = message;
    els.appModalConfirm.textContent = confirmText;
    els.appModalCancel.textContent = cancelText;
    els.appModalCancel.classList.toggle("hidden", !showCancel);
    els.appModalConfirm.classList.toggle("btn-danger", danger);
    els.appModalConfirm.classList.toggle("btn-primary", !danger);
    els.appModal.classList.remove("hidden");
    setTimeout(() => els.appModalConfirm.focus(), 0);

    return new Promise((resolve) => {
      state.dialogResolver = resolve;
    });
  }

  function showNotice(title, message) {
    return openAppModal({
      title,
      message,
      confirmText: "Entendi",
      showCancel: false,
    });
  }

  function confirmOperation(title, message, options = {}) {
    return openAppModal({
      title,
      message,
      confirmText: options.confirmText || "Confirmar",
      cancelText: options.cancelText || "Cancelar",
      showCancel: true,
      danger: Boolean(options.danger),
    });
  }

  function debounce(fn, delay) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  const debouncedLoadTickets = debounce(loadTickets, 280);

  function clearInjectedSearchValue() {
    if (!els.ticketSearch || state.search || state.searchTouched || document.activeElement === els.ticketSearch) {
      return;
    }

    if (els.ticketSearch.value) {
      els.ticketSearch.value = "";
    }
  }

  function blockSearchAutofill() {
    clearInjectedSearchValue();
    [80, 250, 700, 1400].forEach((delay) => {
      setTimeout(clearInjectedSearchValue, delay);
    });
  }

  function todayGmt3() {
    const now = new Date();
    const gmt3 = new Date(now.getTime() - 3 * 60 * 60 * 1000);
    const year = gmt3.getUTCFullYear();
    const month = String(gmt3.getUTCMonth() + 1).padStart(2, "0");
    const day = String(gmt3.getUTCDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function isoToPtBrDate(value) {
    const [year, month, day] = String(value || "").split("-");
    if (!year || !month || !day) return "";
    return `${day}/${month}/${year}`;
  }

  function ptBrToIsoDate(value) {
    const match = String(value || "").match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!match) return "";
    const [, day, month, year] = match;
    const parsed = new Date(`${year}-${month}-${day}T00:00:00`);
    if (
      Number.isNaN(parsed.getTime()) ||
      parsed.getFullYear() !== Number(year) ||
      parsed.getMonth() + 1 !== Number(month) ||
      parsed.getDate() !== Number(day)
    ) {
      return "";
    }
    return `${year}-${month}-${day}`;
  }

  function maskPtBrDate(value) {
    const digits = String(value || "").replace(/\D/g, "").slice(0, 8);
    if (digits.length <= 2) return digits;
    if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
    return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
  }

  function pad2(value) {
    return String(value).padStart(2, "0");
  }

  function formatKg(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "-- kg";
    }
    return `${Number(value).toLocaleString("pt-BR")} kg`;
  }

  function normalizeText(value) {
    return String(value || "").trim().replace(/\s+/g, " ").toLocaleUpperCase("pt-BR");
  }

  function operatorLabel(value) {
    const normalized = normalizeText(value);
    const ignored = new Set(["", "BALANCA", "BALANÇA", "USUARIO NAO IDENTIFICADO", "USUÁRIO NÃO IDENTIFICADO"]);
    return ignored.has(normalized) ? "Balança" : normalized;
  }

  function weighingCreatedTime(record) {
    const date = new Date(record?.created_at || record?.data_hora || 0);
    const time = date.getTime();
    return Number.isNaN(time) ? 0 : time;
  }

  function orderedWeighings(rows) {
    return [...(rows || [])].sort((a, b) => {
      const byCreatedAt = weighingCreatedTime(a) - weighingCreatedTime(b);
      if (byCreatedAt !== 0) return byCreatedAt;
      return Number(a?.id || 0) - Number(b?.id || 0);
    });
  }

  function normalizeOptionalInteger(value) {
    const normalized = String(value ?? "").trim();
    if (!normalized) return null;
    const parsed = Number.parseInt(normalized, 10);
    return Number.isNaN(parsed) ? null : Math.max(parsed, 0);
  }

  function splitLacres(value) {
    return String(value || "")
      .split(/[,;\n]+/)
      .map(normalizeText)
      .filter(Boolean);
  }

  function updateLacreRemoveState() {
    const rows = [...els.lacresList.querySelectorAll(".lacre-row")];
    rows.forEach((row) => {
      const removeButton = row.querySelector("[data-lacre-action='remove']");
      if (removeButton) {
        removeButton.disabled = rows.length <= 1 && !row.querySelector("input")?.value.trim();
      }
    });
  }

  function addLacreInput(value = "") {
    const row = document.createElement("div");
    row.className = "lacre-row";
    row.innerHTML = `
      <input name="lacre_item" autocomplete="off" maxlength="80" data-uppercase value="${escapeHtml(value)}" />
      <button class="lacre-icon-btn" data-lacre-action="remove" type="button" title="Remover lacre" aria-label="Remover lacre">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"/></svg>
      </button>
    `;
    els.lacresList.appendChild(row);
    updateLacreRemoveState();
    return row.querySelector("input");
  }

  function renderLacres(value) {
    els.lacresList.innerHTML = "";
    const lacres = splitLacres(value);
    (lacres.length ? lacres : [""]).forEach(addLacreInput);
    updateLacreRemoveState();
  }

  function lacresFromForm() {
    return [...els.lacresList.querySelectorAll("input[name='lacre_item']")]
      .map((input) => normalizeText(input.value))
      .filter(Boolean)
      .join(", ");
  }

  function currentOperatorNameForPayload() {
    return operatorLabel(state.currentUser.username);
  }

  function uppercaseInput(input) {
    if (!input?.hasAttribute("data-uppercase")) return;
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const upperValue = input.value.toLocaleUpperCase("pt-BR");
    if (input.value === upperValue) return;
    input.value = upperValue;
    if (typeof start === "number" && typeof end === "number") {
      input.setSelectionRange(start, end);
    }
  }

  function bindUppercaseInputs() {
    els.ticketForm.querySelectorAll("[data-uppercase]").forEach((input) => {
      if (input.dataset.uppercaseBound === "true") return;
      input.dataset.uppercaseBound = "true";
      input.addEventListener("input", () => uppercaseInput(input));
    });
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char]));
  }

  function foldText(value) {
    return normalizeText(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function catalogValues(rows, key) {
    return [...new Set(rows.map((row) => normalizeText(row[key])).filter(Boolean))];
  }

  function mergeCatalogValues(currentValues, rows, key) {
    return [...new Set([...(currentValues || []), ...catalogValues(rows, key)])].filter(Boolean);
  }

  function addCatalogValue(catalogName, value) {
    const normalized = normalizeText(value);
    if (!normalized) return;
    const values = state.catalogs[catalogName] || (state.catalogs[catalogName] = []);
    const index = values.findIndex((item) => foldText(item) === foldText(normalized));
    if (index >= 0) {
      values.splice(index, 1);
    }
    values.unshift(normalized);
    values.length = Math.min(values.length, 1000);
  }

  function syncLocalCatalogsFromTicket(ticket) {
    addCatalogValue("horsePlates", ticket.placa_cavalo);
    addCatalogValue("tankPlates", ticket.placa_tanque);
    addCatalogValue("drivers", ticket.motorista);
    addCatalogValue("transporters", ticket.transportadora);
    addCatalogValue("customers", ticket.fornecedor_cliente);
    addCatalogValue("chemicalSpecs", ticket.especificacao_quimico);
    addCatalogValue("destinations", ticket.destino_procedencia);
  }

  function highlightedCatalogValue(value, query) {
    const normalizedValue = normalizeText(value);
    const normalizedQuery = normalizeText(query);
    if (!normalizedQuery) return escapeHtml(normalizedValue);

    const index = normalizedValue.indexOf(normalizedQuery);
    if (index < 0) return escapeHtml(normalizedValue);

    return [
      escapeHtml(normalizedValue.slice(0, index)),
      `<mark>${escapeHtml(normalizedValue.slice(index, index + normalizedQuery.length))}</mark>`,
      escapeHtml(normalizedValue.slice(index + normalizedQuery.length)),
    ].join("");
  }

  function renderDatalist(listEl, rows, key) {
    listEl.innerHTML = "";
    rows.forEach((row) => {
      const option = document.createElement("option");
      option.value = row[key];
      listEl.appendChild(option);
    });
  }

  function renderAutocomplete(input, panel, values, activeIndex = -1, onSelect = () => {}) {
    if (input.disabled) {
      input.closest("label")?.classList.remove("autocomplete-open");
      return -1;
    }

    const query = foldText(input.value);
    const matches = values
      .filter((value) => !query || foldText(value).includes(query))
      .slice(0, 9);

    panel.innerHTML = "";
    if (!matches.length) {
      panel.innerHTML = '<div class="autocomplete-empty">Nenhum cadastro encontrado.</div>';
      input.closest("label")?.classList.add("autocomplete-open");
      return -1;
    }

    const selectedIndex = Math.max(-1, Math.min(activeIndex, matches.length - 1));
    matches.forEach((value, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `autocomplete-option${index === selectedIndex ? " active" : ""}`;
      button.innerHTML = highlightedCatalogValue(value, input.value);
      button.addEventListener("mousedown", (event) => {
        event.preventDefault();
        onSelect(value);
      });
      panel.appendChild(button);
    });

    input.closest("label")?.classList.add("autocomplete-open");
    return selectedIndex;
  }

  function bindCatalogAutocomplete(input, values) {
    if (!input || input.dataset.autocompleteBound === "true") return;

    input.dataset.autocompleteBound = "true";
    input.removeAttribute("list");
    const label = input.closest("label");
    const panel = document.createElement("div");
    panel.className = "autocomplete-panel";
    panel.setAttribute("role", "listbox");
    label.appendChild(panel);

    let activeIndex = -1;
    let selecting = false;
    const close = () => {
      activeIndex = -1;
      panel.innerHTML = "";
      label.classList.remove("autocomplete-open");
    };
    const selectValue = (value) => {
      selecting = true;
      input.value = value;
      close();
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      selecting = false;
      input.focus();
    };
    const open = () => {
      activeIndex = renderAutocomplete(input, panel, values, activeIndex, selectValue);
    };

    input.addEventListener("focus", open);
    input.addEventListener("input", () => {
      if (selecting) return;
      uppercaseInput(input);
      activeIndex = -1;
      open();
    });
    input.addEventListener("keydown", (event) => {
      const options = [...panel.querySelectorAll(".autocomplete-option")];
      if (event.key === "Escape") {
        close();
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        activeIndex = Math.min(activeIndex + 1, Math.max(options.length - 1, 0));
        renderAutocomplete(input, panel, values, activeIndex, selectValue);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        renderAutocomplete(input, panel, values, activeIndex, selectValue);
        return;
      }
      if (event.key === "Enter" && activeIndex >= 0 && options[activeIndex]) {
        event.preventDefault();
        options[activeIndex].dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
      }
    });
    input.addEventListener("blur", () => {
      setTimeout(close, 120);
    });
  }

  function setupCatalogAutocomplete() {
    els.ticketForm.querySelectorAll("[data-catalog]").forEach((input) => {
      bindCatalogAutocomplete(input, state.catalogs[input.dataset.catalog] || []);
    });
  }

  async function loadCatalogs() {
    try {
      const [horsePlates, tankPlates, drivers, transporters, customers, chemicalSpecs, destinations] = await Promise.all([
        api("/catalog/horse-plates?limit=1000"),
        api("/catalog/tank-plates?limit=1000"),
        api("/catalog/drivers?limit=1000"),
        api("/catalog/transporters?limit=1000"),
        api("/catalog/customers?limit=1000"),
        api("/catalog/chemical-specs?limit=1000"),
        api("/catalog/destinations?limit=1000"),
      ]);
      state.catalogs = {
        horsePlates: mergeCatalogValues(state.catalogs.horsePlates, horsePlates, "placa"),
        tankPlates: mergeCatalogValues(state.catalogs.tankPlates, tankPlates, "placa"),
        drivers: mergeCatalogValues(state.catalogs.drivers, drivers, "nome"),
        transporters: mergeCatalogValues(state.catalogs.transporters, transporters, "nome"),
        customers: mergeCatalogValues(state.catalogs.customers, customers, "nome"),
        chemicalSpecs: mergeCatalogValues(state.catalogs.chemicalSpecs, chemicalSpecs, "nome"),
        destinations: mergeCatalogValues(state.catalogs.destinations, destinations, "nome"),
      };
      renderDatalist(els.horsePlatesList, horsePlates, "placa");
      renderDatalist(els.tankPlatesList, tankPlates, "placa");
      renderDatalist(els.driversList, drivers, "nome");
      renderDatalist(els.transportersList, transporters, "nome");
      setupCatalogAutocomplete();
    } catch (error) {
      setMessage(`Falha ao carregar cadastros: ${error.message}`, true);
    }
  }

  async function loadCurrentOperator({ force = false } = {}) {
    const authUnavailable = window.sessionStorage.getItem("balancaWindowsAuthUnavailable") === "1";
    if (!force && (authUnavailable || state.operatorLookupAttempted)) {
      els.currentUserEmail.textContent = state.currentUser.username;
      els.currentUserEmail.title = state.currentUser.username;
      return state.currentUser;
    }

    if (state.operatorLookupPromise) {
      await state.operatorLookupPromise;
      return state.currentUser;
    }

    state.operatorLookupAttempted = true;
    els.currentUserEmail.textContent = "Identificando...";
    els.currentUserEmail.title = "Identificando usuario do Windows";

    state.operatorLookupPromise = (async () => {
      const response = await fetch(`/whoami?t=${Date.now()}`, {
        cache: "no-store",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload?.ok) {
        const error = new Error(payload?.error?.message || `Falha na API (${response.status}).`);
        error.status = response.status;
        throw error;
      }
      if (!payload.data?.authenticated) {
        const error = new Error("Usuario Windows nao identificado.");
        error.status = 401;
        throw error;
      }
      return payload.data;
    })();

    try {
      const user = await state.operatorLookupPromise;
      const email = user?.email || user?.username || "Balança";
      const username = user?.username || String(email).split("@")[0] || "Balança";
      state.currentUser = {
        username,
        email,
      };
      window.sessionStorage.removeItem("balancaWindowsAuthUnavailable");
    } catch (error) {
      state.currentUser = { username: "Balança", email: "Balança" };
      window.sessionStorage.setItem("balancaWindowsAuthUnavailable", "1");
    } finally {
      state.operatorLookupPromise = null;
    }

    els.currentUserEmail.textContent = state.currentUser.username;
    els.currentUserEmail.title = state.currentUser.username;
    return state.currentUser;
  }

  function formatDate(value) {
    if (!value) return "--";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "--";
    return `${pad2(date.getDate())}/${pad2(date.getMonth() + 1)}/${date.getFullYear()} ${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`;
  }

  function formatDateOnly(value) {
    if (!value) return "--";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "--";
    return `${pad2(date.getDate())}/${pad2(date.getMonth() + 1)}/${date.getFullYear()}`;
  }

  function formatTimeOnly(value) {
    if (!value) return "--";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "--";
    return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
  }

  function productLabel(ticket) {
    const label = PRODUCT_LABELS[ticket.produto] || ticket.produto || "--";
    if (ticket.produto === "QUIMICOS" && ticket.especificacao_quimico) {
      return `${label} (${ticket.especificacao_quimico.toUpperCase()})`;
    }
    return label;
  }

  function weighingBySequence(ticket, sequence) {
    return orderedWeighings(ticket.pesagens).find((record) => Number(record.sequencia) === sequence);
  }

  function weighingTableCell(ticket, sequence) {
    const record = weighingBySequence(ticket, sequence);
    if (!record) {
      return '<td class="weighing-cell muted-cell">--</td>';
    }

    return `
      <td class="weighing-cell">
        <strong>${formatKg(record.peso)}</strong>
        <div class="weighing-time">${formatTimeOnly(record.data_hora)}</div>
      </td>
    `;
  }

  function liquidWeight(ticket) {
    const count = Number(ticket.pesagens_count ?? ticket.pesagens?.length ?? 0);
    const hasTara = Number(ticket?.tara || 0) > 0;
    if (count === 1 && hasTara) return ticket.peso_liquido;
    if (count % 2 !== 0) return null;
    return ticket.peso_liquido;
  }

  function weighingCountLabel(ticket) {
    const count = Number(ticket.pesagens_count ?? ticket.pesagens?.length ?? 0);
    return `${count} ${count <= 1 ? "pesagem" : "pesagens"}`;
  }

  function pairLiquidWeight(pesagens, record, ticket) {
    if (record.sequencia % 2 !== 0) return "";
    const previous = pesagens[record.sequencia - 2];
    if (!previous) return "";
    const pairLiquid = Math.abs(Number(previous.peso) - Number(record.peso));
    const tara = record.sequencia === 2 ? Number(ticket?.tara || 0) : 0;
    return formatKg(Math.max(pairLiquid - tara, 0));
  }

  function scaleLabel(value) {
    const normalized = String(value || "").trim();
    if (!normalized || normalized === "Balança 020" || normalized === "Balanca 020") {
      return "Balança 002";
    }
    return normalized;
  }

  function statusLabel(status) {
    return {
      ABERTO: "Aberto",
      EM_ANDAMENTO: "Em andamento",
      COMPLETO: "Encerrado",
    }[status] || status || "Aberto";
  }

  function shortTicketCode(ticket) {
    if (ticket?.id) {
      return `T-${String(ticket.id).padStart(5, "0")}`;
    }
    return ticket?.ticket_code || "--";
  }

  function isLocked(ticket) {
    return ticket?.status === "COMPLETO";
  }

  function hasWeighings(ticket) {
    return Number(ticket?.pesagens_count ?? ticket?.pesagens?.length ?? 0) > 0;
  }

  function isInProgress(ticket) {
    return ticket?.status === "EM_ANDAMENTO" || (!isLocked(ticket) && hasWeighings(ticket));
  }

  function canCloseTicket(ticket) {
    const count = ticket?.pesagens?.length || 0;
    const hasTara = Number(ticket?.tara || 0) > 0;
    return Boolean(ticket?.id) && !isLocked(ticket) && count > 0 && (count % 2 === 0 || (count === 1 && hasTara));
  }

  function hasAdminConfirmation() {
    return state.adminUnlocked;
  }

  function updateAdminState() {
    els.adminLock.classList.toggle("unlocked", hasAdminConfirmation());
    els.adminLock.title = hasAdminConfirmation() ? "Bloquear modo admin" : "Liberar modo admin";
    els.adminLock.setAttribute(
      "aria-label",
      hasAdminConfirmation() ? "Bloquear modo admin" : "Liberar modo admin"
    );
    renderTickets();
    if (state.activeTicket) {
      renderOperation();
    }
  }

  function ticketFromForm() {
    return {
      placa_cavalo: normalizeText(field("placaCavalo").value),
      placa_tanque: normalizeText(field("placaTanque").value),
      motorista: normalizeText(field("motorista").value),
      fornecedor_cliente: normalizeText(field("fornecedorCliente").value),
      transportadora: normalizeText(field("transportadora").value),
      produto: field("produto").value,
      especificacao_quimico: normalizeText(field("especificacaoQuimico").value),
      destino_procedencia: normalizeText(field("destinoProcedencia").value),
      tara: normalizeOptionalInteger(field("tara").value),
      num_agendamento: normalizeText(field("numAgendamento").value),
      lacre: lacresFromForm(),
      observacao: normalizeText(field("observacao").value),
    };
  }

  function fillForm(ticket) {
    field("placaCavalo").value = normalizeText(ticket.placa_cavalo);
    field("placaTanque").value = normalizeText(ticket.placa_tanque);
    field("motorista").value = normalizeText(ticket.motorista);
    field("fornecedorCliente").value = normalizeText(ticket.fornecedor_cliente);
    field("transportadora").value = normalizeText(ticket.transportadora);
    field("produto").value = ticket.produto || "";
    field("especificacaoQuimico").value = normalizeText(ticket.especificacao_quimico);
    field("destinoProcedencia").value = normalizeText(ticket.destino_procedencia);
    field("tara").value = ticket.tara ?? "";
    field("numAgendamento").value = normalizeText(ticket.num_agendamento);
    renderLacres(ticket.lacre);
    field("observacao").value = normalizeText(ticket.observacao);
    els.quimicoField.classList.toggle("hidden", ticket.produto !== "QUIMICOS");
  }

  function setFormLocked(locked, protectedLocked = false) {
    const protectedIds = ["placaCavalo", "placaTanque"];
    els.ticketForm.classList.toggle("locked", locked);
    els.ticketForm.classList.toggle("protected-locked", protectedLocked && !locked);
    els.ticketForm.querySelectorAll("input, select, [data-lacre-action]").forEach((control) => {
      control.disabled = locked || (protectedLocked && protectedIds.includes(control.id));
    });
  }

  function validateHeader(ticket) {
    const errors = [];
    const required = [
      ["placa_cavalo", "Placa Cavalo"],
      ["placa_tanque", "Placa Tanque"],
      ["motorista", "Motorista"],
      ["fornecedor_cliente", "Fornecedor/Cliente"],
      ["transportadora", "Transportadora"],
      ["produto", "Produto"],
      ["destino_procedencia", "Destino/Procedência"],
    ];

    required.forEach(([key, label]) => {
      if (!String(ticket[key] || "").trim()) errors.push(label);
    });

    if (ticket.produto === "QUIMICOS" && !ticket.especificacao_quimico.trim()) {
      errors.push("Especificação do Químico");
    }

    return errors;
  }

  function actionButtonForTicket(ticket) {
    const editDisabled = isLocked(ticket) && !hasAdminConfirmation() ? "disabled" : "";
    const deleteDisabled = (isLocked(ticket) || hasWeighings(ticket)) && !hasAdminConfirmation() ? "disabled" : "";
    const disabled = editDisabled;
    const effectiveDeleteTitle = deleteDisabled ? "Modo admin necessario" : "Excluir";
    const editTitle = disabled ? "Modo admin necessário" : "Editar";
    const deleteTitle = disabled ? "Modo admin necessário" : "Excluir";

    return `
      <button class="action-btn icon-only" data-action="view" data-id="${ticket.id}" type="button" title="Visualizar" aria-label="Visualizar ticket">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.25 12s3.5-6 9.75-6 9.75 6 9.75 6-3.5 6-9.75 6-9.75-6-9.75-6Z"/><circle cx="12" cy="12" r="2.75"/></svg>
      </button>
      <button class="action-btn icon-only" data-action="edit" data-id="${ticket.id}" type="button" title="${editTitle}" aria-label="${editTitle}" ${editDisabled}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4.5L19.2 9.3a2.1 2.1 0 0 0 0-3L17.7 4.8a2.1 2.1 0 0 0-3 0L4 15.5V20Z"/><path d="m13.5 6 4.5 4.5"/></svg>
      </button>
      <button class="action-btn icon-only danger" data-action="delete" data-id="${ticket.id}" type="button" title="${effectiveDeleteTitle}" aria-label="${effectiveDeleteTitle}" ${deleteDisabled}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M6.5 7l1 13h9l1-13"/><path d="M9 7V4h6v3"/></svg>
      </button>
    `;
  }

  function renderTickets() {
    els.ticketsBody.innerHTML = "";
    els.emptyTable.style.display = state.tickets.length ? "none" : "block";
    els.emptyTable.textContent = "Nenhum ticket encontrado.";

    state.tickets.forEach((ticket) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="date-cell">${formatDateOnly(ticket.created_at || ticket.updated_at)}</td>
        <td>
          <div class="ticket-code-cell">${shortTicketCode(ticket)}</div>
          <div class="ticket-count">${weighingCountLabel(ticket)}</div>
        </td>
        <td><span class="status-badge status-${ticket.status}">${statusLabel(ticket.status)}</span></td>
        <td>${ticket.motorista || "--"}</td>
        <td class="product-cell">${productLabel(ticket)}</td>
        ${weighingTableCell(ticket, 1)}
        ${weighingTableCell(ticket, 2)}
        <td><strong>${formatKg(liquidWeight(ticket))}</strong></td>
        <td>
          <div class="row-actions">
            ${actionButtonForTicket(ticket)}
          </div>
        </td>
      `;

      tr.addEventListener("click", (event) => {
        if (event.target.closest("button")) return;
        if (ticket.status === "COMPLETO") {
          openTicketPdf(ticket.id);
          return;
        }
        openTicket(ticket.id, false);
      });

      els.ticketsBody.appendChild(tr);
    });
  }

  function renderTicketsLoading() {
    els.emptyTable.style.display = "none";
    els.ticketsBody.innerHTML = `
      <tr class="loading-row">
        <td colspan="9">
          <div class="loading-box">
            <span class="table-loader" aria-label="Buscando informações no banco"></span>
            <div>
              <strong>Buscando informações no banco</strong>
              <span>Aguarde enquanto os registros são atualizados.</span>
            </div>
          </div>
        </td>
      </tr>
    `;
  }

  function renderOperation() {
    const ticket = state.activeTicket || emptyTicket;
    const pesagens = orderedWeighings(ticket.pesagens);

    els.operationStatus.textContent = statusLabel(ticket.status).toUpperCase();
    els.operationTitle.textContent = ticket.id ? `Ticket ${shortTicketCode(ticket)}` : "Nova pesagem";
    els.ticketCode.textContent = ticket.id ? shortTicketCode(ticket) : "--";
    els.pesoInicial.textContent = formatKg(ticket.peso_inicial);
    els.pesoFinal.textContent = formatKg(ticket.peso_final);
    els.pesoLiquido.textContent = formatKg(liquidWeight(ticket));
    const showCloseAction = canCloseTicket(ticket);
    const adminMissing = !hasAdminConfirmation();
    setFormLocked(isLocked(ticket) && adminMissing, isInProgress(ticket) && adminMissing);
    els.addWeighing.classList.toggle("hidden", isLocked(ticket));
    els.addWeighing.disabled = isLocked(ticket) || state.weighingInFlight;
    els.addWeighing.textContent = state.weighingInFlight ? "Registrando..." : "Nova leitura";
    els.closeTicket.classList.toggle("hidden", !showCloseAction);
    const canViewTicket = pesagens.length > 0;
    els.openPdf.classList.toggle("hidden", !canViewTicket);
    els.openPdf.disabled = !canViewTicket;
    els.openPdf.title = canViewTicket ? "Visualizar ticket" : "Registre ao menos uma pesagem para visualizar o ticket";

    els.weighingTimeline.innerHTML = "";
    if (!pesagens.length) {
      els.weighingTimeline.innerHTML = '<div class="subtle">Nenhuma leitura registrada para este ticket.</div>';
      return;
    }

    pesagens.forEach((record) => {
      const canDeleteWeighing = hasAdminConfirmation() && record.id;
      const isDeleting = Number(state.deletingWeighingId) === Number(record.id);
      const item = document.createElement("article");
      item.className = "timeline-item";
      item.innerHTML = `
        <div class="sequence-dot">${record.sequencia}</div>
        <div>
          <div class="timeline-title-row">
            <h4>Pesagem ${record.sequencia} - ${record.tipo === "SAIDA" ? "Saída" : "Entrada"}</h4>
            ${canDeleteWeighing ? `
              <button
                class="timeline-delete"
                data-delete-weighing="${record.id}"
                type="button"
                title="Excluir pesagem"
                aria-label="Excluir pesagem ${record.sequencia}"
                ${isDeleting ? "disabled" : ""}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M3 6h18"/>
                  <path d="M8 6V4h8v2"/>
                  <path d="M19 6l-1 14H6L5 6"/>
                  <path d="M10 11v5"/>
                  <path d="M14 11v5"/>
                </svg>
              </button>
            ` : ""}
          </div>
          <p>${formatDate(record.data_hora)} • ${scaleLabel(record.balanca)} • ${operatorLabel(record.operador)}</p>
        </div>
        <div class="timeline-weight">${formatKg(record.peso)}</div>
      `;
      els.weighingTimeline.appendChild(item);

      const pairLiquid = pairLiquidWeight(pesagens, record, ticket);
      if (pairLiquid) {
        const pairItem = document.createElement("article");
        pairItem.className = "pair-liquid-row";
        pairItem.innerHTML = `<span>Peso líquido parcial</span><strong>${pairLiquid}</strong>`;
        els.weighingTimeline.appendChild(pairItem);
      }
    });
  }

  function showList() {
    state.operationSeq += 1;
    clearTimeout(state.saveTimer);
    state.saveTimer = null;
    state.ticketCreatePromise = null;
    state.activeTicket = null;
    els.operationView.classList.add("hidden");
    els.listView.classList.remove("hidden");
    loadTickets();
  }

  function showOperation(ticket) {
    state.operationSeq += 1;
    clearTimeout(state.saveTimer);
    state.saveTimer = null;
    state.ticketCreatePromise = null;
    state.activeTicket = ticket;
    fillForm(ticket);
    renderOperation();
    els.listView.classList.add("hidden");
    els.operationView.classList.remove("hidden");
  }

  async function loadTickets() {
    const requestId = state.ticketsRequestSeq += 1;
    const params = new URLSearchParams();
    if (state.search) params.set("q", state.search);
    if (state.status) params.set("status", state.status);
    if (state.date) params.set("date", state.date);
    params.set("limit", "200");

    renderTicketsLoading();

    try {
      const tickets = await api(`/tickets?${params.toString()}`);
      if (requestId !== state.ticketsRequestSeq) return;
      state.tickets = tickets;
      renderTickets();
    } catch (error) {
      if (requestId !== state.ticketsRequestSeq) return;
      state.tickets = [];
      renderTickets();
      els.emptyTable.style.display = "block";
      els.emptyTable.textContent = error.message;
    }
  }

  async function createTicketIfNeeded() {
    if (state.activeTicket?.id) return state.activeTicket;
    if (state.ticketCreatePromise) return state.ticketCreatePromise;

    const draftTicket = state.activeTicket;
    const seq = state.operationSeq;
    const payload = { ...(draftTicket || {}), ...ticketFromForm() };
    state.ticketCreatePromise = api("/tickets", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((ticket) => {
      if (state.operationSeq === seq && (state.activeTicket === draftTicket || !state.activeTicket?.id)) {
        state.activeTicket = ticket;
        syncLocalCatalogsFromTicket(ticket);
        renderOperation();
      }
      return ticket;
    }).finally(() => {
      if (state.operationSeq === seq) {
        state.ticketCreatePromise = null;
      }
    });

    return state.ticketCreatePromise;
  }

  async function persistActiveTicket() {
    if (!state.activeTicket) return null;
    const seq = state.operationSeq;
    const targetTicket = state.activeTicket;
    const data = ticketFromForm();
    state.activeTicket = { ...state.activeTicket, ...data };
    els.quimicoField.classList.toggle("hidden", data.produto !== "QUIMICOS");
    renderOperation();

    try {
      const ticket = await createTicketIfNeeded();
      if (state.operationSeq !== seq || (!targetTicket?.id && state.activeTicket?.id !== ticket?.id)) {
        return null;
      }
      if (targetTicket?.id && state.activeTicket?.id !== targetTicket.id) {
        return null;
      }
      const updated = await api(`/tickets/${ticket.id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
      if (state.operationSeq !== seq || state.activeTicket?.id !== updated.id) {
        return null;
      }
      state.activeTicket = updated;
      syncLocalCatalogsFromTicket(updated);
      renderOperation();
      loadTickets();
      return updated;
    } catch (error) {
      setMessage(error.message, true);
      return null;
    }
  }

  function hasDraftTicketData(data) {
    return [
      data.placa_cavalo,
      data.placa_tanque,
      data.motorista,
      data.fornecedor_cliente,
      data.transportadora,
      data.produto,
      data.especificacao_quimico,
      data.destino_procedencia,
      data.tara,
      data.num_agendamento,
      data.lacre,
      data.observacao,
    ].some(Boolean);
  }

  function updateActiveDraftFromForm() {
    if (!state.activeTicket) return null;
    const data = ticketFromForm();
    state.activeTicket = { ...state.activeTicket, ...data };
    els.quimicoField.classList.toggle("hidden", data.produto !== "QUIMICOS");
    return data;
  }

  function persistAfterFieldExit(control) {
    if (!control?.name || !state.activeTicket) return;

    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(() => {
      const data = updateActiveDraftFromForm();
      if (!data) return;
      if (!state.activeTicket?.id && !hasDraftTicketData(data)) return;
      persistActiveTicket();
    }, 160);
  }

  async function openTicket(id) {
    try {
      const ticket = await api(`/tickets/${id}`);
      showOperation(ticket);
    } catch (error) {
      setMessage(error.message, true);
      if (error.message !== "Operação cancelada.") {
        await showNotice("Não foi possível abrir o ticket", error.message);
      }
    }
  }

  function startNewTicket() {
    setMessage("", false);
    showOperation({ ...emptyTicket, pesagens: [] });
  }

  async function handleAddWeighing() {
    if (state.weighingInFlight) {
      return;
    }

    state.weighingInFlight = true;
    els.addWeighing.disabled = true;
    els.addWeighing.textContent = "Registrando...";
    let returnedToList = false;

    try {
      const draft = { ...(state.activeTicket || emptyTicket), ...ticketFromForm() };
      const errors = validateHeader(draft);
      if (errors.length) {
        const message = `Preencha os campos obrigatórios: ${errors.join(", ")}.`;
        setMessage(message, true);
        await showNotice("Dados obrigatórios", message);
        return;
      }

      if (isLocked(state.activeTicket) && !hasAdminConfirmation()) {
        await showNotice("Modo admin necessário", "Libere o modo admin para realizar ações em tickets encerrados.");
        return;
      }

      setMessage("Registrando leitura atual da balança...", false);
      clearTimeout(state.saveTimer);
      state.saveTimer = null;

      const ticket = await persistActiveTicket();
      if (!ticket?.id) return;
      const updated = await api(`/tickets/${ticket.id}/weighings`, {
        method: "POST",
        body: JSON.stringify({
          operador: currentOperatorNameForPayload(),
        }),
      });
      state.activeTicket = updated;
      fillForm(updated);
      renderOperation();
      setMessage(canCloseTicket(updated) ? "Pesagem registrada. O ticket pode ser visualizado ou encerrado." : "Pesagem registrada.", false);
      loadTickets();
      if (canCloseTicket(updated)) {
        const confirmed = await confirmOperation(
          "Encerrar ticket?",
          `Foram registradas ${updated.pesagens.length} pesagens. Deseja encerrar este ticket agora?`,
          {
            confirmText: "Encerrar ticket",
            cancelText: "Continuar aberto",
          }
        );

        if (confirmed) {
          const printWindow = reservePrintWindow();
          returnedToList = await closeActiveTicket({ askConfirmation: false, printWindow });
        }
      }
    } catch (error) {
      setMessage(error.message, true);
      await showNotice("Falha ao registrar pesagem", error.message);
    } finally {
      state.weighingInFlight = false;
      els.addWeighing.disabled = false;
      els.addWeighing.textContent = "Nova leitura";
      if (!returnedToList) {
        renderOperation();
      }
    }
  }

  async function closeActiveTicket({ askConfirmation = false, printWindow = null } = {}) {
    if (!canCloseTicket(state.activeTicket)) {
      await showNotice("Encerramento indisponivel", "O ticket so pode ser encerrado apos uma quantidade par de pesagens ou uma pesagem com tara informada.");
      return false;
    }

    if (askConfirmation) {
      const confirmed = await confirmOperation(
        "Encerrar ticket?",
        "Deseja encerrar este ticket?",
        {
          confirmText: "Encerrar ticket",
          cancelText: "Cancelar",
        }
      );
      if (!confirmed) return false;
    }

    printWindow = printWindow || reservePrintWindow();
    els.closeTicket.disabled = true;
    setMessage("Encerrando ticket...", false);
    let returnedToList = false;

    try {
      const updated = await api(`/tickets/${state.activeTicket.id}/close`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      state.activeTicket = updated;
      navigatePrintWindow(printWindow, updated.id);
      setMessage("Ticket encerrado. Abrindo ticket para impressão.", false);
      returnedToList = true;
      showList();
      return true;
    } catch (error) {
      closeReservedPrintWindow(printWindow);
      setMessage(error.message, true);
      await showNotice("Falha ao encerrar ticket", error.message);
      return false;
    } finally {
      els.closeTicket.disabled = false;
      if (!returnedToList) {
        renderOperation();
      }
    }
  }

  async function handleCloseTicket() {
    await closeActiveTicket({ askConfirmation: true });
  }

  async function handleDeleteWeighing(recordId) {
    if (!state.activeTicket?.id || !recordId) return;

    if (!hasAdminConfirmation()) {
      await showNotice("Modo admin necessario", "Libere o modo admin para excluir uma pesagem.");
      return;
    }

    const record = (state.activeTicket.pesagens || []).find((item) => Number(item.id) === Number(recordId));
    if (!record) return;

    const confirmed = await confirmOperation(
      "Excluir pesagem?",
      `Deseja excluir a pesagem ${record.sequencia}? Os pesos e a sequencia do ticket serao recalculados.`,
      {
        confirmText: "Excluir",
        danger: true,
      }
    );
    if (!confirmed) return;

    state.deletingWeighingId = Number(recordId);
    renderOperation();

    try {
      const updated = await api(`/tickets/${state.activeTicket.id}/weighings/${recordId}/delete`, {
        method: "POST",
      });
      state.activeTicket = updated;
      fillForm(updated);
      renderOperation();
      await loadTickets();
      showToast("Pesagem excluida com sucesso.", "success");
    } catch (error) {
      setMessage(error.message, true);
      await showNotice("Falha ao excluir pesagem", error.message);
    } finally {
      state.deletingWeighingId = null;
      renderOperation();
    }
  }

  function ticketPrintUrl(id, autoPrint = false) {
    const printParam = autoPrint ? "&print=1" : "";
    return `/frontend/ticket.html?id=${encodeURIComponent(id)}${printParam}`;
  }

  function openTicketPdf(id, autoPrint = false) {
    window.open(ticketPrintUrl(id, autoPrint), "_blank", "noopener");
  }

  function reservePrintWindow() {
    const printWindow = window.open("", "_blank");
    if (!printWindow) return null;

    printWindow.document.write(`
      <!doctype html>
      <html lang="pt-BR">
        <head><title>Abrindo ticket...</title></head>
        <body style="font-family: Arial, sans-serif; padding: 24px;">Abrindo ticket para impressão...</body>
      </html>
    `);
    printWindow.document.close();
    return printWindow;
  }

  function navigatePrintWindow(printWindow, id) {
    const url = ticketPrintUrl(id, true);
    if (printWindow && !printWindow.closed) {
      printWindow.location.href = url;
      return true;
    }

    return Boolean(window.open(url, "_blank", "noopener"));
  }

  function closeReservedPrintWindow(printWindow) {
    if (printWindow && !printWindow.closed) {
      printWindow.close();
    }
  }

  async function handleDelete(id) {
    const ticket = state.tickets.find((item) => Number(item.id) === Number(id));
    if (!ticket) return;

    const confirmed = await confirmOperation(
      "Excluir ticket?",
      `Deseja excluir o ticket ${shortTicketCode(ticket)}? Esta operação não poderá ser desfeita.`,
      {
        confirmText: "Excluir",
        danger: true,
      }
    );
    if (!confirmed) return;

    try {
      await api(`/tickets/${id}/delete`, {
        method: "POST",
      });
      await loadTickets();
      showToast("Ticket excluído com sucesso.", "success");
    } catch (error) {
      setMessage(error.message, true);
      if (error.message !== "Operação cancelada.") {
        await showNotice("Falha ao excluir ticket", error.message);
      }
    }
  }

  function openAdminModal() {
    if (hasAdminConfirmation()) {
      state.adminUnlocked = false;
      state.adminPassword = "";
      updateAdminState();
      showToast("Modo admin bloqueado.", "success");
      return;
    }

    els.adminModal.classList.remove("hidden");
    els.adminPassword.value = "";
    els.adminPassword.focus();
  }

  function resolveAdminModal(accepted) {
    if (!accepted) {
      els.adminModal.classList.add("hidden");
      return;
    }

    const password = els.adminPassword.value;
    if (password !== ADMIN_PASSWORD) {
      showToast("Senha admin inválida.", "error");
      els.adminPassword.select();
      return;
    }

    state.adminUnlocked = true;
    state.adminPassword = password;
    els.adminModal.classList.add("hidden");
    updateAdminState();
    showToast("Modo admin liberado.", "success");
  }

  function bindEvents() {
    bindUppercaseInputs();
    els.adminLock.addEventListener("click", openAdminModal);
    els.startTicket.addEventListener("click", startNewTicket);
    els.backToList.addEventListener("click", showList);
    els.openPdf.addEventListener("click", async () => {
      if (!state.activeTicket?.id) {
        await showNotice("Ticket ainda não salvo", "Digite e aguarde o ticket ser salvo antes de visualizar.");
        return;
      }
      if (!(state.activeTicket.pesagens || []).length) {
        await showNotice("Ticket sem pesagem", "Registre ao menos uma pesagem antes de visualizar o ticket.");
        return;
      }
      openTicketPdf(state.activeTicket.id);
    });
    els.addWeighing.addEventListener("click", handleAddWeighing);
    els.closeTicket.addEventListener("click", handleCloseTicket);
    els.weighingTimeline.addEventListener("click", (event) => {
      const button = event.target.closest("[data-delete-weighing]");
      if (!button) return;
      handleDeleteWeighing(button.dataset.deleteWeighing);
    });

    els.ticketSearch.addEventListener("keydown", () => {
      state.searchTouched = true;
    });
    els.ticketSearch.addEventListener("paste", () => {
      state.searchTouched = true;
    });
    els.ticketSearch.addEventListener("input", (event) => {
      if (!state.searchTouched && document.activeElement !== els.ticketSearch) {
        event.target.value = "";
        state.search = "";
        loadTickets();
        return;
      }

      state.searchTouched = true;
      state.search = event.target.value.trim();
      debouncedLoadTickets();
    });
    els.ticketDate.addEventListener("input", (event) => {
      event.target.value = maskPtBrDate(event.target.value);
      const isoDate = ptBrToIsoDate(event.target.value);
      if (isoDate) {
        state.date = isoDate;
        debouncedLoadTickets();
      }
    });
    els.ticketDate.addEventListener("blur", (event) => {
      const isoDate = ptBrToIsoDate(event.target.value);
      state.date = isoDate || todayGmt3();
      event.target.value = isoToPtBrDate(state.date);
      loadTickets();
    });
    els.statusFilter.addEventListener("change", (event) => {
      state.status = event.target.value;
      loadTickets();
    });

    els.ticketForm.addEventListener("click", (event) => {
      const button = event.target.closest("[data-lacre-action]");
      if (!button) return;

      const action = button.dataset.lacreAction;
      if (action === "add") {
        const input = addLacreInput("");
        input.focus();
        return;
      }

      if (action === "remove") {
        const rows = [...els.lacresList.querySelectorAll(".lacre-row")];
        const row = button.closest(".lacre-row");
        if (rows.length <= 1) {
          const input = row?.querySelector("input");
          if (input) input.value = "";
        } else {
          row?.remove();
        }
        updateLacreRemoveState();
        updateActiveDraftFromForm();
        persistAfterFieldExit({ name: "lacre" });
      }
    });

    els.ticketForm.addEventListener("input", (event) => {
      if (!event.target.name) return;
      uppercaseInput(event.target);
      if (event.target.name === "lacre_item") {
        updateLacreRemoveState();
      }
      updateActiveDraftFromForm();
      if (event.target.name === "produto") {
        els.quimicoField.classList.toggle("hidden", event.target.value !== "QUIMICOS");
      }
    });
    els.ticketForm.addEventListener("change", (event) => {
      if (!event.target.name) return;
      uppercaseInput(event.target);
      updateActiveDraftFromForm();
      if (event.target.name === "produto") {
        els.quimicoField.classList.toggle("hidden", event.target.value !== "QUIMICOS");
      }
    });
    els.ticketForm.addEventListener("focusout", (event) => {
      persistAfterFieldExit(event.target);
    });

    els.ticketsBody.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button) return;
      if (button.disabled) return;

      const id = button.dataset.id;
      const action = button.dataset.action;
      if (action === "view") openTicketPdf(id);
      if (action === "edit") {
        openTicket(id);
      }
      if (action === "delete") handleDelete(id);
    });

    els.adminConfirm.addEventListener("click", () => resolveAdminModal(true));
    els.adminCancel.addEventListener("click", () => resolveAdminModal(false));
    els.adminPassword.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        resolveAdminModal(true);
      }
    });
    els.appModalConfirm.addEventListener("click", () => resolveAppModal(true));
    els.appModalCancel.addEventListener("click", () => resolveAppModal(false));
    els.appModal.addEventListener("click", (event) => {
      if (event.target === els.appModal) {
        resolveAppModal(false);
      }
    });
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !els.appModal.classList.contains("hidden")) {
        resolveAppModal(false);
      }
    });
    window.addEventListener("pageshow", blockSearchAutofill);
  }

  bindEvents();
  state.date = todayGmt3();
  state.search = "";
  els.ticketSearch.value = "";
  blockSearchAutofill();
  els.ticketDate.value = isoToPtBrDate(state.date);
  loadCurrentOperator();
  loadCatalogs();
  loadTickets();
})();
