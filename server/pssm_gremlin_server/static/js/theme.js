/* REvoDesign GREMLIN Server — Theme detection and cycling */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var STORAGE_KEY = "revodesign-theme";
  var MODE_ICONS = { light: "☀", dark: "☾", auto: "◐" };

  function getStoredThemeMode() {
    try {
      var storedTheme = window.localStorage.getItem(STORAGE_KEY);
      if (storedTheme === "light" || storedTheme === "dark") {
        return storedTheme;
      }
    } catch (e) { /* ignore */ }
    return "auto";
  }

  function resolveThemeMode(mode) {
    if (mode === "light" || mode === "dark") return mode;
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }
    return "light";
  }

  function applyTheme(mode) {
    var resolved = resolveThemeMode(mode);
    document.documentElement.dataset.themeMode = mode;
    document.documentElement.dataset.theme = resolved;
  }

  // Initial detection – fire before paint
  applyTheme(getStoredThemeMode());

  // Expose for page-level toggle buttons
  window.REvoDesignTheme = {
    getStoredThemeMode: getStoredThemeMode,
    applyTheme: applyTheme,
    MODE_ICONS: MODE_ICONS,
    STORAGE_KEY: STORAGE_KEY,
    cycle: function (button) {
      var current = getStoredThemeMode();
      var next = current === "auto" ? "light" : current === "light" ? "dark" : "auto";
      try { window.localStorage.setItem(STORAGE_KEY, next); } catch (e) {}
      applyTheme(next);
      if (button) {
        button.classList.remove("mode-auto", "mode-light", "mode-dark");
        button.classList.add("mode-" + next);
        button.setAttribute("aria-pressed", next === "auto" ? "mixed" : "true");
        var icon = button.querySelector(".theme-icon");
        if (icon) {
          icon.textContent = MODE_ICONS[next];
          button.classList.add("is-animating");
          icon.addEventListener("animationend", function handler() {
            button.classList.remove("is-animating");
            icon.removeEventListener("animationend", handler);
          }, { once: true });
        }
      }
    },
    initToggle: function (button) {
      if (!button) return;
      var mode = getStoredThemeMode();
      button.classList.add("mode-" + mode);
      button.setAttribute("aria-pressed", mode === "auto" ? "mixed" : "true");
      var icon = button.querySelector(".theme-icon");
      if (icon) icon.textContent = MODE_ICONS[mode];
      var self = this;
      button.addEventListener("click", function () { self.cycle(button); });
    }
  };
})();
