/* REvoDesign GREMLIN Server — Auth token helpers */
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
        var res = await fetch("/PSSM_GREMLIN/api/auth/token", { credentials: "same-origin" });
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
      window.location.href = "/PSSM_GREMLIN/login";
      throw new Error("Authentication required");
    }
    return response;
  }

  window.REvoDesignAuth = {
    getToken: getToken,
    setToken: setToken,
    clearToken: clearToken,
    authFetch: authFetch,
    TOKEN_KEY: TOKEN_KEY
  };
})();
