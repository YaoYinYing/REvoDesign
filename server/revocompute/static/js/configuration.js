/* REvoCompute — Configuration page logic */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var A = window.REvoDesignAuth;

  var tbody = document.getElementById("configBody");
  var saveBtn = document.getElementById("saveBtn");
  var addBtn = document.getElementById("addRowBtn");
  var saveStatus = document.getElementById("saveStatus");
  var logoutBtn = document.getElementById("logoutBtn");

  if (logoutBtn) {
    logoutBtn.addEventListener("click", function () {
      A.authFetch("/compute/api/auth/logout", { method: "POST" })
        .finally(function () { A.clearToken(); window.location.href = "/compute/login"; });
    });
  }

  // -- state --------------------------------------------------------------

  var original = {};  // snapshot after last load/save

  // -- rendering ----------------------------------------------------------

  function renderRow(key, value) {
    var tr = document.createElement("tr");
    tr.innerHTML =
      '<td><input class="text-input config-key" type="text" value="' + esc(key) + '"></td>' +
      '<td><input class="text-input config-value" type="text" value="' + esc(value) + '"></td>' +
      '<td><button class="btn btn-soft delete-row-btn" type="button">&times;</button></td>';
    tr.querySelector(".delete-row-btn").addEventListener("click", function () { tr.remove(); });
    return tr;
  }

  function renderAll(data) {
    original = data || {};
    tbody.innerHTML = "";
    var keys = Object.keys(original).sort();
    if (keys.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" class="muted" style="text-align:center;">No configuration entries yet. Click "Add Row" to create one.</td></tr>';
      return;
    }
    keys.forEach(function (k) {
      tbody.appendChild(renderRow(k, original[k]));
    });
  }

  // -- helpers ------------------------------------------------------------

  function esc(s) { return String(s).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"); }

  function readTable() {
    var rows = tbody.querySelectorAll("tr");
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

  function diff(a, b) {
    var allKeys = {};
    Object.keys(a).forEach(function (k) { allKeys[k] = true; });
    Object.keys(b).forEach(function (k) { allKeys[k] = true; });
    var changed = {};
    Object.keys(allKeys).forEach(function (k) {
      if (a[k] !== b[k]) changed[k] = b[k] !== undefined ? b[k] : null;
    });
    return changed;
  }

  // -- API ----------------------------------------------------------------

  async function loadConfig() {
    saveStatus.textContent = "Loading…";
    try {
      var resp = await A.authFetch("/compute/api/auth/admin/config");
      if (!resp.ok) { saveStatus.textContent = "Load failed: " + resp.status; return; }
      var data = await resp.json();
      renderAll(data);
      saveStatus.textContent = "";
    } catch (e) {
      saveStatus.textContent = "Load error: " + e.message;
    }
  }

  async function saveConfig(changed) {
    saveBtn.disabled = true;
    saveStatus.textContent = "Saving…";
    try {
      var resp = await A.authFetch("/compute/api/auth/admin/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changed),
      });
      if (!resp.ok) { saveStatus.textContent = "Save failed: " + resp.status; return; }
      saveStatus.textContent = "Saved " + Object.keys(changed).length + " key(s).";
      await loadConfig();
    } catch (e) {
      saveStatus.textContent = "Save error: " + e.message;
    } finally {
      saveBtn.disabled = false;
    }
  }

  // -- events -------------------------------------------------------------

  saveBtn.addEventListener("click", function () {
    var current = readTable();
    var changed = diff(original, current);
    if (Object.keys(changed).length === 0) {
      saveStatus.textContent = "No changes to save.";
      return;
    }
    saveConfig(changed);
  });

  addBtn.addEventListener("click", function () {
    var placeholder = tbody.querySelector("tr td[colspan]");
    if (placeholder) tbody.innerHTML = "";
    tbody.appendChild(renderRow("", ""));
    tbody.lastElementChild.querySelector(".config-key").focus();
  });

  loadConfig();
})();
