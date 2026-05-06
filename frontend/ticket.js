(function () {
  const PRODUCT_LABELS = {
    GLP: "GLP",
    QUIMICOS: "QUÍMICOS",
    BORRA: "BORRA",
  };

  const params = new URLSearchParams(window.location.search);
  const ticketId = params.get("id");
  const shouldAutoPrint = params.get("print") === "1";

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

  function productLabel(ticket) {
    const label = PRODUCT_LABELS[ticket.produto] || ticket.produto || "--";
    if (ticket.produto === "QUIMICOS" && ticket.especificacao_quimico) {
      return `${label} (${ticket.especificacao_quimico.toUpperCase()})`;
    }
    return label;
  }

  function shouldShowLiquidWeight(ticket) {
    return (ticket.pesagens || []).length > 0 && ticket.pesagens.length % 2 === 0 && ticket.peso_liquido !== null;
  }

  function ticketTitle(ticket) {
    const weighingCount = (ticket.pesagens || []).length;
    const status = weighingCount % 2 === 1 ? "PESAGEM PARCIAL" : "PESAGEM COMPLETA";
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

    if (!ticket.pesagens?.length) {
      container.innerHTML = '<article class="weighing-block"><h2>Pesagens</h2><div class="weighing-box">Nenhuma pesagem registrada.</div></article>';
      return;
    }

    ticket.pesagens.forEach((record) => {
      const card = document.createElement("article");
      card.className = "weighing-block";
      card.innerHTML = `
        <h2>${weighingTitle(record)}</h2>
        <dl class="weighing-box">
          <div><dt>Data/hora:</dt><dd>${formatDate(record.data_hora)}</dd></div>
          <div><dt>Balança:</dt><dd>${scaleLabel(record.balanca)}</dd></div>
          <div><dt>Peso:</dt><dd>${formatKg(record.peso)}</dd></div>
          <div><dt>Operador:</dt><dd>${record.operador || "Balança"}</dd></div>
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
      text("destino", ticket.destino_procedencia);
      const netWeight = document.getElementById("net-weight");
      netWeight.style.display = shouldShowLiquidWeight(ticket) ? "grid" : "none";
      text("peso-liquido", formatKg(ticket.peso_liquido));
      renderWeighings(ticket);
      if (shouldAutoPrint) {
        setTimeout(() => window.print(), 350);
      }
    } catch (error) {
      document.body.innerHTML = error.message;
    }
  }

  document.getElementById("print").addEventListener("click", () => window.print());
  init();
})();
