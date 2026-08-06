/* REvoDesign GREMLIN Server — lazy active-log viewer */
(function () {
  "use strict";

  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;
  var selectedLog = "gunicorn-access";
  var activeController = null;
  var output = document.getElementById("logOutput");
  var status = document.getElementById("logStatus");
  var buttons = document.querySelectorAll(".log-select");
  var archivePanel = document.getElementById("archivePanel");
  var archiveTree = document.getElementById("archiveTree");
  var archiveStatus = document.getElementById("archiveStatus");
  var archivesLoaded = false;

  T.initToggle(document.getElementById("themeToggle"));

  function stopLoad() {
    if (activeController) {
      activeController.abort();
      activeController = null;
    }
  }

  async function loadSelectedLog() {
    stopLoad();
    var controller = new AbortController();
    activeController = controller;
    output.textContent = "";
    status.textContent = "Loading " + selectedLog + "…";

    try {
      var response = await A.authFetch(
        "/compute/api/auth/admin/logs/" + selectedLog,
        { signal: controller.signal }
      );
      if (!response.ok) {
        var error = await response.json();
        throw new Error(error.error || "Failed to load log");
      }
      if (!response.body) {
        output.textContent = await response.text();
      } else {
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var byteCount = 0;
        var result = await reader.read();
        while (!result.done) {
          byteCount += result.value.byteLength;
          output.appendChild(document.createTextNode(decoder.decode(result.value, { stream: true })));
          output.scrollTop = output.scrollHeight;
          status.textContent = "Streaming " + selectedLog + " — " + byteCount + " bytes";
          result = await reader.read();
        }
        output.appendChild(document.createTextNode(decoder.decode()));
      }
      status.textContent = "Loaded " + selectedLog;
    } catch (error) {
      if (error.name !== "AbortError") {
        status.textContent = error.message || "Failed to load log.";
      }
    } finally {
      if (activeController === controller) activeController = null;
    }
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    var value;
    var unit;
    if (bytes < 1024 * 1024) {
      value = bytes / 1024;
      unit = "KiB";
    } else if (bytes < 1024 * 1024 * 1024) {
      value = bytes / (1024 * 1024);
      unit = "MiB";
    } else if (bytes < 1024 * 1024 * 1024 * 1024) {
      value = bytes / (1024 * 1024 * 1024);
      unit = "GiB";
    } else {
      value = bytes / (1024 * 1024 * 1024 * 1024);
      unit = "TiB";
    }
    return value.toFixed(value >= 10 ? 0 : 1) + " " + unit;
  }

  function renderArchives(groups) {
    archiveTree.textContent = "";
    groups.forEach(function (group) {
      var branch = document.createElement("details");
      branch.className = "archive-branch";
      branch.open = group.archives.length > 0;

      var summary = document.createElement("summary");
      summary.textContent = group.filename + " (" + group.archives.length + ")";
      branch.appendChild(summary);

      var list = document.createElement("ul");
      group.archives.forEach(function (archive) {
        var item = document.createElement("li");
        var link = document.createElement("a");
        link.href = "/compute/api/auth/admin/logs/archives/" +
          encodeURIComponent(archive.filename);
        link.download = archive.filename;
        link.textContent = archive.filename;
        item.appendChild(link);

        var metadata = document.createElement("span");
        metadata.className = "archive-meta";
        metadata.textContent = formatSize(archive.size) + " · " +
          new Date(archive.modified_at * 1000).toLocaleString();
        item.appendChild(metadata);
        list.appendChild(item);
      });
      if (!group.archives.length) {
        var empty = document.createElement("li");
        empty.className = "muted";
        empty.textContent = "No rotated files";
        list.appendChild(empty);
      }
      branch.appendChild(list);
      archiveTree.appendChild(branch);
    });
  }

  async function loadArchives() {
    archiveStatus.textContent = "Loading rotated logs…";
    try {
      var response = await A.authFetch(
        "/compute/api/auth/admin/logs/archives"
      );
      var result = await response.json();
      if (!response.ok) throw new Error(result.error || "Failed to load rotated logs");
      renderArchives(result.logs || []);
      archivesLoaded = true;
      archiveStatus.textContent = "Rotated logs loaded.";
    } catch (error) {
      archiveStatus.textContent = error.message || "Failed to load rotated logs.";
    }
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      buttons.forEach(function (item) { item.classList.remove("active"); });
      button.classList.add("active");
      selectedLog = button.dataset.log;
      loadSelectedLog();
    });
  });
  document.getElementById("refreshLog").addEventListener("click", loadSelectedLog);
  archivePanel.addEventListener("toggle", function () {
    if (archivePanel.open && !archivesLoaded) loadArchives();
  });
  document.getElementById("refreshArchives").addEventListener("click", loadArchives);
  document.getElementById("logoutBtn").addEventListener("click", function () {
    function finishLogout() {
      A.clearToken();
      window.location.replace("/compute/login");
    }
    A.authFetch("/compute/api/auth/logout", { method: "POST" })
      .then(finishLogout)
      .catch(finishLogout);
  });
  loadSelectedLog();
}());
