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
        "/PSSM_GREMLIN/api/auth/admin/logs/" + selectedLog,
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
        while (true) {
          var result = await reader.read();
          if (result.done) break;
          byteCount += result.value.byteLength;
          output.appendChild(document.createTextNode(decoder.decode(result.value, { stream: true })));
          output.scrollTop = output.scrollHeight;
          status.textContent = "Streaming " + selectedLog + " — " + byteCount + " bytes";
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

  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      buttons.forEach(function (item) { item.classList.remove("active"); });
      button.classList.add("active");
      selectedLog = button.dataset.log;
      loadSelectedLog();
    });
  });
  document.getElementById("refreshLog").addEventListener("click", loadSelectedLog);
  document.getElementById("logoutBtn").addEventListener("click", function () {
    A.authFetch("/PSSM_GREMLIN/api/auth/logout", { method: "POST" })
      .then(function () { A.clearToken(); window.location.href = "/PSSM_GREMLIN/login"; })
      .catch(function () { A.clearToken(); window.location.href = "/PSSM_GREMLIN/login"; });
  });
  loadSelectedLog();
}());
