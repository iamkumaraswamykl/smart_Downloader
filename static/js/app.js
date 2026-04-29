const state = {
  categories: [],
  actions: [],
  pickerTarget: null,
  pickerParent: "",
};

const els = {
  watchPath: document.querySelector("#watchPath"),
  destinationRoot: document.querySelector("#destinationRoot"),
  processExisting: document.querySelector("#processExisting"),
  startBtn: document.querySelector("#startBtn"),
  stopBtn: document.querySelector("#stopBtn"),
  refreshBtn: document.querySelector("#refreshBtn"),
  refreshLogsBtn: document.querySelector("#refreshLogsBtn"),
  statusPill: document.querySelector("#statusPill"),
  metricStatus: document.querySelector("#metricStatus"),
  metricQueue: document.querySelector("#metricQueue"),
  metricCategory: document.querySelector("#metricCategory"),
  metricProcessed: document.querySelector("#metricProcessed"),
  llmProvider: document.querySelector("#llmProvider"),
  recentList: document.querySelector("#recentList"),
  categoryList: document.querySelector("#categoryList"),
  historyRows: document.querySelector("#historyRows"),
  logOutput: document.querySelector("#logOutput"),
  toast: document.querySelector("#toast"),
  folderDialog: document.querySelector("#folderDialog"),
  closePickerBtn: document.querySelector("#closePickerBtn"),
  pickerPath: document.querySelector("#pickerPath"),
  folderList: document.querySelector("#folderList"),
  rootChips: document.querySelector("#rootChips"),
  upBtn: document.querySelector("#upBtn"),
  goBtn: document.querySelector("#goBtn"),
  chooseBtn: document.querySelector("#chooseBtn"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("visible");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => els.toast.classList.remove("visible"), 3600);
}

async function loadStatus() {
  const status = await api("/api/status");
  renderStatus(status);
  if (!els.watchPath.value && status.default_downloads) {
    els.watchPath.value = status.default_downloads;
  }
}

function renderStatus(status) {
  els.statusPill.textContent = status.running ? "Running" : "Idle";
  els.statusPill.className = `status-pill ${status.running ? "running" : "idle"}`;
  els.metricStatus.textContent = status.running ? "Monitoring" : "Idle";
  els.metricQueue.textContent = status.queued || 0;
  els.llmProvider.textContent = status.llm_provider || "local-semantic";
  if (status.watch_path) {
    els.watchPath.value = status.watch_path;
  }
  if (status.destination_root) {
    els.destinationRoot.value = status.destination_root;
  }
}

async function loadCategories() {
  state.categories = await api("/api/categories");
  els.categoryList.innerHTML = state.categories
    .map(
      (category) => `
      <div class="category-item">
        <strong>${escapeHtml(category.name)}</strong>
        <span>${escapeHtml(category.description || "")}</span>
      </div>
    `
    )
    .join("");
}

async function loadActions() {
  state.actions = await api("/api/actions?limit=120");
  renderActions();
}

function renderActions() {
  const processed = state.actions.filter((item) => item.status !== "error");
  els.metricProcessed.textContent = String(processed.length);
  els.metricCategory.textContent = processed[0]?.category || "None";

  const recent = state.actions.slice(0, 8);
  els.recentList.innerHTML = recent.length
    ? recent.map(renderActivityItem).join("")
    : `<div class="activity-item"><span class="meta-line">No files processed yet.</span></div>`;

  els.historyRows.innerHTML = state.actions.length
    ? state.actions.map(renderHistoryRow).join("")
    : `<tr><td colspan="6">No history yet.</td></tr>`;

  bindHistoryActions();
}

function renderActivityItem(item) {
  return `
    <article class="activity-item">
      <div class="activity-top">
        <div class="file-name">${escapeHtml(item.file_name)}</div>
        <span class="category-badge">${escapeHtml(item.category)}</span>
      </div>
      <div class="meta-line">${escapeHtml(item.status)} | ${escapeHtml(item.method || "")} | ${formatConfidence(item.confidence)}</div>
      <p class="preview">${escapeHtml(item.extracted_preview || item.error || item.current_path || "")}</p>
    </article>
  `;
}

function renderHistoryRow(item) {
  const options = state.categories
    .map((category) => {
      const selected = category.name === item.category ? "selected" : "";
      return `<option ${selected} value="${escapeAttr(category.name)}">${escapeHtml(category.name)}</option>`;
    })
    .join("");

  const canUndo = item.status === "moved" || item.status === "reclassified";
  return `
    <tr>
      <td>
        <strong class="file-name">${escapeHtml(item.file_name)}</strong>
        <div class="meta-line">${escapeHtml(item.current_path || item.original_path || "")}</div>
      </td>
      <td><select class="inline-select" data-reclassify="${item.id}">${options}</select></td>
      <td>${formatConfidence(item.confidence)}</td>
      <td>${escapeHtml(item.status)}</td>
      <td>${escapeHtml(item.created_at || "")}</td>
      <td>
        <div class="table-actions">
          <button class="ghost" data-apply="${item.id}">Apply</button>
          <button class="danger" data-undo="${item.id}" ${canUndo ? "" : "disabled"}>Undo</button>
        </div>
      </td>
    </tr>
  `;
}

