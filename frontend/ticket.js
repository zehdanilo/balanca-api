(function () {
  const PRODUCT_LABELS = {
    GLP: "GLP",
    QUIMICOS: "QUÍMICOS",
    BORRA: "BORRA",
  };

  const params = new URLSearchParams(window.location.search);
  const ticketId = params.get("id");
  const shouldAutoPrint = params.get("print") === "1";
  const printButton = document.getElementById("print");
  let ticketReadyToPrint = false;

  function setPrintReady(ready) {
    ticketReadyToPrint = ready;
    printButton.disabled = !ready;
    printButton.textContent = ready ? "Imprimir / salvar PDF" : "Carregando ticket...";
  }

  async function api(path) {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.error?.message || `Falha na API (${response.status}).`);
    }
    return payload.data;
  }

  function text(id, value) {
    document.getElementById(id).textContent = value || "--";
  }

  function optionalText(id, value) {
    const element = document.getElementById(id);
    const normalized = String(value || "").trim();
    element.closest(".field").classList.toggle("hidden", !normalized);
    element.textContent = normalized;
  }

  function formatKg(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "-- kg";
    }
    return `${Number(value).toLocaleString("pt-BR")} kg`;
  }

  function formatDate(value) {
    if (!value) return "--";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "--";
    const pad2 = (part) => String(part).padStart(2, "0");
    return `${pad2(date.getDate())}/${pad2(date.getMonth() + 1)}/${date.getFullYear()} ${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`;
  }

  function scaleLabel(value) {
    const normalized = String(value || "").trim();
    if (!normalized || normalized === "Balança 020" || normalized === "Balanca 020") {
      return "Balança 002";
    }
    return normalized;
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

  function productLabel(ticket) {
    const label = PRODUCT_LABELS[ticket.produto] || ticket.produto || "--";
    if (ticket.produto === "QUIMICOS" && ticket.especificacao_quimico) {
      return `${label} (${ticket.especificacao_quimico.toUpperCase()})`;
    }
    return label;
  }

  function shouldShowLiquidWeight(ticket) {
    const pesagens = orderedWeighings(ticket.pesagens);
    const hasTara = Number(ticket?.tara || 0) > 0;
    return pesagens.length > 0 && (pesagens.length % 2 === 0 || (pesagens.length === 1 && hasTara)) && liquidWeight(ticket) !== null;
  }

  function liquidWeight(ticket) {
    if (ticket.peso_liquido !== null && ticket.peso_liquido !== undefined) {
      return ticket.peso_liquido;
    }

    const pesagens = orderedWeighings(ticket.pesagens);
    const tara = Number(ticket?.tara || 0);
    if (pesagens.length === 1 && tara > 0) {
      return Math.max(Number(pesagens[0].peso || 0) - tara, 0);
    }

    if (pesagens.length >= 2 && pesagens.length % 2 === 0) {
      let total = 0;
      for (let index = 0; index < pesagens.length; index += 2) {
        total += Math.abs(Number(pesagens[index].peso || 0) - Number(pesagens[index + 1].peso || 0));
      }
      return Math.max(total - tara, 0);
    }

    return null;
  }

  function ticketTitle(ticket) {
    const weighingCount = orderedWeighings(ticket.pesagens).length;
    const hasTara = Number(ticket?.tara || 0) > 0;
    const status = weighingCount % 2 === 1 && !(weighingCount === 1 && hasTara) ? "PESAGEM PARCIAL" : "PESAGEM COMPLETA";
    return `TICKET DE BALANÇA - ${status}`;
  }

  function statusLabel(status) {
    return {
      ABERTO: "ABERTO",
      EM_ANDAMENTO: "OK",
      COMPLETO: "OK",
    }[status] || status || "--";
  }

  function shortTicketCode(ticket) {
    if (ticket?.id) {
      return `T-${String(ticket.id).padStart(5, "0")}`;
    }
    return ticket?.ticket_code || "--";
  }

  function weighingTitle(record) {
    const names = ["Primeira", "Segunda", "Terceira", "Quarta", "Quinta", "Sexta", "Sétima", "Oitava"];
    const prefix = names[record.sequencia - 1] || `${record.sequencia}ª`;
    const type = record.tipo === "SAIDA" ? "Saída" : "Chegada";
    return `${prefix} Pesagem (${type})`;
  }

  function renderWeighings(ticket) {
    const container = document.getElementById("weighings");
    container.innerHTML = "";

    const pesagens = orderedWeighings(ticket.pesagens);

    if (!pesagens.length) {
      container.innerHTML = '<article class="weighing-block"><h2>Pesagens</h2><div class="weighing-box">Nenhuma pesagem registrada.</div></article>';
      return;
    }

    pesagens.forEach((record) => {
      const card = document.createElement("article");
      card.className = "weighing-block";
      card.innerHTML = `
        <h2>${weighingTitle(record)}</h2>
        <dl class="weighing-box">
          <div><dt>Data/hora:</dt><dd>${formatDate(record.data_hora)}</dd></div>
          <div><dt>Balança:</dt><dd>${scaleLabel(record.balanca)}</dd></div>
          <div><dt>Peso:</dt><dd>${formatKg(record.peso)}</dd></div>
          <div><dt>Operador:</dt><dd>${operatorLabel(record.operador)}</dd></div>
        </dl>
      `;
      container.appendChild(card);
    });
  }

  async function init() {
    if (!ticketId) {
      document.body.innerHTML = "Ticket não informado.";
      return;
    }

    try {
      const ticket = await api(`/tickets/${encodeURIComponent(ticketId)}`);
      document.title = `Ticket ${shortTicketCode(ticket)}`;
      text("ticket-title", ticketTitle(ticket));
      text("ticket-code", shortTicketCode(ticket));
      text("ticket-status", statusLabel(ticket.status));
      text("ticket-operation", "Pesagem");
      text("placa-cavalo", ticket.placa_cavalo);
      text("placa-tanque", ticket.placa_tanque);
      text("motorista", ticket.motorista);
      text("fornecedor", ticket.fornecedor_cliente);
      text("transportadora", ticket.transportadora);
      text("produto", productLabel(ticket));
      const tara = Number(ticket.tara || 0);
      const taraField = document.getElementById("tara").closest(".field");
      document.querySelector(".field-grid").classList.toggle("has-tara", tara > 0);
      taraField.classList.toggle("hidden", tara <= 0);
      document.getElementById("tara").textContent = tara > 0 ? formatKg(tara) : "";
      text("destino", ticket.destino_procedencia);
      optionalText("num-agendamento", ticket.num_agendamento);
      optionalText("lacre", ticket.lacre);
      const observacao = String(ticket.observacao || "").trim();
      document.getElementById("observacao").closest(".field").classList.toggle("hidden", !observacao);
      text("observacao", observacao);
      const netWeight = document.getElementById("net-weight");
      netWeight.style.display = shouldShowLiquidWeight(ticket) ? "grid" : "none";
      text("peso-liquido", formatKg(liquidWeight(ticket)));
      renderWeighings(ticket);
      setPrintReady(true);
      if (shouldAutoPrint) {
        setTimeout(() => window.print(), 350);
      }
    } catch (error) {
      setPrintReady(false);
      document.body.innerHTML = error.message;
    }
  }

  printButton.addEventListener("click", () => {
    if (!ticketReadyToPrint) return;
    window.print();
  });
  setPrintReady(false);
  init();
})();
