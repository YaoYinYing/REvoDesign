/* REvoCompute — Reset Password page logic */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var T = window.REvoDesignTheme;
  T.initToggle(document.getElementById("themeToggle"));

  var form = document.getElementById("resetForm");
  var statusEl = document.getElementById("status");
  var submitBtn = document.getElementById("submitBtn");

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    statusEl.className = "status-msg";
    statusEl.textContent = "";
    submitBtn.disabled = true;
    submitBtn.textContent = "Setting…";

    var payload = {
      token: new URLSearchParams(window.location.search).get("c") || "",
      password: document.getElementById("password").value,
    };

    fetch("/compute/reset_password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (result) {
        if (result.ok) {
          statusEl.className = "status-msg ok";
          statusEl.textContent = result.data.message + " Redirecting to login…";
          setTimeout(function () { window.location.href = "/compute/login"; }, 2000);
        } else {
          submitBtn.disabled = false;
          submitBtn.textContent = "Set Password";
          statusEl.className = "status-msg error";
          statusEl.textContent = result.data.error || "Reset failed.";
        }
      })
      .catch(function () {
        submitBtn.disabled = false;
        submitBtn.textContent = "Set Password";
        statusEl.className = "status-msg error";
        statusEl.textContent = "Network error. Please try again.";
      });
  });
})();
