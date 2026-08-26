/* REvoCompute — Configuration page logic */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;

  // -- DOM refs ----------------------------------------------------------

  var taskTypeCards = document.getElementById("taskTypeCards");
  var taskTypeStatus = document.getElementById("taskTypeStatus");
  var resourceBody = document.getElementById("resourceBody");
  var resourceSaveStatus = document.getElementById("resourceSaveStatus");
  var saveResourcesBtn = document.getElementById("saveResourcesBtn");
  var logoutBtn = document.getElementById("logoutBtn");
  var toastWrap = document.getElementById("toastWrap");

  if (logoutBtn) {
    logoutBtn.addEventListener("click", A.logout);
  }

  // -- State -------------------------------------------------------------

  var taskTypeConfigs = [];     // from admin config API, including effective_resources
  var resources = {};           // {key: value}
  var taskTypes = [];           // from /api/types (metadata: display_name, params, etc.)
  var slurmEnabled = false;     // global SLURM feature flag
  var slurmAllowedQueues = [];  // whitelisted partitions

  var SLURM_FIELDS = [
    { key: "slurm_partition",     label: "Partition",     type: "text",    placeholder: "e.g. gpu" },
    { key: "slurm_gres",          label: "GRES",          type: "text",    placeholder: "e.g. gpu:A100:1" },
    { key: "slurm_nodes",         label: "Nodes",         type: "number",  placeholder: "e.g. 1" },
    { key: "slurm_ntasks",        label: "NTasks",        type: "number",  placeholder: "e.g. 1" },
    { key: "slurm_qos",           label: "QOS",           type: "text",    placeholder: "e.g. normal" },
    { key: "slurm_account",       label: "Account",       type: "text",    placeholder: "e.g. lab-abc" },
    { key: "slurm_constraint",    label: "Constraint",    type: "text",    placeholder: "e.g. avx512" },
    { key: "slurm_exclusive",     label: "Exclusive",     type: "toggle",  placeholder: "" },
  ];

  function parseRuntime(raw) {
    if (raw == null || String(raw).trim() === "") return null;
    var s = String(raw).trim();
    // HH:MM:SS or H:MM:SS
    var parts = s.split(":");
    if (parts.length === 3) {
      var h = parseInt(parts[0], 10), m = parseInt(parts[1], 10), sec = parseInt(parts[2], 10);
      if (!isNaN(h) && !isNaN(m) && !isNaN(sec)) return h * 3600 + m * 60 + sec;
    }
    var n = Number(s);
    return isNaN(n) ? null : Math.round(n);
  }

  function formatRuntime(seconds) {
    if (seconds == null || seconds === "") return "";
    var s = Number(seconds);
    if (isNaN(s)) return String(seconds);
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return h + ":" + (m < 10 ? "0" : "") + m + ":" + (sec < 10 ? "0" : "") + sec;
  }

  var RESOURCE_FIELDS = [
    { key: "cpus",                 label: "CPU cores",   type: "number", placeholder: "e.g. 8" },
    { key: "memory",               label: "Memory",      type: "text",   placeholder: "e.g. 16G" },
    { key: "max_runtime_seconds",  label: "Max runtime", type: "text",   placeholder: "1:00:00 or 3600" },
  ];

  // -- Sub-tab navigation ------------------------------------------------

  document.querySelectorAll("#configTabs .sub-tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      document.querySelectorAll("#configTabs .sub-tab").forEach(function (t) { t.classList.remove("active"); });
      tab.classList.add("active");
      var tabId = "tab-" + tab.dataset.tab;
      document.querySelectorAll(".config-panel").forEach(function (p) { p.style.display = "none"; });
      var panel = document.getElementById(tabId);
      if (panel) panel.style.display = "";
    });
  });

  // -- Toast -------------------------------------------------------------

  function toast(message, type) {
    type = type || "info";
    var node = document.createElement("div");
    node.className = "toast " + type;
    node.textContent = message;
    toastWrap.appendChild(node);
    setTimeout(function () { node.remove(); }, 3000);
  }

  // -- API ---------------------------------------------------------------

  async function loadConfig() {
    try {
      var resp = await A.authFetch("/compute/api/auth/admin/config");
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      var data = await resp.json();
      taskTypeConfigs = data.task_types || [];
      resources = data.resources || {};
      slurmEnabled = (data.slurm && data.slurm.enabled) || false;
      slurmAllowedQueues = (data.slurm && data.slurm.allowed_queues) || [];
      if (data.ignored_resource_keys && data.ignored_resource_keys.length) {
        toast("Ignored obsolete resource keys: " + data.ignored_resource_keys.join(", "), "info");
      }
    } catch (e) {
      toast("Failed to load configuration: " + e.message, "error");
      taskTypeConfigs = [];
      resources = {};
      slurmEnabled = false;
      slurmAllowedQueues = [];
    }
  }

  async function loadTaskTypes() {
    try {
      var resp = await fetch("/compute/api/types");
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      taskTypes = (await resp.json()).task_types || [];
    } catch (e) {
      taskTypes = [];
    }
  }

  async function saveStructured(body) {
    try {
      var resp = await A.authFetch("/compute/api/auth/admin/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        var err = await resp.json().catch(function () { return {}; });
        throw new Error(err.error || "HTTP " + resp.status);
      }
      await loadConfig();
      return true;
    } catch (e) {
      toast("Save failed: " + e.message, "error");
      return false;
    }
  }

  // -- Task Type cards (driven from taskTypeConfigs, NOT /api/types) -----

  function findTypeMeta(tool) {
    return taskTypes.find(function (t) { return t.name === tool; });
  }

  function renderTaskTypeCards() {
    // Drive from taskTypeConfigs so disabled task types remain visible
    if (!taskTypeConfigs.length) {
      taskTypeCards.innerHTML = '<div class="empty">No task type configuration loaded.</div>';
      taskTypeStatus.textContent = "";
      return;
    }

    var taskConfigs = taskTypeConfigs.filter(function (c) { return !c.is_workflow_stage; });
    var enabledCount = taskConfigs.filter(function (c) { return c.enabled !== false; }).length;
    taskTypeStatus.textContent = taskConfigs.length + " type(s) · " + enabledCount + " enabled";

    taskTypeCards.innerHTML = taskConfigs.map(function (config) {
      var meta = findTypeMeta(config.tool);
      var displayName = meta ? meta.display_name : (config.display_name || config.tool);
      var ext = meta ? meta.input_extension : "";
      var inputLabel = meta ? meta.input_label : "";
      var stageCount = meta ? Object.keys(meta.stage_markers).length : 0;
      var paramCount = meta ? meta.params.length : 0;
      var enabled = config.enabled !== false;

      var stages = taskTypeConfigs.filter(function (stage) {
        return stage.is_workflow_stage && stage.tool.indexOf(config.tool + ".") === 0;
      });
      var submodules = stages.map(function (stage) {
        var stageLabel = stage.display_name.indexOf(displayName + " / ") === 0
          ? stage.display_name.slice(displayName.length + 3)
          : stage.display_name;
        return buildCard(
          stage.tool,
          stageLabel,
          "",
          "",
          0,
          0,
          stage.enabled !== false,
          stage
        );
      }).join("");

      return buildCard(config.tool, displayName, ext, inputLabel, stageCount, paramCount, enabled, config) +
        (submodules ? '<div class="workflow-submodules">' + submodules + '</div>' : '');
    }).join("");

    // Wire toggle events
    taskTypeCards.querySelectorAll(".toggle-switch input[type=checkbox]").forEach(function (cb) {
      cb.addEventListener("change", async function () {
        var tool = cb.dataset.type;
        var enabled = cb.checked;
        var ok = await saveStructured({ task_types: [{ tool: tool, enabled: enabled }] });
        if (ok) {
          toast(escapeHtml(tool) + (enabled ? " enabled" : " disabled"), "success");
          renderTaskTypeCards();
        } else {
          cb.checked = !enabled;
        }
      });
    });

    // Wire inline field changes (auto-save on change)
    taskTypeCards.querySelectorAll(".card-field-input").forEach(function (input) {
      input.addEventListener("change", function () {
        saveCardField(input);
      });
    });

    // Wire expand/collapse
    taskTypeCards.querySelectorAll(".card-expand-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var card = btn.closest(".type-card");
        var body = card.querySelector(".type-card-body");
        if (!body) return;
        var expanded = body.style.display !== "none";
        body.style.display = expanded ? "none" : "";
        btn.classList.toggle("expanded", !expanded);
      });
    });
  }

  function buildCard(tool, displayName, ext, inputLabel, stageCount, paramCount, enabled, config) {
    var descParts = [];
    if (inputLabel) descParts.push(escapeHtml(inputLabel) + " input");
    if (stageCount) descParts.push(stageCount + " stage(s)");
    if (paramCount) descParts.push(paramCount + " param(s)");

    var metaHtml = renderConfigMeta(config);

    // Resource fields (always visible, inline)
    var resFieldsHtml = RESOURCE_FIELDS.map(function (f) {
      return buildFieldInput(f.key, f.label, f.type, f.placeholder, config, tool);
    }).join("");

    // SLURM fields (only if globally enabled)
    var slurmSectionHtml = "";
    if (slurmEnabled) {
      var slurmFieldsHtml = SLURM_FIELDS.filter(function (field) {
        return field.key !== "slurm_gres" || config.requires_gpu;
      }).map(function (f) {
        return buildFieldInput(f.key, f.label, f.type, f.placeholder, config, tool);
      }).join("");

      slurmSectionHtml =
        '<div class="card-section-label">SLURM <span class="card-badge-on">enabled</span></div>' +
        '<div class="card-field-grid">' + slurmFieldsHtml + '</div>';
    }

    var enableControl = config.is_workflow_stage ? '<span class="toggle-label">Workflow stage</span>' :
      '<span class="toggle-label ' + (enabled ? "enabled-text" : "disabled-text") + '">' +
        (enabled ? "Enabled" : "Disabled") +
      '</span>' +
      '<label class="toggle-switch">' +
        '<input type="checkbox" data-type="' + escapeHtml(tool) + '"' + (enabled ? " checked" : "") + '>' +
        '<span class="toggle-track"></span>' +
      '</label>';

    return (
      '<div class="type-card ' + (enabled ? "enabled" : "disabled") + '">' +
        '<div class="type-card-head">' +
          '<div>' +
            '<span class="type-card-name">' + escapeHtml(displayName) +
              (ext ? '<span class="type-card-ext">' + escapeHtml(ext) + '</span>' : '') +
            '</span>' +
          '</div>' +
          '<div class="card-head-right">' +
            enableControl +
            '<button class="card-expand-toggle" type="button" title="Configure resources" aria-label="Configure resources">' +
              '&#9881;' +
            '</button>' +
          '</div>' +
        '</div>' +
        (descParts.length ? '<p class="type-card-desc">' + descParts.join(" &middot; ") + '</p>' : '') +
        '<div class="type-card-meta">' + metaHtml + '</div>' +
        '<div class="type-card-body" style="display:none">' +
          '<div class="card-section-label">Resources</div>' +
          '<div class="card-field-grid">' + resFieldsHtml + '</div>' +
          slurmSectionHtml +
        '</div>' +
      '</div>'
    );
  }

  function buildFieldInput(key, label, type, placeholder, config, tool) {
    var val = config[key];

    if (type === "toggle") {
      return (
        '<label class="card-field">' +
          '<span class="card-field-label">' + escapeHtml(label) + '</span>' +
          '<label class="toggle-switch toggle-switch-sm">' +
            '<input type="checkbox" class="card-field-input" data-tool="' + escapeHtml(tool) +
              '" data-key="' + escapeHtml(key) + '"' + (val === true ? " checked" : "") + '>' +
            '<span class="toggle-track"></span>' +
          '</label>' +
        '</label>'
      );
    }

    return (
      '<label class="card-field">' +
        '<span class="card-field-label">' + escapeHtml(label) + '</span>' +
        '<input class="card-field-input config-value" type="' + type +
          '" data-tool="' + escapeHtml(tool) + '" data-key="' + escapeHtml(key) +
          '" value="' + escapeHtml(String(val != null ? val : "")) +
          '" placeholder="' + escapeHtml(placeholder) + '">' +
      '</label>'
    );
  }

  async function saveCardField(input) {
    var tool = input.dataset.tool;
    var key = input.dataset.key;
    var isToggle = input.type === "checkbox";
    var rawValue = isToggle ? input.checked : input.value.trim();

    var value;
    if (isToggle) {
      value = rawValue;
    } else if (rawValue === "") {
      value = null;
    } else if (key === "max_runtime_seconds") {
      value = parseRuntime(rawValue);
      if (value === null) { toast("Invalid runtime format — use 1:00:00 or 3600", "error"); return; }
    } else {
      var num = Number(rawValue);
      value = isNaN(num) ? rawValue : num;
    }

    var entry = { tool: tool };
    entry[key] = value;

    var cl = input.closest(".card-field");
    var label = cl ? cl.querySelector(".card-field-label").textContent : key;
    var ok = await saveStructured({ task_types: [entry] });
    if (ok) {
      toast(escapeHtml(tool) + ": " + escapeHtml(label) + " saved", "success");
      renderTaskTypeCards();
    }
  }

  function renderConfigMeta(config) {
    var parts = [];
    var effective = config.effective_resources;
    if (config.resource_error) return '<span class="config-error">Invalid: ' + escapeHtml(config.resource_error) + "</span>";
    if (effective) {
      parts.push("cpus=" + escapeHtml(String(effective.cpus)));
      parts.push("memory=" + escapeHtml(effective.memory));
      parts.push("runtime=" + formatRuntime(effective.max_runtime_seconds));
      if (effective.partition) parts.push("partition=" + escapeHtml(effective.partition));
      if (effective.gres) parts.push("gres=" + escapeHtml(effective.gres));
    }
    return parts.length
      ? parts.map(function (p) { return "<span>" + p + "</span>"; }).join(" &middot; ")
      : '<span class="muted">(no overrides — using global defaults)</span>';
  }

  // -- Resource table ----------------------------------------------------

  var RESOURCE_KEYS = [
    { key: "cpus",                 label: "CPU cores",              desc: "Default CPU allocation per scientific task" },
    { key: "memory",               label: "Memory",                 desc: "Default task memory, e.g. 4G or 16000M" },
    { key: "max_runtime_seconds",  label: "Maximum runtime",        desc: "Default wall-clock limit in seconds" },
  ];

  function getResourceKeys() {
    var keys = RESOURCE_KEYS.slice();
    keys.push({ key: "slurm_enabled",         label: "SLURM enabled",         desc: "Feature flag: true / false" });
    keys.push({ key: "slurm_allowed_queues",  label: "SLURM allowed queues",  desc: "Comma-separated partition names" });
    if (slurmEnabled) {
      SLURM_FIELDS.forEach(function (f) {
        var description = f.key === "slurm_gres"
          ? "Default for GPU task types only; CPU tasks never inherit it"
          : "Default when per-task not set";
        keys.push({ key: f.key, label: f.label + " (global)", desc: description });
      });
    }
    return keys;
  }

  function displayResourceValue(key, raw) {
    if (key === "max_runtime_seconds" && raw != null && raw !== "") return formatRuntime(raw);
    return raw || "";
  }

  function renderResourceTable() {
    var keys = getResourceKeys();
    resourceBody.innerHTML = keys.map(function (rk) {
      return '<tr>' +
        '<td><strong>' + escapeHtml(rk.label) + '</strong></td>' +
        '<td><input class="config-value" type="text" data-key="' + escapeHtml(rk.key) + '" value="' + escapeHtml(displayResourceValue(rk.key, resources[rk.key])) + '" placeholder="(default)"></td>' +
        '<td class="config-desc">' + escapeHtml(rk.desc) + '</td>' +
      '</tr>';
    }).join("");
    resourceSaveStatus.textContent = "";
  }

  saveResourcesBtn.addEventListener("click", async function () {
    saveResourcesBtn.disabled = true;
    resourceSaveStatus.textContent = "Saving…";
    var changed = {};
    resourceBody.querySelectorAll(".config-value").forEach(function (input) {
      var key = input.dataset.key;
      var val = input.value.trim();
      if (val === (resources[key] || "")) return;
      if (key === "max_runtime_seconds" && val !== "") {
        var parsed = parseRuntime(val);
        if (parsed === null) { toast("Invalid runtime format — use 1:00:00 or 3600", "error"); return; }
        changed[key] = String(parsed);
      } else {
        changed[key] = val === "" ? "" : val;
      }
    });
    if (!Object.keys(changed).length) {
      resourceSaveStatus.textContent = "No changes.";
      saveResourcesBtn.disabled = false;
      return;
    }
    var ok = await saveStructured({ resources: changed });
    saveResourcesBtn.disabled = false;
    resourceSaveStatus.textContent = ok ? "Saved " + Object.keys(changed).length + " value(s)." : "";
    if (ok) { toast("Resource settings saved.", "success"); renderResourceTable(); renderTaskTypeCards(); }
  });

  // -- Init --------------------------------------------------------------

  async function init() {
    await Promise.all([loadConfig(), loadTaskTypes()]);
    renderTaskTypeCards();
    renderResourceTable();
  }

  T.initToggle(document.getElementById("themeToggle"));

  init();
})();
