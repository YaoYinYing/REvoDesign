/* REvoCompute — Configuration page logic */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var A = window.REvoDesignAuth;

  // -- DOM refs ----------------------------------------------------------

  var taskTypeCards = document.getElementById("taskTypeCards");
  var taskTypeStatus = document.getElementById("taskTypeStatus");
  var resourceBody = document.getElementById("resourceBody");
  var resourceSaveStatus = document.getElementById("resourceSaveStatus");
  var saveResourcesBtn = document.getElementById("saveResourcesBtn");
  var allKeysBody = document.getElementById("allKeysBody");
  var allSaveStatus = document.getElementById("allSaveStatus");
  var saveAllBtn = document.getElementById("saveAllBtn");
  var addRowBtn = document.getElementById("addRowBtn");
  var logoutBtn = document.getElementById("logoutBtn");
  var toastWrap = document.getElementById("toastWrap");

  if (logoutBtn) {
    logoutBtn.addEventListener("click", function () {
      A.authFetch("/compute/api/auth/logout", { method: "POST" })
        .finally(function () { A.clearToken(); window.location.href = "/compute/login"; });
    });
  }

  // -- State -------------------------------------------------------------

  var taskTypeConfigs = [];     // from admin config API: [{tool, enabled, nproc, ...slurm_*}]
  var resources = {};           // {key: value}
  var taskTypes = [];           // from /api/types (metadata: display_name, params, etc.)
  var slurmEnabled = false;     // global SLURM feature flag
  var slurmAllowedQueues = [];  // whitelisted partitions
  var allKeysOriginal = {};

  var SLURM_FIELDS = [
    { key: "slurm_partition",     label: "Partition",     type: "text",    placeholder: "e.g. gpu" },
    { key: "slurm_cpus_per_task", label: "CPUs / task",   type: "number",  placeholder: "e.g. 8" },
    { key: "slurm_gres",          label: "GRES",          type: "text",    placeholder: "e.g. gpu:A100:1" },
    { key: "slurm_mem",           label: "Memory",        type: "text",    placeholder: "e.g. 64G" },
    { key: "slurm_time",          label: "Time limit",    type: "text",    placeholder: "e.g. 04:00:00" },
    { key: "slurm_nodes",         label: "Nodes",         type: "number",  placeholder: "e.g. 1" },
    { key: "slurm_ntasks",        label: "NTasks",        type: "number",  placeholder: "e.g. 1" },
    { key: "slurm_qos",           label: "QOS",           type: "text",    placeholder: "e.g. normal" },
    { key: "slurm_account",       label: "Account",       type: "text",    placeholder: "e.g. lab-abc" },
    { key: "slurm_constraint",    label: "Constraint",    type: "text",    placeholder: "e.g. avx512" },
    { key: "slurm_exclusive",     label: "Exclusive",     type: "toggle",  placeholder: "" },
  ];

  var RESOURCE_FIELDS = [
    { key: "nproc",                label: "nproc",      type: "number", placeholder: "CPU cores" },
    { key: "maxmem",               label: "maxmem",     type: "number", placeholder: "Memory GB" },
    { key: "max_runtime_seconds",  label: "Max runtime", type: "number", placeholder: "seconds" },
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

  // -- Helpers -----------------------------------------------------------

  function esc(s) { return String(s).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"); }

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
      taskTypes = await resp.json();
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

    var enabledCount = taskTypeConfigs.filter(function (c) { return c.enabled !== false; }).length;
    taskTypeStatus.textContent = taskTypeConfigs.length + " type(s) &middot; " + enabledCount + " enabled";

    taskTypeCards.innerHTML = taskTypeConfigs.map(function (config) {
      var meta = findTypeMeta(config.tool);
      var displayName = meta ? meta.display_name : config.tool;
      var ext = meta ? meta.input_extension : "";
      var inputLabel = meta ? meta.input_label : "";
      var stageCount = meta ? Object.keys(meta.stage_markers).length : 0;
      var paramCount = meta ? meta.params.length : 0;
      var enabled = config.enabled !== false;

      return buildCard(config.tool, displayName, ext, inputLabel, stageCount, paramCount, enabled, config);
    }).join("");

    // Wire toggle events
    taskTypeCards.querySelectorAll(".toggle-switch input[type=checkbox]").forEach(function (cb) {
      cb.addEventListener("change", async function () {
        var tool = cb.dataset.type;
        var enabled = cb.checked;
        var ok = await saveStructured({ task_types: [{ tool: tool, enabled: enabled }] });
        if (ok) {
          toast(esc(tool) + (enabled ? " enabled" : " disabled"), "success");
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
    if (inputLabel) descParts.push(esc(inputLabel) + " input");
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
      var slurmFieldsHtml = SLURM_FIELDS.map(function (f) {
        return buildFieldInput(f.key, f.label, f.type, f.placeholder, config, tool);
      }).join("");

      slurmSectionHtml =
        '<div class="card-section-label">SLURM <span class="card-badge-on">enabled</span></div>' +
        '<div class="card-field-grid">' + slurmFieldsHtml + '</div>';
    }

    return (
      '<div class="type-card ' + (enabled ? "enabled" : "disabled") + '">' +
        '<div class="type-card-head">' +
          '<div>' +
            '<span class="type-card-name">' + esc(displayName) +
              (ext ? '<span class="type-card-ext">' + esc(ext) + '</span>' : '') +
            '</span>' +
          '</div>' +
          '<div class="card-head-right">' +
            '<span class="toggle-label ' + (enabled ? "enabled-text" : "disabled-text") + '">' +
              (enabled ? "Enabled" : "Disabled") +
            '</span>' +
            '<label class="toggle-switch">' +
              '<input type="checkbox" data-type="' + esc(tool) + '"' + (enabled ? " checked" : "") + '>' +
              '<span class="toggle-track"></span>' +
            '</label>' +
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
          '<span class="card-field-label">' + esc(label) + '</span>' +
          '<label class="toggle-switch toggle-switch-sm">' +
            '<input type="checkbox" class="card-field-input" data-tool="' + esc(tool) +
              '" data-key="' + esc(key) + '"' + (val === true ? " checked" : "") + '>' +
            '<span class="toggle-track"></span>' +
          '</label>' +
        '</label>'
      );
    }

    return (
      '<label class="card-field">' +
        '<span class="card-field-label">' + esc(label) + '</span>' +
        '<input class="card-field-input config-value" type="' + type +
          '" data-tool="' + esc(tool) + '" data-key="' + esc(key) +
          '" value="' + esc(String(val != null ? val : "")) +
          '" placeholder="' + esc(placeholder) + '">' +
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
      // ponytail: empty = inherit global, skip save
      return;
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
      toast(esc(tool) + ": " + esc(label) + " saved", "success");
      renderTaskTypeCards();
    }
  }

  function renderConfigMeta(config) {
    var parts = [];
    if (config.nproc != null) parts.push("nproc=" + esc(String(config.nproc)));
    if (config.maxmem != null) parts.push("maxmem=" + esc(String(config.maxmem)) + "G");
    if (config.max_runtime_seconds != null) {
      parts.push("runtime=" + Math.round(config.max_runtime_seconds / 60) + "min");
    }
    if (slurmEnabled) {
      if (config.slurm_partition) parts.push("partition=" + esc(config.slurm_partition));
      if (config.slurm_cpus_per_task) parts.push("cpus=" + esc(String(config.slurm_cpus_per_task)));
      if (config.slurm_gres) parts.push("gres=" + esc(config.slurm_gres));
    }
    return parts.length
      ? parts.map(function (p) { return "<span>" + p + "</span>"; }).join(" &middot; ")
      : '<span class="muted">(no overrides — using global defaults)</span>';
  }

  // -- Resource table ----------------------------------------------------

  var RESOURCE_KEYS = [
    { key: "nproc",                label: "nproc",                 desc: "CPU cores per runner container" },
    { key: "maxmem",               label: "maxmem",                desc: "Memory limit (GB) per runner" },
    { key: "worker_concurrency",   label: "Worker concurrency",    desc: "Celery concurrent jobs" },
    { key: "gunicorn_workers",     label: "Gunicorn workers",      desc: "Number of web workers" },
    { key: "result_retention_days",label: "Result retention",      desc: "Days before cleanup (fractional OK)" },
  ];

  function getResourceKeys() {
    var keys = RESOURCE_KEYS.slice();
    if (slurmEnabled) {
      keys.push({ key: "slurm_enabled",         label: "SLURM enabled",         desc: "Feature flag: true / false" });
      keys.push({ key: "slurm_allowed_queues",  label: "SLURM allowed queues",  desc: "Comma-separated partition names" });
      SLURM_FIELDS.forEach(function (f) {
        keys.push({ key: f.key, label: f.label + " (global)", desc: "Default when per-task not set" });
      });
    }
    return keys;
  }

  function renderResourceTable() {
    var keys = getResourceKeys();
    resourceBody.innerHTML = keys.map(function (rk) {
      return '<tr>' +
        '<td><strong>' + esc(rk.label) + '</strong></td>' +
        '<td><input class="config-value" type="text" data-key="' + esc(rk.key) + '" value="' + esc(resources[rk.key] || "") + '" placeholder="(default)"></td>' +
        '<td class="config-desc">' + esc(rk.desc) + '</td>' +
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
      if (val !== (resources[key] || "")) changed[key] = val;
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

  // -- All Keys (advanced) -----------------------------------------------

  function flattenAll() {
    var result = {};
    taskTypeConfigs.forEach(function (c) {
      var prefix = "task_type." + c.tool;
      result[prefix + ".enabled"] = c.enabled ? "true" : "false";
      RESOURCE_FIELDS.forEach(function (f) {
        if (c[f.key] != null) result[prefix + "." + f.key] = String(c[f.key]);
      });
      if (slurmEnabled) {
        SLURM_FIELDS.forEach(function (f) {
          if (c[f.key] != null) {
            result[prefix + "." + f.key] = typeof c[f.key] === "boolean"
              ? (c[f.key] ? "true" : "false")
              : String(c[f.key]);
          }
        });
      }
    });
    Object.keys(resources).forEach(function (k) { result[k] = resources[k]; });
    return result;
  }

  function renderAllKeys() {
    var flat = flattenAll();
    allKeysOriginal = Object.assign({}, flat);
    var keys = Object.keys(flat).sort();
    allKeysBody.innerHTML = "";
    if (!keys.length) {
      allKeysBody.innerHTML = '<tr><td colspan="3" class="empty">No configuration entries yet.</td></tr>';
      return;
    }
    keys.forEach(function (k) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        '<td><input class="config-key" type="text" value="' + esc(k) + '"></td>' +
        '<td><input class="config-value" type="text" value="' + esc(flat[k]) + '"></td>' +
        '<td><button class="btn btn-soft delete-row-btn" type="button">&times;</button></td>';
      tr.querySelector(".delete-row-btn").addEventListener("click", function () { tr.remove(); });
      allKeysBody.appendChild(tr);
    });
    allSaveStatus.textContent = "";
  }

  function readAllKeysTable() {
    var rows = allKeysBody.querySelectorAll("tr");
    var data = {};
    rows.forEach(function (tr) {
      var keyInput = tr.querySelector(".config-key");
      var valInput = tr.querySelector(".config-value");
      if (keyInput && valInput) {
        var key = keyInput.value.trim();
        if (key) data[key] = valInput.value;
      }
    });
    return data;
  }

  function allKeysDiff(current) {
    var all = {};
    Object.keys(allKeysOriginal).forEach(function (k) { all[k] = true; });
    Object.keys(current).forEach(function (k) { all[k] = true; });
    var changed = {};
    Object.keys(all).forEach(function (k) {
      if (allKeysOriginal[k] !== current[k]) changed[k] = current[k] !== undefined ? current[k] : null;
    });
    return changed;
  }

  function flatToStructured(flat) {
    var taskTypeUpdates = {};
    var resourceUpdates = {};
    Object.keys(flat).forEach(function (k) {
      if (k.startsWith("task_type.")) {
        var parts = k.split(".");
        if (parts.length >= 3) {
          var tool = parts[1];
          var field = parts.slice(2).join(".");
          if (!taskTypeUpdates[tool]) taskTypeUpdates[tool] = {};
          var val = flat[k];
          if (field === "enabled" || field === "slurm_exclusive") {
            taskTypeUpdates[tool][field] = val.toLowerCase() === "true";
          } else if (field === "nproc" || field === "maxmem" || field === "max_runtime_seconds" ||
                     field === "slurm_cpus_per_task" || field === "slurm_nodes" || field === "slurm_ntasks") {
            var num = parseInt(val, 10);
            if (!isNaN(num)) taskTypeUpdates[tool][field] = num;
            else taskTypeUpdates[tool][field] = val;
          } else {
            taskTypeUpdates[tool][field] = val;
          }
        }
      } else {
        resourceUpdates[k] = flat[k];
      }
    });
    return {
      task_types: Object.keys(taskTypeUpdates).map(function (tool) {
        return Object.assign({ tool: tool }, taskTypeUpdates[tool]);
      }),
      resources: resourceUpdates,
    };
  }

  saveAllBtn.addEventListener("click", async function () {
    var current = readAllKeysTable();
    var changed = allKeysDiff(current);
    if (!Object.keys(changed).length) {
      allSaveStatus.textContent = "No changes.";
      return;
    }
    saveAllBtn.disabled = true;
    allSaveStatus.textContent = "Saving…";
    var structured = flatToStructured(current);
    var ok = await saveStructured(structured);
    saveAllBtn.disabled = false;
    if (ok) {
      allSaveStatus.textContent = "Saved " + Object.keys(changed).length + " key(s).";
      toast("Configuration saved.", "success");
      renderAllKeys();
      renderTaskTypeCards();
      renderResourceTable();
    } else {
      allSaveStatus.textContent = "";
    }
  });

  addRowBtn.addEventListener("click", function () {
    var placeholder = allKeysBody.querySelector("tr td.empty");
    if (placeholder) allKeysBody.innerHTML = "";
    var tr = document.createElement("tr");
    tr.innerHTML =
      '<td><input class="config-key" type="text" value="" placeholder="key"></td>' +
      '<td><input class="config-value" type="text" value="" placeholder="value"></td>' +
      '<td><button class="btn btn-soft delete-row-btn" type="button">&times;</button></td>';
    tr.querySelector(".delete-row-btn").addEventListener("click", function () { tr.remove(); });
    allKeysBody.appendChild(tr);
    tr.querySelector(".config-key").focus();
  });

  // -- Init --------------------------------------------------------------

  async function init() {
    await Promise.all([loadConfig(), loadTaskTypes()]);
    renderTaskTypeCards();
    renderResourceTable();
    renderAllKeys();
  }

  init();
})();
