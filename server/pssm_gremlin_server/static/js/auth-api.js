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

  async function authFetch(url, options) {
    options = options || {};
    options.headers = options.headers || {};
    // ponytail: send the auth cookie so API calls work even when
    // sessionStorage is unavailable (private browsing, cleared, etc.).
    options.credentials = "same-origin";
    var token = getToken();
    if (token) {
      options.headers["Authorization"] = "Bearer " + token;
    }
    var response = await fetch(url, options);
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
