/* REvoDesign GREMLIN Server — Login form handler */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;

  var form = document.getElementById("loginForm");
  var statusEl = document.getElementById("status");
  var submitBtn = document.getElementById("submitBtn");

  T.initToggle(document.getElementById("themeToggle"));

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    statusEl.className = "status-msg";
    statusEl.textContent = "";
    submitBtn.disabled = true;
    submitBtn.textContent = "Logging in…";

    var payload = {
      username: document.getElementById("username").value.trim(),
      password: document.getElementById("password").value
    };

    fetch("/PSSM_GREMLIN/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
    .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
    .then(function (result) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Log In";
      if (result.ok) {
        A.setToken(result.data.token);
        statusEl.className = "status-msg success";
        statusEl.textContent = "Logged in as " + result.data.username + ". Redirecting to dashboard…";
        setTimeout(function () { window.location.href = "/PSSM_GREMLIN/dashboard"; }, 800);
      } else {
        statusEl.className = "status-msg error";
        statusEl.textContent = result.data.error || "Login failed.";
      }
    })
    .catch(function () {
      submitBtn.disabled = false;
      submitBtn.textContent = "Log In";
      statusEl.className = "status-msg error";
      statusEl.textContent = "Network error. Please try again.";
    });
  });

  // ---- Forgot password ----

  var forgotLink = document.getElementById("forgotLink");
  var forgotSection = document.getElementById("forgotSection");
  var forgotForm = document.getElementById("forgotForm");
  var forgotStatus = document.getElementById("forgotStatus");
  var forgotSubmitBtn = document.getElementById("forgotSubmitBtn");

  forgotLink.addEventListener("click", function (e) {
    e.preventDefault();
    forgotSection.style.display = forgotSection.style.display === "none" ? "block" : "none";
  });

  forgotForm.addEventListener("submit", function (e) {
    e.preventDefault();
    forgotStatus.className = "status-msg";
    forgotStatus.textContent = "";
    forgotSubmitBtn.disabled = true;
    forgotSubmitBtn.textContent = "Sending…";

    fetch("/PSSM_GREMLIN/api/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: document.getElementById("forgotEmail").value.trim() }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (result) {
        forgotSubmitBtn.disabled = false;
        forgotSubmitBtn.textContent = "Send Reset Link";
        if (result.ok) {
          forgotStatus.className = "status-msg ok";
          forgotStatus.textContent = result.data.message;
          forgotForm.reset();
        } else {
          forgotStatus.className = "status-msg error";
          forgotStatus.textContent = result.data.error || "Request failed.";
        }
      })
      .catch(function () {
        forgotSubmitBtn.disabled = false;
        forgotSubmitBtn.textContent = "Send Reset Link";
        forgotStatus.className = "status-msg error";
        forgotStatus.textContent = "Network error. Please try again.";
      });
  });
})();