function bindHistoryActions() {
  document.querySelectorAll("[data-undo]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api(`/api/actions/${button.dataset.undo}/undo`, { method: "POST" });
        toast("Movement undone.");
        await loadActions();
      } catch (error) {
        toast(error.message);
      }
    });
  });

  document.querySelectorAll("[data-apply]").forEach((button) => {
    button.addEventListener("click", async () => {
      const select = document.querySelector(`[data-reclassify="${button.dataset.apply}"]`);
      try {
        await api(`/api/actions/${button.dataset.apply}/reclassify`, {
          method: "POST",
          body: JSON.stringify({ category: select.value }),
        });
        toast("Category updated.");
        await loadActions();
      } catch (error) {
        toast(error.message);
      }
    });
  });
}

async function loadLogs() {
  const data = await api("/api/logs?lines=180");
  els.logOutput.textContent = data.lines.join("");
}

async function startMonitoring() {
  try {
    const status = await api("/api/start", {
      method: "POST",
      body: JSON.stringify({
        watch_path: els.watchPath.value,
        destination_root: els.destinationRoot.value,
        process_existing: els.processExisting.checked,
      }),
    });
    renderStatus(status);
    toast(status.queued_existing ? `Started. Queued ${status.queued_existing} files.` : "Monitoring started.");
  } catch (error) {
    toast(error.message);
  }
}

async function stopMonitoring() {
  try {
    const status = await api("/api/stop", { method: "POST" });
    renderStatus(status);
    toast("Monitoring stopped.");
  } catch (error) {
    toast(error.message);
  }
}

async function openPicker(targetId) {
  state.pickerTarget = targetId;
  const current = document.querySelector(`#${targetId}`).value || els.watchPath.value;
  await browse(current);
  els.folderDialog.showModal();
}

async function browse(path) {
  const data = await api(`/api/browse?path=${encodeURIComponent(path || "")}`);
  state.pickerParent = data.parent || "";
  els.pickerPath.value = data.path;
  els.rootChips.innerHTML = data.roots
    .map((root) => `<button data-root="${escapeAttr(root.path)}">${escapeHtml(root.name)}</button>`)
    .join("");
  els.folderList.innerHTML = data.directories.length
    ? data.directories
        .map((dir) => `<button class="folder-item" data-folder="${escapeAttr(dir.path)}">${escapeHtml(dir.name)}</button>`)
        .join("")
    : `<div class="folder-item"><span class="meta-line">No child folders available.</span></div>`;

  document.querySelectorAll("[data-folder]").forEach((button) => {
    button.addEventListener("click", () => browse(button.dataset.folder));
  });
  document.querySelectorAll("[data-root]").forEach((button) => {
    button.addEventListener("click", () => browse(button.dataset.root));
  });
}

function bindNavigation() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", async () => {
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("active-view"));
      document.querySelector(`#${button.dataset.view}View`).classList.add("active-view");
      if (button.dataset.view === "logs") {
        await loadLogs();
      }
    });
  });
}

function formatConfidence(value) {
  const numeric = Number(value || 0);
  return `${Math.round(numeric * 100)}%`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

function bindEvents() {
  els.startBtn.addEventListener("click", startMonitoring);
  els.stopBtn.addEventListener("click", stopMonitoring);
  els.refreshBtn.addEventListener("click", loadActions);
  els.refreshLogsBtn.addEventListener("click", loadLogs);
  els.closePickerBtn.addEventListener("click", () => els.folderDialog.close());
  els.upBtn.addEventListener("click", () => state.pickerParent && browse(state.pickerParent));
  els.goBtn.addEventListener("click", () => browse(els.pickerPath.value));
  els.chooseBtn.addEventListener("click", () => {
    if (state.pickerTarget) {
      document.querySelector(`#${state.pickerTarget}`).value = els.pickerPath.value;
    }
    els.folderDialog.close();
  });

  document.querySelectorAll("[data-picker-target]").forEach((button) => {
    button.addEventListener("click", () => openPicker(button.dataset.pickerTarget));
  });
}

async function boot() {
  bindEvents();
  bindNavigation();
  await Promise.all([loadStatus(), loadCategories(), loadActions()]);
  window.setInterval(async () => {
    try {
      await Promise.all([loadStatus(), loadActions()]);
    } catch (error) {
      console.warn(error);
    }
  }, 5000);
}

boot().catch((error) => toast(error.message));

