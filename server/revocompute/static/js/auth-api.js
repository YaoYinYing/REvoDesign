/* REvoCompute — Auth token helpers */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var TOKEN_KEY = "revodesign-auth-token";

  function getToken() {
    try { return window.sessionStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; }
  }

  function setToken(token) {
    try { window.sessionStorage.setItem(TOKEN_KEY, token); } catch (e) {}
  }

  function clearToken() {
    try { window.sessionStorage.removeItem(TOKEN_KEY); } catch (e) {}
  }

  var _tokenRefreshPromise = null;

  async function ensureToken() {
    // ponytail: request a fresh Bearer token via the cookie-authenticated
    // refresh endpoint.  Deduplicate concurrent refreshes.
    if (_tokenRefreshPromise) return _tokenRefreshPromise;
    _tokenRefreshPromise = (async function () {
      try {
        var res = await fetch("/compute/api/auth/token", { credentials: "same-origin" });
        if (res.ok) {
          var data = await res.json();
          setToken(data.token);
          return data.token;
        }
      } catch (e) { /* network error — caller will retry without token */ }
      return "";
    })();
    var token = await _tokenRefreshPromise;
    _tokenRefreshPromise = null;
    return token;
  }

  async function authFetch(url, options) {
    options = options || {};
    options.headers = options.headers || {};
    options.credentials = "same-origin";
    var token = getToken();
    if (!token) {
      token = await ensureToken();
    }
    if (token) {
      options.headers["Authorization"] = "Bearer " + token;
    }
    var response = await fetch(url, options);
    // If the stored token is stale (e.g. expired or version-bumped),
    // refresh once and retry before giving up.
    if (response.status === 403) {
      try {
        var body = await response.clone().json();
        if (body.error && body.error.indexOf("Bearer token") !== -1) {
          clearToken();
          token = await ensureToken();
          if (token) {
            options.headers["Authorization"] = "Bearer " + token;
            response = await fetch(url, options);
          }
        }
      } catch (e) { /* non-JSON body — pass through original response */ }
    }
    if (response.status === 401) {
      clearToken();
      window.location.href = "/compute/login";
      throw new Error("Authentication required");
    }
    return response;
  }

  function logout() {
    return authFetch("/compute/api/auth/logout", { method: "POST" })
      .catch(function () { /* local logout still applies during network failure */ })
      .finally(function () {
        clearToken();
        window.location.replace("/compute/login");
      });
  }

  // A page restored from the browser's back/forward cache does not make a new
  // request to Flask.  Revalidate it before exposing the cached dashboard.
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    fetch("/compute/api/auth/token", {
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Accept": "application/json" }
    }).then(function (response) {
      if (response.ok) return;
      clearToken();
      window.location.replace("/compute/login");
    }).catch(function () {
      clearToken();
      window.location.replace("/compute/login");
    });
  });

  window.REvoDesignAuth = {
    getToken: getToken,
    setToken: setToken,
    clearToken: clearToken,
    authFetch: authFetch,
    logout: logout,
    TOKEN_KEY: TOKEN_KEY
  };
})();

function escapeHtml(str) {
  if (!str && str !== 0) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
