/* REvoDesign GREMLIN Server — Registration form handler */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var T = window.REvoDesignTheme;

  var form = document.getElementById("registerForm");
  var statusEl = document.getElementById("status");
  var submitBtn = document.getElementById("submitBtn");
  var resendRow = document.getElementById("resendRow");
  var resendBtn = document.getElementById("resendBtn");
  var captchaQuestion = document.getElementById("captchaQuestion");
  var captchaToken = document.getElementById("captchaToken");
  var captchaAnswer = document.getElementById("captchaAnswer");
  var registeredEmail = "";

  T.initToggle(document.getElementById("themeToggle"));

  function loadCaptcha() {
    captchaQuestion.textContent = "Loading…";
    captchaAnswer.value = "";
    captchaAnswer.disabled = true;
    fetch("/PSSM_GREMLIN/api/auth/captcha")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        captchaQuestion.textContent = data.question;
        captchaToken.value = data.token;
        captchaAnswer.disabled = false;
        captchaAnswer.focus();
      })
      .catch(function () {
        captchaQuestion.textContent = "(unavailable — refresh the page)";
      });
  }

  loadCaptcha();

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    statusEl.className = "status-msg";
    statusEl.textContent = "";
    resendRow.style.display = "none";
    submitBtn.disabled = true;
    submitBtn.textContent = "Registering…";

    var payload = {
      username: document.getElementById("username").value.trim(),
      email: document.getElementById("email").value.trim(),
      password: document.getElementById("password").value,
      affiliation: document.getElementById("affiliation").value.trim(),
      terms_agreed: document.getElementById("termsAgreed").checked,
      captcha_token: captchaToken.value,
      captcha_answer: captchaAnswer.value,
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
        statusEl.textContent = result.data.message;
        registeredEmail = payload.email;
        form.reset();
        if (resendRow) {
          resendRow.style.display = result.data.email_sent ? "block" : "block";
        }
      } else {
        statusEl.className = "status-msg error";
        statusEl.textContent = result.data.error || "Registration failed.";
        // Reload CAPTCHA on failure (answer consumed)
        loadCaptcha();
      }
    })
    .catch(function () {
      submitBtn.disabled = false;
      submitBtn.textContent = "Register";
      statusEl.className = "status-msg error";
      statusEl.textContent = "Network error. Please try again.";
      loadCaptcha();
    });
  });

  if (resendBtn) {
    resendBtn.addEventListener("click", function () {
      resendBtn.disabled = true;
      resendBtn.textContent = "Sending…";

      fetch("/PSSM_GREMLIN/api/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: registeredEmail })
      })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (result) {
        resendBtn.disabled = false;
        resendBtn.textContent = "Resend verification email";
        if (result.ok) {
          statusEl.className = "status-msg success";
          statusEl.textContent = result.data.message;
        } else {
          statusEl.className = "status-msg error";
          statusEl.textContent = result.data.error || "Failed to resend.";
        }
      })
      .catch(function () {
        resendBtn.disabled = false;
        resendBtn.textContent = "Resend verification email";
        statusEl.className = "status-msg error";
        statusEl.textContent = "Network error. Please try again.";
      });
    });
  }
})();
