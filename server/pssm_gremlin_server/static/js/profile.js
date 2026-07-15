/* REvoDesign GREMLIN Server — Profile page */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;

  var form = document.getElementById("passwordForm");
  var statusEl = document.getElementById("status");
  var submitBtn = document.getElementById("submitBtn");
  var infoEl = document.getElementById("userInfo");

  T.initToggle(document.getElementById("themeToggle"));

  /* Load current user info */
  A.authFetch("/PSSM_GREMLIN/api/auth/me")
    .then(function (r) { return r.json(); })
    .then(function (user) {
      var label = user.role === "guest" ? " (guest account)" : "";
      infoEl.textContent = "Logged in as " + user.username + " (" + user.email + ")" + label;
      if (user.role === "guest") {
        document.getElementById("passwordSection").style.display = "none";
        document.getElementById("apiKeySection").style.display = "none";
      }
    })
    .catch(function () {
      infoEl.textContent = "Unable to load profile.";
    });

  /* Password change */
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    statusEl.className = "status-msg";
    statusEl.textContent = "";
    submitBtn.disabled = true;

    var newPassword = document.getElementById("newPassword").value;
    var confirmPassword = document.getElementById("confirmPassword").value;

    if (newPassword !== confirmPassword) {
      statusEl.className = "status-msg error";
      statusEl.textContent = "New passwords do not match.";
      submitBtn.disabled = false;
      return;
    }

    if (newPassword.length < 8) {
      statusEl.className = "status-msg error";
      statusEl.textContent = "Password must be at least 8 characters.";
      submitBtn.disabled = false;
      return;
    }

    var payload = {
      current_password: document.getElementById("currentPassword").value,
      new_password: newPassword
    };

    A.authFetch("/PSSM_GREMLIN/api/auth/me", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (result) {
        submitBtn.disabled = false;
        if (result.ok) {
          statusEl.className = "status-msg success";
          statusEl.textContent = "Password updated successfully.";
          form.reset();
        } else {
          statusEl.className = "status-msg error";
          statusEl.textContent = result.data.error || "Failed to update password.";
        }
      })
      .catch(function () {
        submitBtn.disabled = false;
        statusEl.className = "status-msg error";
        statusEl.textContent = "Network error. Please try again.";
      });
  });

  /* ---- API key management ---- */

  var apiKeyStatus = document.getElementById("apiKeyStatus");
  var generateBtn = document.getElementById("generateKeyBtn");
  var revokeBtn = document.getElementById("revokeKeyBtn");
  var apiKeyDisplay = document.getElementById("apiKeyDisplay");
  var apiKeyValue = document.getElementById("apiKeyValue");
  var apiKeyMsg = document.getElementById("apiKeyMsg");

  function refreshApiKeyStatus() {
    A.authFetch("/PSSM_GREMLIN/api/auth/me/api-key")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.has_api_key) {
          apiKeyStatus.textContent = "You have an active API key. Use it with the X-API-Key header for programmatic access.";
          generateBtn.style.display = "inline-block";
          revokeBtn.style.display = "inline-block";
          generateBtn.textContent = "Regenerate API Key";
        } else {
          apiKeyStatus.textContent = "No API key configured. Generate one for programmatic access.";
          generateBtn.style.display = "inline-block";
          revokeBtn.style.display = "none";
          generateBtn.textContent = "Generate API Key";
        }
        /* ponytail: only hide the key display if the user is NOT currently
           looking at a freshly-generated key (the value input is empty). */
        if (!apiKeyValue.value) {
          apiKeyDisplay.style.display = "none";
        }
      })
      .catch(function () {
        apiKeyStatus.textContent = "Unable to load API key status.";
      });
  }

  generateBtn.addEventListener("click", function () {
    apiKeyMsg.className = "status-msg";
    apiKeyMsg.textContent = "";
    generateBtn.disabled = true;

    A.authFetch("/PSSM_GREMLIN/api/auth/me/api-key", { method: "POST" })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (result) {
        generateBtn.disabled = false;
        if (result.ok && result.data.api_key) {
          apiKeyValue.value = result.data.api_key;
          apiKeyDisplay.style.display = "block";
          apiKeyMsg.className = "status-msg success";
          apiKeyMsg.textContent = result.data.message;
          refreshApiKeyStatus();
          generateBtn.textContent = "Regenerate API Key";
          revokeBtn.style.display = "inline-block";
          apiKeyStatus.textContent = "You have an active API key.";
        } else {
          apiKeyMsg.className = "status-msg error";
          apiKeyMsg.textContent = result.data.error || "Failed to generate API key.";
        }
      })
      .catch(function () {
        generateBtn.disabled = false;
        apiKeyMsg.className = "status-msg error";
        apiKeyMsg.textContent = "Network error. Please try again.";
      });
  });

  revokeBtn.addEventListener("click", function () {
    if (!confirm("Revoke your API key? All existing uses will stop working.")) return;
    apiKeyMsg.className = "status-msg";
    apiKeyMsg.textContent = "";
    revokeBtn.disabled = true;

    A.authFetch("/PSSM_GREMLIN/api/auth/me/api-key", { method: "DELETE" })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (result) {
        revokeBtn.disabled = false;
        if (result.ok) {
          apiKeyMsg.className = "status-msg success";
          apiKeyMsg.textContent = "API key revoked.";
          apiKeyDisplay.style.display = "none";
          refreshApiKeyStatus();
        } else {
          apiKeyMsg.className = "status-msg error";
          apiKeyMsg.textContent = result.data.error || "Failed to revoke API key.";
        }
      })
      .catch(function () {
        revokeBtn.disabled = false;
        apiKeyMsg.className = "status-msg error";
        apiKeyMsg.textContent = "Network error. Please try again.";
      });
  });

  refreshApiKeyStatus();

  /* ---- Logout ---- */
  var logoutBtn = document.getElementById("logoutBtn");
  logoutBtn.addEventListener("click", function () {
    /* The cookie is HttpOnly — JS can't touch it.  Ask the server to clear it. */
    A.authFetch("/PSSM_GREMLIN/api/auth/logout", { method: "POST" })
      .then(function () {
        A.clearToken();
        window.location.href = "/PSSM_GREMLIN/login";
      })
      .catch(function () {
        /* Even if the request fails (network), clear local state and move on. */
        A.clearToken();
        window.location.href = "/PSSM_GREMLIN/login";
      });
  });

  /* ---- Copy API key ---- */
  var copyBtn = document.getElementById("copyKeyBtn");
  copyBtn.addEventListener("click", function () {
    var input = document.getElementById("apiKeyValue");
    input.select();
    input.setSelectionRange(0, 99999); /* mobile */
    try {
      navigator.clipboard.writeText(input.value).then(function () {
        copyBtn.textContent = "✓";
        setTimeout(function () { copyBtn.textContent = "⨏"; }, 1600);
      });
    } catch (_) {
      /* fallback: selection above already copied for manual Ctrl+C */
      copyBtn.textContent = "✓";
      setTimeout(function () { copyBtn.textContent = "⨏"; }, 1600);
    }
  });
})();
