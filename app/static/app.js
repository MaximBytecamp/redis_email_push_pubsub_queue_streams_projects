const state = {
  mailings: [],
  recipients: [],
  selectedMailingId: null,
  mode: "manual",
};

const qs = (selector) => document.querySelector(selector);

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function statusBadge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

function setResult(id, message, isError = false) {
  const node = qs(id);
  node.textContent = message;
  node.style.color = isError ? "var(--rose)" : "var(--muted)";
}

async function refreshHealth() {
  try {
    const health = await api("/health");
    qs("#healthStatus").textContent = `Redis: ${health.redis}`;
  } catch (error) {
    qs("#healthStatus").textContent = "API недоступен";
  }
}

async function refreshRecipients() {
  state.recipients = await api("/recipients");
  qs("#recipientCount").textContent = state.recipients.length;
  qs("#recipientsTable").innerHTML = state.recipients
    .map(
      (recipient) => `
        <tr>
          <td>${recipient.id}</td>
          <td>${recipient.name || ""}</td>
          <td>${recipient.email}</td>
          <td>${recipient.group || ""}</td>
        </tr>
      `,
    )
    .join("");
}

async function refreshMailings() {
  state.mailings = await api("/mailings");
  qs("#mailingCount").textContent = state.mailings.length;
  qs("#sentCount").textContent = state.mailings.reduce((sum, item) => sum + item.sent_count, 0);
  qs("#failedCount").textContent = state.mailings.reduce((sum, item) => sum + item.failed_count, 0);

  qs("#mailingsList").innerHTML = state.mailings
    .map((mailing) => {
      const pending = Math.max(mailing.total_recipients - mailing.sent_count - mailing.failed_count, 0);
      const total = Math.max(mailing.total_recipients, 1);
      return `
        <article class="mailing-card">
          <div class="mailing-head">
            <div>
              <h3>${mailing.title}</h3>
              <p>${mailing.subject}</p>
            </div>
            ${statusBadge(mailing.status)}
          </div>
          <div class="progress" style="--sent:${mailing.sent_count / total}fr; --failed:${mailing.failed_count / total}fr; --pending:${pending / total}fr">
            <span></span><span></span><span></span>
          </div>
          <div class="mailing-actions">
            <span class="hint">Всего: ${mailing.total_recipients}, sent: ${mailing.sent_count}, failed: ${mailing.failed_count}</span>
            <div>
              <button type="button" class="secondary" onclick="selectMailing(${mailing.id})">Письма</button>
              <button type="button" class="secondary" onclick="retryFailed(${mailing.id})">Retry failed</button>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

async function refreshEmails() {
  if (!state.selectedMailingId) return;
  const emails = await api(`/mailings/${state.selectedMailingId}/emails`);
  qs("#selectedMailingLabel").textContent = `Рассылка #${state.selectedMailingId}`;
  qs("#emailsTable").innerHTML = emails
    .map(
      (email) => `
        <tr>
          <td>${email.id}</td>
          <td>${email.recipient}</td>
          <td>${statusBadge(email.status)}</td>
          <td>${email.error || ""}</td>
        </tr>
      `,
    )
    .join("");
}

async function refreshEvents() {
  const events = await api("/events?limit=80");
  qs("#eventsList").innerHTML = events
    .map(
      (event) => `
        <article class="event">
          <strong>${event.event}</strong>
          <p>${new Date(event.created_at || Date.now()).toLocaleString()} | ${JSON.stringify(event.data)}</p>
        </article>
      `,
    )
    .join("");
}

async function refreshAll() {
  await Promise.all([refreshHealth(), refreshRecipients(), refreshMailings(), refreshEvents()]);
  await refreshEmails();
}

async function selectMailing(id) {
  state.selectedMailingId = id;
  await refreshEmails();
}

async function retryFailed(id) {
  await api(`/mailings/${id}/retry-failed`, { method: "POST" });
  state.selectedMailingId = id;
  await refreshAll();
}

function setupForms() {
  qs("#importForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.target);
    try {
      const result = await api("/imports", { method: "POST", body: formData });
      setResult("#importResult", `Импорт #${result.import_id}: ${result.message}`);
      event.target.reset();
      await refreshEvents();
    } catch (error) {
      setResult("#importResult", error.message, true);
    }
  });

  qs("#mailingForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const payload = {
      title: form.get("title"),
      subject: form.get("subject"),
      body: form.get("body"),
    };
    if (state.mode === "manual") {
      payload.recipients = String(form.get("recipients") || "")
        .split(/[,\n;]/)
        .map((email) => email.trim())
        .filter(Boolean);
    } else {
      payload.group = String(form.get("group") || "").trim();
    }

    try {
      const result = await api("/mailings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setResult("#mailingResult", `Рассылка #${result.mailing_id}: ${result.total_recipients} писем в очереди`);
      event.target.reset();
      state.selectedMailingId = result.mailing_id;
      await refreshAll();
    } catch (error) {
      setResult("#mailingResult", error.message, true);
    }
  });

  document.querySelectorAll(".segmented button").forEach((button) => {
    button.addEventListener("click", () => {
      state.mode = button.dataset.mode;
      document.querySelectorAll(".segmented button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      qs("#manualRecipients").classList.toggle("hidden", state.mode !== "manual");
      qs("#groupRecipients").classList.toggle("hidden", state.mode !== "group");
    });
  });

  qs("#refreshButton").addEventListener("click", refreshAll);
}

function setupNotifications() {
  const source = new EventSource("/notifications/stream");
  source.onmessage = async (event) => {
    const payload = JSON.parse(event.data);
    const node = document.createElement("article");
    node.className = "notification";
    node.innerHTML = `<strong>${payload.event}</strong><p>${payload.message || JSON.stringify(payload)}</p>`;
    qs("#notifications").prepend(node);
    while (qs("#notifications").children.length > 12) {
      qs("#notifications").lastElementChild.remove();
    }
    await refreshAll();
  };
}

setupForms();
setupNotifications();
refreshAll();
setInterval(refreshAll, 10000);
