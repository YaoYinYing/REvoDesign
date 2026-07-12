/* REvoDesign GREMLIN Server — Registration form handler */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var T = window.REvoDesignTheme;

  var form = document.getElementById("registerForm");
  var statusEl = document.getElementById("status");
  var submitBtn = document.getElementById("submitBtn");

  T.initToggle(document.getElementById("themeToggle"));

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    statusEl.className = "status-msg";
    statusEl.textContent = "";
    submitBtn.disabled = true;
    submitBtn.textContent = "Registering…";

    var payload = {
      username: document.getElementById("username").value.trim(),
      email: document.getElementById("email").value.trim(),
      password: document.getElementById("password").value
    };

    fetch("/PSSM_GREMLIN/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
    .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, status: r.status, data: data }; }); })
    .then(function (result) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Register";
      if (result.ok) {
        statusEl.className = "status-msg success";
        statusEl.textContent = result.data.message + " You can now log in.";
        form.reset();
      } else {
        statusEl.className = "status-msg error";
        statusEl.textContent = result.data.error || "Registration failed.";
      }
    })
    .catch(function () {
      submitBtn.disabled = false;
      submitBtn.textContent = "Register";
      statusEl.className = "status-msg error";
      statusEl.textContent = "Network error. Please try again.";
    });
  });
})();
