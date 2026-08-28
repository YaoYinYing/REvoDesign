/* REvoCompute — dedicated manifest-first task result workspace */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  "use strict";
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;
  var task = JSON.parse(document.getElementById("result-task-data").textContent);
  var artifacts = [];
  var activeMolstar = null;
  var previewRegistry = null;
  var previewHost = null;
  var resultViews = [];
  var shortlist = new Map();
  var MAX_SHORTLIST_ITEMS = 200;
  // Warm Mol* viewer: one shell iframe and one plugin instance stay alive
  // across structure previews. The frame lives in a persistent holder that
  // is never reparented (reparenting reloads an iframe), so switching
  // between PDB/mmCIF artifacts reuses the booted viewer instead of
  // re-downloading and re-initializing the bundle on every click.
  var warmMolstar = null;
  var structureHolder = null;
  var warmPending = {};
  var warmListenerInstalled = false;
  // Downloaded structure texts, keyed by artifact path, so switching back to
  // an already-viewed structure skips the network fetch entirely. Bounded:
  // at most 3 files and 60 MB total.
  var structureTextCache = new Map();
  var structureTextCacheBytes = 0;
  var STRUCTURE_CACHE_MAX_FILES = 3;
  var STRUCTURE_CACHE_MAX_BYTES = 60 * 1024 * 1024;
  var MOLSTAR_THEME_COOKIE = "revodesign-molstar-theme";
  // Mol* runs inside the isolated /compute/viewer-shell iframe (its bundle
  // needs new Function, which only that shell's CSP permits). All constants
  // and the asset loader live in viewer-shell.js.;

  function formatBytes(value) {
    var bytes = Number(value || 0);
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KiB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MiB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GiB";
  }

  function showToast(message, type) {
    var node = document.createElement("div");
    node.className = "toast " + (type || "info");
    node.setAttribute("role", type === "error" ? "alert" : "status");
    node.textContent = message;
    document.getElementById("toastWrap").appendChild(node);
    setTimeout(function () { node.remove(); }, 3600);
  }

  // The shell iframe is sandboxed without allow-same-origin, so its origin
  // is opaque ("null") — postMessages must target the frame's own serialized
  // origin, never the parent's.
  function postToShell(frame, payload, transfer) {
    var targetOrigin = "*";
    try { targetOrigin = frame.contentWindow.origin || "*"; } catch (e) { /* frame gone */ }
    frame.contentWindow.postMessage(payload, targetOrigin, transfer || []);
  }

  function readMolstarTheme() {
    var prefix = MOLSTAR_THEME_COOKIE + "=";
    var value = document.cookie.split(";").map(function (part) { return part.trim(); }).find(function (part) {
      return part.startsWith(prefix);
    });
    return value && value.slice(prefix.length) === "dark" ? "dark" : "light";
  }

  function setMolstarTheme(theme) {
    var resolved = theme === "dark" ? "dark" : "light";
    var secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = MOLSTAR_THEME_COOKIE + "=" + resolved + "; Path=/; Max-Age=31536000; SameSite=Lax" + secure;
    var frame = activeMolstar ? activeMolstar.frame : document.querySelector("iframe.artifact-molstar-preview");
    if (frame) postToShell(frame, { type: "theme", theme: resolved });
    document.querySelectorAll(".molstar-theme-toggle").forEach(function (button) {
      button.textContent = resolved === "dark" ? "☾" : "☀";
      button.setAttribute("aria-label", resolved === "dark" ? "Use light Mol* theme" : "Use dark Mol* theme");
      button.title = button.getAttribute("aria-label");
      button.setAttribute("aria-pressed", resolved === "dark" ? "true" : "false");
    });
  }

  function disposeActiveViewer() {
    var frame = warmMolstar ? warmMolstar.frame : null;
    warmMolstar = null;
    if (activeMolstar) activeMolstar = null;
    Object.keys(warmPending).forEach(function (key) {
      var pending = warmPending[key];
      clearTimeout(pending.timer);
      if (pending.reject) { try { pending.reject(new Error("Viewer disposed")); } catch (e) { /* already settled */ } }
      delete warmPending[key];
    });
    if (!frame) return Promise.resolve();
    // Give the shell a moment to run its own teardown (selection unsubscribe
    // + plugin.dispose) before the iframe is detached; the shell acknowledges
    // with a "disposed" message, and a 2s timeout guarantees the frame never
    // lingers when the shell is already gone.
    return new Promise(function (resolve) {
      var removed = false;
      var timer = null;
      var removeFrame = function () {
        if (removed) return;
        removed = true;
        clearTimeout(timer);
        window.removeEventListener("message", onDisposed);
        frame.remove();
        resolve();
      };
      var onDisposed = function (event) {
        if (removed || event.source !== frame.contentWindow || !event.data || event.data.type !== "disposed") return;
        removeFrame();
      };
      timer = setTimeout(removeFrame, 2000);
      window.addEventListener("message", onDisposed);
      try { postToShell(frame, { type: "dispose" }); } catch (e) { removeFrame(); }
    });
  }

  // One shared message listener for the warm shell: resolves the pending
  // handshake for the given requestId, and flushes the first structure
  // message when the shell reports ready.
  function installWarmListener() {
    if (warmListenerInstalled) return;
    warmListenerInstalled = true;
    window.addEventListener("message", function (event) {
      if (!warmMolstar || event.source !== warmMolstar.frame.contentWindow || !event.data) return;
      if (event.data.type === "shell-ready") {
        var ready = warmPending["__shell_ready__"];
        if (ready) { delete warmPending["__shell_ready__"]; clearTimeout(ready.timer); ready.resolve(); }
        return;
      }
      var pending = warmPending[event.data.requestId];
      if (!pending) return;
      delete warmPending[event.data.requestId];
      clearTimeout(pending.timer);
      if (event.data.type === "ready") pending.resolve(warmMolstar.frame);
      else if (event.data.type === "error") pending.reject(new Error(event.data.message));
    });
  }

  function structureFormat(path) {
    var lower = String(path).toLowerCase();
    return lower.endsWith(".cif") || lower.endsWith(".mmcif") ? "mmcif" : "pdb";
  }

  // Single-flight guard: every async render captures the host generation at
  // start and re-checks it after each await. A viewer toggle, artifact
  // switch, or destroy bumps the generation, so a stale Mol*/py2Dmol
  // continuation can never mount or load a file after its surface is gone —
  // the two viewers are never in flight for the same stage simultaneously.
  function isStale(generation) {
    return previewHost && previewHost.generation !== generation;
  }

  async function renderPy2DmolFallback(text, artifact, stage, generation, molstarError) {
    try {
      await window.REvoDesignPy2Dmol.renderAlphaTrace(
        stage,
        text,
        structureFormat(artifact.path),
        artifact.path,
        [Math.max(320, Math.min(stage.clientWidth - 220, 900)), 560],
        function () { return isStale(generation); }
      );
      if (isStale(generation)) return;
    } catch (error) {
      if (isStale(generation)) return;
      throw molstarError;
    }
    var note = document.createElement("p");
    note.className = "preview-message py2dmol-note";
    note.textContent = "Mol* was unavailable; showing the interactive py2Dmol alpha-trace fallback.";
    stage.appendChild(note);
  }

  // ponytail: current viewer choice per artifact — kept simple (no global
  // preference store).  Resets when the user selects a different artifact.
  var structureViewer = "molstar";

  var activeColorMode = "chain";

  function setStructureColor(mode) {
    activeColorMode = mode;
    // Mol* backend — forward the mode into the isolated viewer shell
    if (activeMolstar) {
      try { postToShell(activeMolstar.frame, { type: "color", mode: mode }); } catch (e) { /* frame gone */ }
    }
    // py2Dmol backend — drive the existing color select in its right panel
    var colorSelect = document.querySelector(".py2dmol-fallback #colorSelect");
    if (colorSelect) {
      colorSelect.value = mode;
      colorSelect.dispatchEvent(new Event("change", { bubbles: true }));
    }
    // Highlight active color toggle
    document.querySelectorAll(".color-toggle").forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.mode === mode);
      btn.setAttribute("aria-pressed", btn.dataset.mode === mode ? "true" : "false");
    });
  }

  function structureViewerBar(artifact, rerender) {
    var bar = document.createElement("div");
    bar.className = "structure-viewer-bar";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Structure viewer controls");
    var makeBtn = function (label, viewer) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "viewer-toggle" + (structureViewer === viewer ? " active" : "");
      btn.textContent = label;
      btn.setAttribute("aria-pressed", structureViewer === viewer ? "true" : "false");
      btn.addEventListener("click", function () { structureViewer = viewer; (rerender || previewArtifact)(artifact); });
      return btn;
    };
    bar.append(makeBtn("Mol* (full)", "molstar"), makeBtn("py2Dmol (alpha)", "py2dmol"));
    var colorBar = document.createElement("div");
    colorBar.className = "structure-color-bar";
    colorBar.setAttribute("role", "group");
    colorBar.setAttribute("aria-label", "Structure color theme");
    var colorModes = [{ mode: "chain", label: "Chain" }, { mode: "rainbow", label: "Rainbow" }];
    if (artifact.confidence_encoding === "plddt_bfactor") colorModes.unshift({ mode: "plddt", label: "pLDDT" });
    if (!colorModes.some(function (item) { return item.mode === activeColorMode; })) activeColorMode = "chain";
    colorModes.forEach(function (c) {
      var btn = document.createElement("button");
      btn.type = "button"; btn.className = "color-toggle"; btn.textContent = c.label; btn.dataset.mode = c.mode;
      if (activeColorMode === c.mode) btn.classList.add("active");
      btn.setAttribute("aria-pressed", activeColorMode === c.mode ? "true" : "false");
      btn.addEventListener("click", function () { setStructureColor(c.mode); });
    colorBar.appendChild(btn);
    });
    bar.appendChild(colorBar);
    var themeButton = document.createElement("button");
    themeButton.type = "button";
    themeButton.className = "molstar-theme-toggle";
    themeButton.addEventListener("click", function () {
      setMolstarTheme(readMolstarTheme() === "dark" ? "light" : "dark");
    });
    bar.appendChild(themeButton);
    setTimeout(function () { setMolstarTheme(readMolstarTheme()); }, 0);
    return bar;
  }

  function viewerAbortError() {
    var error = new Error("Viewer render cancelled");
    error.name = "AbortError";
    return error;
  }

  async function renderMolstar(structureText, artifact, stage, generation, fresh, signal) {
    if (signal && signal.aborted) throw viewerAbortError();
    var requestId = "mol-" + Math.random().toString(36).slice(2);
    var message = {
      type: "structure",
      text: structureText,
      format: structureFormat(artifact.path),
      label: artifact.path,
      requestId: requestId,
      theme: readMolstarTheme(),
      colorMode: activeColorMode
    };
    if (!fresh && warmMolstar) {
      // Warm path: the shell is already booted; post the new structure and
      // await the ready report for this requestId. No iframe work at all.
      await new Promise(function (resolve, reject) {
        var settled = false;
        var removeAbort = function () {};
        function finish(error, frame) {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          delete warmPending[requestId];
          removeAbort();
          if (error) reject(error); else resolve(frame);
        }
        var timer = setTimeout(function () { finish(new Error("Mol* timed out")); }, 45000);
        warmPending[requestId] = {
          resolve: function (frame) { finish(null, frame); }, reject: finish, timer: timer
        };
        if (signal) {
          var onAbort = function () { finish(viewerAbortError()); disposeActiveViewer(); };
          signal.addEventListener("abort", onAbort, { once: true });
          removeAbort = function () { signal.removeEventListener("abort", onAbort); };
        }
        try { postToShell(warmMolstar.frame, message); } catch (error) { finish(error); }
      });
      if (isStale(generation)) return warmMolstar.frame;
      activeMolstar = warmMolstar;
      return warmMolstar.frame;
    }
    if (fresh) {
      // Cold path for the linked table/structure view: a dedicated frame in
      // the caller's stage with its own one-shot handshake.
      var frame = document.createElement("iframe");
      frame.className = "artifact-molstar-preview";
      frame.sandbox = "allow-scripts";
      frame.title = "Mol* structure viewer";
      var handshake = new Promise(function (resolve, reject) {
        var settled = false;
        function finish(error) {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          window.removeEventListener("message", onMessage);
          if (signal) signal.removeEventListener("abort", onAbort);
          if (error) reject(error); else resolve(frame);
        }
        var timer = setTimeout(function () { finish(new Error("Mol* timed out")); }, 45000);
        function onAbort() { frame.remove(); finish(viewerAbortError()); }
        function onMessage(event) {
          if ((event.origin !== location.origin && event.origin !== "null") || event.source !== frame.contentWindow || !event.data) return;
          if (event.data.type === "shell-ready") postToShell(frame, message);
          else if (event.data.type === "ready" && event.data.requestId === requestId) {
            finish();
          } else if (event.data.type === "error" && event.data.requestId === requestId) {
            finish(new Error(event.data.message));
          }
        }
        window.addEventListener("message", onMessage);
        if (signal) signal.addEventListener("abort", onAbort, { once: true });
      });
      stage.appendChild(frame);
      frame.src = "/compute/viewer-shell";
      if (isStale(generation)) { frame.remove(); return; }
      await handshake;
      if (isStale(generation)) { frame.remove(); return; }
      return frame;
    }
    // First warm mount: one frame in the persistent holder, never reparented.
    var warmFrame = document.createElement("iframe");
    warmFrame.className = "artifact-molstar-preview";
    warmFrame.sandbox = "allow-scripts";
    warmFrame.title = "Mol* structure viewer";
    warmMolstar = { frame: warmFrame };
    installWarmListener();
    structureHolder.replaceChildren();
    structureHolder.appendChild(warmFrame);
    warmFrame.src = "/compute/viewer-shell";
    await new Promise(function (resolve, reject) {
      var settled = false;
      var removeAbort = function () {};
      function finish(error, frame) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        delete warmPending["__shell_ready__"];
        delete warmPending[requestId];
        removeAbort();
        if (error) reject(error); else resolve(frame);
      }
      var timer = setTimeout(function () { finish(new Error("Mol* timed out")); }, 45000);
      warmPending["__shell_ready__"] = {
        resolve: function () {
          try { postToShell(warmFrame, message); } catch (error) { finish(error); return; }
          timer = setTimeout(function () { finish(new Error("Mol* timed out")); }, 45000);
          warmPending[requestId] = {
            resolve: function (frame) { finish(null, frame); }, reject: finish, timer: timer
          };
        },
        reject: finish,
        timer: timer
      };
      if (signal) {
        var onAbort = function () { finish(viewerAbortError()); disposeActiveViewer(); };
        signal.addEventListener("abort", onAbort, { once: true });
        removeAbort = function () { signal.removeEventListener("abort", onAbort); };
      }
    });
    if (isStale(generation)) return warmFrame;
    activeMolstar = warmMolstar;
    return warmFrame;
  }

  // The warm Mol* iframe lives inside the holder and must survive surface
  // clears: clearing it detaches the frame, whose contentWindow then reads
  // null on the next postMessage ("Cannot read properties of null").
  function clearSurfacePreservingWarm(surface) {
    if (!warmMolstar || warmMolstar.frame.parentNode !== surface) {
      surface.replaceChildren();
      return;
    }
    Array.from(surface.children).forEach(function (child) {
      if (child !== warmMolstar.frame) child.remove();
    });
  }

  function showLoading(surface, label) {
    var box = document.createElement("div");
    box.className = "preview-loading";
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    var bars = document.createElement("div");
    bars.className = "preview-loading-bars";
    for (var index = 0; index < 3; index += 1) bars.appendChild(document.createElement("span"));
    var text = document.createElement("p");
    text.className = "preview-loading-label";
    text.textContent = label || "Loading preview…";
    box.append(bars, text);
    if (warmMolstar && warmMolstar.frame.parentNode === surface) surface.insertBefore(box, warmMolstar.frame);
    else surface.appendChild(box);
    return box;
  }

  async function structureText(artifact, generation, signal) {
    var cached = structureTextCache.get(artifact.path);
    if (cached) return cached;
    var response = await A.authFetch(artifact.url, signal ? { signal: signal } : undefined);
    if (isStale(generation)) return null;
    if (!response.ok) throw new Error("Structure download failed (HTTP " + response.status + ")");
    var text = await response.text();
    if (isStale(generation)) return null;
    structureTextCache.set(artifact.path, text);
    structureTextCacheBytes += text.length;
    while (structureTextCache.size > STRUCTURE_CACHE_MAX_FILES || structureTextCacheBytes > STRUCTURE_CACHE_MAX_BYTES) {
      var oldest = structureTextCache.keys().next().value;
      structureTextCacheBytes -= structureTextCache.get(oldest).length;
      structureTextCache.delete(oldest);
    }
    return text;
  }

  async function previewStructure(artifact, stage, signal) {
    var generation = previewHost.generation;
    var cached = structureTextCache.has(artifact.path);
    var text = await structureText(artifact, generation, signal);
    if (!text) return;
    var surface = structureHolder || stage;
    clearSurfacePreservingWarm(surface);
    var bar = structureViewerBar(artifact);
    // Keep the toolbar above the preserved warm iframe (appending would push
    // the controls below the 34–48rem-tall canvas).
    if (warmMolstar && warmMolstar.frame.parentNode === surface) surface.insertBefore(bar, warmMolstar.frame);
    else surface.appendChild(bar);

    if (structureViewer === "py2dmol") {
      stage.hidden = false;
      if (structureHolder) structureHolder.hidden = true;
      stage.replaceChildren();
      stage.appendChild(structureViewerBar(artifact));
      try {
        await renderPy2DmolFallback(text, artifact, stage, generation, new Error("User selected alpha-trace viewer"));
        if (isStale(generation)) return;
        setTimeout(function () { if (!isStale(generation)) setStructureColor(activeColorMode); }, 100);
      }
      catch (e) {
        if (isStale(generation)) return;
        var unavailableMsg = document.createElement("p");
        unavailableMsg.className = "preview-message";
        unavailableMsg.textContent = "py2Dmol unavailable. Download the structure file to inspect it locally.";
        stage.appendChild(unavailableMsg);
      }
      return;
    }

    // Cached swaps resolve almost instantly; a loading box would only flash.
    var loading = cached ? null : showLoading(surface, "Loading structure…");
    try {
      await renderMolstar(text, artifact, surface, generation, false, signal);
      if (loading) loading.remove();
    }
    catch (error) {
      if (loading) loading.remove();
      if (isStale(generation)) return;
      // A dead warm frame must not poison the next pick: dispose it so the
      // retry cold-starts a fresh shell.
      await disposeActiveViewer();
      if (isStale(generation)) return;
      surface.replaceChildren();
      surface.appendChild(structureViewerBar(artifact));
      var msg = document.createElement("p");
      msg.className = "preview-message";
      msg.textContent = "Mol* could not be loaded: " + (error.message || error);
      var br = document.createElement("br");
      var retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn btn-soft btn-small";
      retry.textContent = "Open with py2Dmol (alpha-trace)";
      retry.type = "button";
      retry.addEventListener("click", function () { structureViewer = "py2dmol"; previewArtifact(artifact); });
      msg.append(br, retry);
      surface.appendChild(msg);
      console.warn("Mol* error:", error);
    }
  }

  function renderTable(page, stage) {
    var rows = [page.columns].concat(page.rows || []);
    if (!page.columns || !page.columns.length) { stage.innerHTML = '<p class="preview-message">This table is empty.</p>'; return; }
    var wrap = document.createElement("div");
    wrap.className = "artifact-table-wrap";
    var table = document.createElement("table");
    table.className = "artifact-table-preview";
    rows.forEach(function (row, rowIndex) {
      var tr = document.createElement("tr");
      row.forEach(function (value) {
        var cell = document.createElement(rowIndex === 0 ? "th" : "td");
        cell.textContent = value;
        tr.appendChild(cell);
      });
      table.appendChild(tr);
    });
    wrap.appendChild(table);
    stage.appendChild(wrap);
  }

  async function previewImage(artifact, stage, services) {
    var response = await A.authFetch(artifact.url, { signal: services.signal });
    if (!response.ok) throw new Error("Image download failed");
    var objectUrl = URL.createObjectURL(await response.blob());
    var image = document.createElement("img");
    image.className = "artifact-image-preview";
    image.alt = artifact.path;
    image.src = objectUrl;
    image.addEventListener("load", function () { URL.revokeObjectURL(objectUrl); }, { once: true });
    image.addEventListener("error", function () { URL.revokeObjectURL(objectUrl); }, { once: true });
    stage.appendChild(image);
  }

  function isMsaFile(path) {
    var ext = String(path || "").toLowerCase();
    return /\.(a3m|aln|fa|faa|fasta|sto)$/.test(ext);
  }

  // Zappo/Clustal residue color scheme
  var RESIDUE_COLORS = {
    A: "#80a0f0", I: "#80a0f0", L: "#80a0f0", M: "#80a0f0", F: "#80a0f0", W: "#80a0f0", V: "#80a0f0", // hydrophobic
    K: "#f01505", R: "#f01505",                                                                         // positive
    D: "#c048c0", E: "#c048c0",                                                                         // negative
    N: "#15c015", Q: "#15c015", S: "#15c015", T: "#15c015",                                             // polar
    C: "#f08080",                                                                                       // cysteine
    G: "#f09048",                                                                                       // glycine
    P: "#c0c000",                                                                                       // proline
    H: "#15a4a4", Y: "#15a4a4",                                                                         // aromatic
    "-": "#c0c0c0", ".": "#c0c0c0"                                                                      // gap
  };

  function renderMsa(text, stage) {
    var wrapper = document.createElement("div");
    wrapper.className = "msa-viewer";
    var lines = String(text).split(/\r?\n/);
    var block = document.createElement("div");
    block.className = "msa-block";
    var lineCount = 0;
    lines.forEach(function (line) {
      if (lineCount >= 5000) return;
      var trimmed = line.trimEnd();
      if (trimmed.startsWith(">") || trimmed.startsWith("#")) {
        var headerSpan = document.createElement("span");
        headerSpan.className = "msa-header";
        headerSpan.textContent = trimmed;
        block.appendChild(headerSpan);
      } else if (trimmed) {
        var seqSpan = document.createElement("span");
        seqSpan.className = "msa-sequence";
        for (var i = 0; i < trimmed.length; i++) {
          var char = trimmed[i].toUpperCase();
          var span = document.createElement("span");
          span.textContent = trimmed[i];
          span.style.color = RESIDUE_COLORS[char] || "inherit";
          seqSpan.appendChild(span);
        }
        block.appendChild(seqSpan);
      } else {
        block.appendChild(document.createElement("br"));
      }
      lineCount += 1;
    });
    if (lines.length > 5000) block.appendChild(document.createTextNode("\n\n[Preview truncated at 5000 lines]"));
    wrapper.appendChild(block);
    stage.appendChild(wrapper);
  }

  async function previewText(artifact, stage, services) {
    var response = await A.authFetch(artifact.url, { headers: { Range: "bytes=0-262143" }, signal: services.signal });
    if (!response.ok && response.status !== 206) throw new Error("Text preview download failed");
    var text = await response.text();
    if (isMsaFile(artifact.path)) {
      renderMsa(text, stage);
      return;
    }
    var pre = document.createElement("pre");
    pre.textContent = text + (artifact.size > 262144 ? "\n\n[Preview truncated at 256 KiB]" : "");
    stage.appendChild(pre);
  }

  async function previewTable(artifact, stage, services) {
    var encoded = artifact.path.split("/").map(encodeURIComponent).join("/");
    var response = await A.authFetch("/compute/api/results/" + encodeURIComponent(task.md5) + "/tables/" + encoded + "?limit=100", { signal: services.signal });
    if (!response.ok) throw new Error("Table preview download failed");
    var page = await response.json();
    renderTable(page, stage);
    if (page.has_more) {
      var note = document.createElement("p");
      note.className = "preview-message";
      note.textContent = "Showing the first 100 rows. Download the file for the complete table.";
      stage.appendChild(note);
    }
  }

  function artifactFor(path) {
    return artifacts.find(function (artifact) { return artifact.path === path; }) || null;
  }

  function artifactPaths(view, source) {
    return (view.sources && Array.isArray(view.sources[source]) ? view.sources[source] : [])
      .map(artifactFor).filter(Boolean);
  }

  function exceedsPreviewLimit(artifact, plugin, stage) {
    if (!plugin || !plugin.maxBytes || Number(artifact.size || 0) <= plugin.maxBytes) return false;
    var message = document.createElement("p"); message.className = "preview-message";
    message.textContent = "This file exceeds the safe inline preview limit. Download it instead.";
    stage.appendChild(message); return true;
  }

  function valueAtPath(value, path) {
    String(path || "").split(".").filter(Boolean).forEach(function (part) {
      if (value == null || !(part in value)) throw new Error("The declared data field is unavailable.");
      value = value[part];
    });
    return value;
  }

  async function loadJson(artifact, signal) {
    if (Number(artifact.size || 0) > 8 * 1024 * 1024) throw new Error("This scientific data file exceeds the 8 MiB preview limit.");
    var response = await A.authFetch(artifact.url, { headers: { Range: "bytes=0-8388607" }, signal: signal });
    if (!response.ok && response.status !== 206) throw new Error("Scientific data could not be loaded.");
    return response.json();
  }

  async function loadCsv(artifact, signal) {
    var rows = [], columns = null, offset = 0;
    do {
      var response = await A.authFetch(tableUrl(artifact.path, offset).replace("limit=100", "limit=500"), { signal: signal });
      if (!response.ok) throw new Error("Scientific table could not be loaded.");
      var page = await response.json();
      columns = columns || page.columns;
      rows = rows.concat(page.rows || []);
      offset += page.rows.length;
      if (!page.has_more) break;
    } while (rows.length < 10000);
    return { columns: columns || [], rows: rows, truncated: rows.length >= 10000 };
  }

  function directionLabel(direction) {
    return { higher: "Higher is favourable", lower: "Lower is favourable", neutral: "No ranking direction" }[direction] || "";
  }

  async function renderAlignment(view, stage, services) {
    var source = artifactPaths(view, "alignment")[0];
    if (!source) throw new Error("The configured alignment is unavailable.");
    var response = await A.authFetch(source.url, { headers: { Range: "bytes=0-262143" }, signal: services.signal });
    if (!response.ok && response.status !== 206) throw new Error("Alignment download failed.");
    var note = document.createElement("p"); note.className = "scientific-note";
    note.textContent = "Columns use " + view.mapping.numbering + " numbering. Preview is bounded to 256 KiB and 5,000 lines.";
    stage.appendChild(note); renderMsa(await response.text(), stage);
  }

  function scientificPicker(items, label, open) {
    var bar = document.createElement("div"); bar.className = "scientific-toolbar";
    var caption = document.createElement("label"); caption.textContent = label + " ";
    var select = document.createElement("select"); select.setAttribute("aria-label", label);
    items.forEach(function (artifact, index) {
      var option = document.createElement("option"); option.value = String(index); option.textContent = artifact.path; select.appendChild(option);
    });
    select.addEventListener("change", function () { open(items[Number(select.value)]).catch(showPreviewError); });
    caption.appendChild(select); bar.appendChild(caption); return bar;
  }

  async function renderMetricSeries(view, stage, services) {
    var sources = artifactPaths(view, "series");
    if (!sources.length) throw new Error("The configured metric series is unavailable.");
    var chart = document.createElement("div"); chart.className = "metric-chart";
    var generation = 0;
    async function open(artifact) {
      var current = ++generation, mapping = view.mapping, series = [], xValues = [];
      if (mapping.format === "json") {
        var values = valueAtPath(await loadJson(artifact, services.signal), mapping.value_path);
        series = [{ name: mapping.y_label || "Value", values: values.map(Number) }];
        xValues = values.map(function (_value, index) { return index + 1; });
      } else {
        var page = await loadCsv(artifact, services.signal);
        var indexes = {}; page.columns.forEach(function (column, index) { indexes[column] = index; });
        xValues = page.rows.map(function (row, index) { return Number(row[indexes[mapping.x_column]]) || index + 1; });
        series = mapping.value_columns.map(function (column) {
          return { name: column, values: page.rows.map(function (row) { return Number(row[indexes[column]]); }) };
        });
      }
      if (current !== generation || services.signal.aborted) return;
      var points = series.flatMap(function (item) { return item.values.filter(Number.isFinite); });
      if (!points.length) throw new Error("The metric series contains no numeric values.");
      var yMin = mapping.y_min == null ? Math.min.apply(null, points) : Number(mapping.y_min);
      var yMax = mapping.y_max == null ? Math.max.apply(null, points) : Number(mapping.y_max);
      if (yMin === yMax) yMax = yMin + 1;
      var width = 760, height = 360, pad = 48;
      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 " + width + " " + height); svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", (mapping.y_label || "Metric") + " by " + (mapping.x_label || "index"));
      var colors = ["#087f8c", "#c44536", "#6a4c93", "#2f7d32", "#b26a00"];
      series.forEach(function (item, seriesIndex) {
        var path = document.createElementNS(svg.namespaceURI, "path");
        var drawing = false;
        var commands = item.values.map(function (value, index) {
          if (!Number.isFinite(value)) { drawing = false; return null; }
          var x = pad + (width - 2 * pad) * (index / Math.max(item.values.length - 1, 1));
          var y = height - pad - (height - 2 * pad) * ((value - yMin) / (yMax - yMin));
          var command = drawing ? "L" : "M"; drawing = true;
          return command + x.toFixed(1) + " " + y.toFixed(1);
        }).filter(Boolean).join(" ");
        path.setAttribute("d", commands); path.setAttribute("fill", "none");
        path.setAttribute("stroke", colors[seriesIndex % colors.length]); path.setAttribute("stroke-width", "2"); svg.appendChild(path);
      });
      var summary = document.createElement("p"); summary.className = "scientific-note";
      summary.textContent = (mapping.x_label || "Index") + ": " + xValues.length + " points · " +
        (mapping.y_label || "Value") + ": " + yMin.toFixed(3) + "–" + yMax.toFixed(3) +
        (mapping.unit ? " " + mapping.unit : "") + " · " + directionLabel(mapping.direction);
      chart.replaceChildren(svg, summary);
    }
    if (sources.length > 1) stage.appendChild(scientificPicker(sources, "Metric source", open));
    stage.appendChild(chart); await open(sources[0]);
  }

  async function renderMatrix(view, stage, services) {
    var sources = artifactPaths(view, "matrices");
    if (!sources.length) throw new Error("The configured matrix is unavailable.");
    var region = document.createElement("div"); region.className = "matrix-view";
    var generation = 0;
    async function open(artifact) {
      var current = ++generation, mapping = view.mapping, values, xLabels, yLabels;
      if (mapping.format === "json") {
        values = valueAtPath(await loadJson(artifact, services.signal), mapping.value_path);
        xLabels = (values[0] || []).map(function (_value, index) { return String(index + 1); });
        yLabels = values.map(function (_value, index) { return String(index + 1); });
      } else {
        var page = await loadCsv(artifact, services.signal); var labelIndex = page.columns.indexOf(mapping.row_labels_column);
        xLabels = page.columns.filter(function (_column, index) { return index !== labelIndex; });
        yLabels = page.rows.map(function (row) { return row[labelIndex]; });
        values = page.rows.map(function (row) { return row.filter(function (_value, index) { return index !== labelIndex; }).map(Number); });
      }
      if (current !== generation || services.signal.aborted) return;
      if (!Array.isArray(values) || !values.length || !Array.isArray(values[0])) throw new Error("The matrix is empty.");
      var numeric = values.flat().map(Number).filter(Number.isFinite);
      var minimum = mapping.scale_min == null ? Math.min.apply(null, numeric) : Number(mapping.scale_min);
      var maximum = mapping.scale_max == null ? Math.max.apply(null, numeric) : Number(mapping.scale_max);
      var center = mapping.center == null ? 0 : Number(mapping.center);
      var canvas = document.createElement("canvas"); canvas.width = 720; canvas.height = 540; canvas.tabIndex = 0;
      canvas.setAttribute("role", "grid"); canvas.setAttribute("aria-label", view.title + "; use arrow keys to inspect cells");
      var context = canvas.getContext("2d"), rows = values.length, columns = values[0].length;
      function color(value) {
        var ratio;
        if (mapping.scale === "diverging") {
          ratio = value <= center ? 0.5 * (value - minimum) / Math.max(center - minimum, 1e-12) :
            0.5 + 0.5 * (value - center) / Math.max(maximum - center, 1e-12);
          return "hsl(" + (220 - 220 * Math.max(0, Math.min(1, ratio))) + " 68% " + (42 + 38 * (1 - Math.abs(ratio - 0.5) * 2)) + "%)";
        }
        ratio = (value - minimum) / Math.max(maximum - minimum, 1e-12);
        return "hsl(" + (205 - 165 * ratio) + " 68% " + (94 - 54 * ratio) + "%)";
      }
      values.forEach(function (row, y) { row.forEach(function (raw, x) {
        context.fillStyle = Number.isFinite(Number(raw)) ? color(Number(raw)) : "#777";
        context.fillRect(x * canvas.width / columns, y * canvas.height / rows, canvas.width / columns + 0.5, canvas.height / rows + 0.5);
      }); });
      var readout = document.createElement("p"); readout.className = "matrix-readout"; readout.setAttribute("role", "status");
      var selected = { x: 0, y: 0 };
      function report() {
        readout.textContent = (mapping.x_label || "Column") + " " + xLabels[selected.x] + " · " +
          (mapping.y_label || "Row") + " " + yLabels[selected.y] + " · value " + values[selected.y][selected.x] +
          (mapping.unit ? " " + mapping.unit : "");
      }
      canvas.addEventListener("click", function (event) {
        var box = canvas.getBoundingClientRect();
        selected.x = Math.min(columns - 1, Math.max(0, Math.floor((event.clientX - box.left) / box.width * columns)));
        selected.y = Math.min(rows - 1, Math.max(0, Math.floor((event.clientY - box.top) / box.height * rows))); report();
      });
      canvas.addEventListener("keydown", function (event) {
        var moves = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
        if (!moves[event.key]) return; event.preventDefault();
        selected.x = Math.min(columns - 1, Math.max(0, selected.x + moves[event.key][0]));
        selected.y = Math.min(rows - 1, Math.max(0, selected.y + moves[event.key][1])); report();
      });
      var legend = document.createElement("p"); legend.className = "scientific-note";
      legend.textContent = "Scale " + minimum + " to " + maximum + (mapping.unit ? " " + mapping.unit : "") +
        " · " + directionLabel(mapping.direction) + " · grey marks missing values.";
      report(); region.replaceChildren(canvas, readout, legend);
    }
    if (sources.length > 1) stage.appendChild(scientificPicker(sources, "Matrix source", open));
    stage.appendChild(region); await open(sources[0]);
  }

  async function renderScalarSummary(view, stage, services) {
    var artifacts = artifactPaths(view, "data");
    if (!artifacts.length) throw new Error("The configured summary data is unavailable.");
    var list = document.createElement("dl"); list.className = "scalar-grid";
    async function open(artifact) {
      var payload = await loadJson(artifact, services.signal); list.replaceChildren();
      view.mapping.fields.forEach(function (field) {
        var term = document.createElement("dt"); term.textContent = field.label;
        var value = document.createElement("dd"); value.textContent = String(valueAtPath(payload, field.path)) +
          (field.unit ? " " + field.unit : "");
        var meaning = document.createElement("span"); meaning.textContent = directionLabel(field.direction); value.appendChild(meaning);
        list.append(term, value);
      });
    }
    if (artifacts.length > 1) stage.appendChild(scientificPicker(artifacts, "Summary source", open));
    stage.appendChild(list); await open(artifacts[0]);
  }

  async function renderTrajectory(view, stage, services) {
    var topologies = artifactPaths(view, "topology"), coordinatesList = artifactPaths(view, "coordinates");
    var coordinates = coordinatesList[0];
    if (!coordinates) {
      var empty = document.createElement("p"); empty.className = "preview-message";
      empty.textContent = "No trajectory coordinates were produced for this run. Declared artifacts remain downloadable below.";
      stage.appendChild(empty); return;
    }
    var coordinateName = coordinates && coordinates.path.split("/").pop();
    var topology = view.mapping.association === "stem-prefix" ? topologies.find(function (artifact) {
      return coordinateName.startsWith(artifact.path.split("/").pop().replace(/\.[^.]+$/, "") + "_");
    }) : topologies[0];
    if (!topology || !coordinates) throw new Error("The declared topology and coordinates are required.");
    if (Number(topology.size) + Number(coordinates.size) > 64 * 1024 * 1024) {
      throw new Error("This trajectory exceeds the 64 MiB inline limit. Download it instead.");
    }
    var topologyResponse = await A.authFetch(topology.url, { signal: services.signal });
    var coordinatesResponse = await A.authFetch(coordinates.url, { signal: services.signal });
    if (!topologyResponse.ok || !coordinatesResponse.ok) throw new Error("Trajectory data could not be loaded.");
    var topologyText = await topologyResponse.text();
    var format = view.mapping.coordinate_format;
    var coordinateData = format === "pdb" ? await coordinatesResponse.text() : await coordinatesResponse.arrayBuffer();
    if (services.signal.aborted) return;
    var controls = document.createElement("div"); controls.className = "trajectory-controls";
    var previous = document.createElement("button"); previous.type = "button"; previous.textContent = "Previous";
    var play = document.createElement("button"); play.type = "button"; play.textContent = "Play"; play.setAttribute("aria-pressed", "false");
    var next = document.createElement("button"); next.type = "button"; next.textContent = "Next";
    var scrub = document.createElement("input"); scrub.type = "range"; scrub.min = "0"; scrub.max = "0"; scrub.value = "0";
    scrub.setAttribute("aria-label", "Trajectory frame");
    var speed = document.createElement("select"); speed.setAttribute("aria-label", "Playback speed");
    [0.5, 1, 2].forEach(function (value) { var option = document.createElement("option"); option.value = value; option.textContent = value + "×"; if (value === 1) option.selected = true; speed.appendChild(option); });
    var readout = document.createElement("span"); readout.setAttribute("role", "status"); readout.textContent = "Loading frames…";
    controls.append(previous, play, next, scrub, speed, readout);
    if (coordinatesList.length > 1) {
      var bounded = document.createElement("p"); bounded.className = "scientific-note";
      bounded.textContent = "Showing the first declared trajectory; " + (coordinatesList.length - 1) + " additional coordinate files remain downloadable below.";
      stage.appendChild(bounded);
    }
    var frame = document.createElement("iframe"); frame.className = "artifact-molstar-preview"; frame.sandbox = "allow-scripts";
    frame.title = "Mol* trajectory viewer"; stage.append(controls, frame);
    var timer = null, frameCount = 1, current = 0, settled = false, onMessage = null, abortHandler = null;
    function showFrame(index) {
      current = Math.min(frameCount - 1, Math.max(0, Number(index) || 0)); scrub.value = String(current);
      readout.textContent = (current + 1) + " / " + frameCount + " · " +
        (current * Number(view.mapping.timestep)) + " " + view.mapping.frame_unit;
    }
    function command(action, value) { postToShell(frame, { type: "trajectory-control", action: action, value: value }); }
    function stop() { clearInterval(timer); timer = null; play.textContent = "Play"; play.setAttribute("aria-pressed", "false"); }
    function start() {
      stop(); play.textContent = "Pause"; play.setAttribute("aria-pressed", "true");
      timer = setInterval(function () { command("advance", 1); }, 1000 / Number(speed.value));
    }
    previous.addEventListener("click", function () { command("advance", -1); }); next.addEventListener("click", function () { command("advance", 1); });
    scrub.addEventListener("input", function () { command("set", Number(scrub.value)); });
    play.addEventListener("click", function () { if (timer) stop(); else start(); }); speed.addEventListener("change", function () { if (timer) start(); });
    var ready = new Promise(function (resolve, reject) {
      var timeout = setTimeout(function () {
        window.removeEventListener("message", onMessage); reject(new Error("Trajectory viewer timed out"));
      }, 45000);
      onMessage = function (event) {
        if (event.source !== frame.contentWindow || !event.data) return;
        if (event.data.type === "shell-ready") {
          var payload = {
            type: "trajectory", requestId: "trajectory", topology: topologyText,
            coordinateFormat: format, label: coordinates.path, theme: readMolstarTheme()
          };
          if (format === "pdb") payload.coordinates = coordinateData;
          else payload.coordinateBytes = new Uint8Array(coordinateData);
          postToShell(frame, payload, format === "pdb" ? [] : [coordinateData]);
        } else if (event.data.type === "trajectory-ready") {
          settled = true; clearTimeout(timeout); frameCount = Math.max(1, Number(event.data.frameCount) || 1); scrub.max = String(frameCount - 1); showFrame(0); resolve();
        } else if (event.data.type === "trajectory-frame") showFrame(event.data.frame);
        else if (event.data.type === "error" && !settled) {
          clearTimeout(timeout); window.removeEventListener("message", onMessage); reject(new Error(event.data.message));
        }
      };
      window.addEventListener("message", onMessage);
      abortHandler = function () { clearTimeout(timeout); stop(); window.removeEventListener("message", onMessage); frame.remove(); };
      services.signal.addEventListener("abort", abortHandler, { once: true });
    });
    frame.src = "/compute/viewer-shell"; await ready;
    return { destroy: function () {
      stop(); window.removeEventListener("message", onMessage);
      services.signal.removeEventListener("abort", abortHandler); frame.remove();
    } };
  }

  function shortlistKey(viewId, entityId) { return viewId + ":" + entityId; }

  function setShortlisted(item, selected) {
    var key = shortlistKey(item.view_id, item.id);
    if (selected && !shortlist.has(key) && shortlist.size >= MAX_SHORTLIST_ITEMS) {
      showToast("The shortlist is limited to 200 selections.", "error");
      return false;
    }
    if (selected) shortlist.set(key, item); else shortlist.delete(key);
    renderShortlist();
    return selected;
  }

  function renderShortlist() {
    var list = document.getElementById("shortlistItems");
    var count = document.getElementById("shortlistCount");
    list.replaceChildren(); count.textContent = shortlist.size + " selected";
    if (!shortlist.size) {
      var empty = document.createElement("p"); empty.className = "muted";
      empty.textContent = "Select candidates or table rows to build a review set."; list.appendChild(empty);
    }
    shortlist.forEach(function (item) {
      var row = document.createElement("div"); row.className = "shortlist-item";
      var label = document.createElement("span"); label.textContent = item.label;
      var remove = document.createElement("button"); remove.type = "button"; remove.className = "btn btn-soft btn-small";
      remove.textContent = "Remove"; remove.addEventListener("click", function () { setShortlisted(item, false); });
      row.append(label, remove); list.appendChild(row);
    });
    document.getElementById("exportShortlist").disabled = !shortlist.size;
  }

  function exportShortlist() {
    if (!shortlist.size) return;
    var payload = {
      schema_version: 1,
      source_task: { id: task.md5, task_type: task.task_type, manifest_schema: 3 },
      selected: Array.from(shortlist.values())
    };
    var exportUrl = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" }));
    var link = document.createElement("a"); link.href = exportUrl; link.download = "shortlist.json"; link.click();
    setTimeout(function () { URL.revokeObjectURL(exportUrl); }, 0);
  }

  function candidateItem(view, artifact) {
    return {
      view_id: view.id, entity: "candidate", id: artifact.path, label: artifact.path,
      values: {}, artifacts: [{ path: artifact.path, sha256: artifact.sha256 }]
    };
  }

  async function renderCandidateCollection(view, stage, services) {
    var candidates = artifactPaths(view, "candidates");
    if (!candidates.length) {
      var empty = document.createElement("p"); empty.className = "preview-message";
      empty.textContent = "No candidates passed the configured filters."; stage.appendChild(empty); return;
    }
    var layout = document.createElement("div"); layout.className = "candidate-layout";
    var list = document.createElement("div"); list.className = "candidate-list";
    var preview = document.createElement("div"); preview.className = "candidate-preview";
    var candidateGeneration = 0;
    layout.append(list, preview); stage.appendChild(layout);
    async function openCandidate(artifact) {
      var generation = ++candidateGeneration;
      artifact.confidence_encoding = view.mapping.confidence_encoding || null;
      list.querySelectorAll(".candidate-card").forEach(function (node) {
        node.setAttribute("aria-current", node.dataset.path === artifact.path ? "true" : "false");
      });
      var candidateStage = document.createElement("div");
      preview.replaceChildren(candidateStage);
      try {
        if (artifact.preview === "structure") {
          var structurePlugin = previewRegistry.resolve(artifact);
          if (exceedsPreviewLimit(artifact, structurePlugin, candidateStage)) return;
          var text = await structureText(artifact, previewHost.generation, services.signal);
          if (!text || generation !== candidateGeneration) return;
          var bar = structureViewerBar(artifact, openCandidate); candidateStage.appendChild(bar);
          if (structureViewer === "py2dmol") {
            await renderPy2DmolFallback(text, artifact, candidateStage, previewHost.generation, new Error("User selected alpha-trace viewer"));
            return;
          }
          await renderMolstar(text, artifact, candidateStage, previewHost.generation, true, services.signal);
          return;
        }
        var plugin = previewRegistry.resolve(artifact);
        if (!plugin) {
          var message = document.createElement("p"); message.className = "preview-message";
          message.textContent = "No inline preview is available. Download this candidate instead."; candidateStage.appendChild(message); return;
        }
        var surface = document.createElement("div"); surface.className = "result-plugin-surface"; candidateStage.appendChild(surface);
        await plugin.render(artifact, surface, services);
      } catch (error) {
        if (generation !== candidateGeneration || (error && error.name === "AbortError")) return;
        candidateStage.replaceChildren(); var errorMessage = document.createElement("p"); errorMessage.className = "preview-message";
        errorMessage.textContent = error.message || "Preview unavailable"; candidateStage.appendChild(errorMessage);
      }
    }
    candidates.forEach(function (artifact) {
      var card = document.createElement("div"); card.className = "candidate-card"; card.dataset.path = artifact.path;
      var open = document.createElement("button"); open.type = "button"; open.className = "candidate-open";
      var name = document.createElement("strong"); name.textContent = artifact.path;
      var meta = document.createElement("span"); meta.textContent = formatBytes(artifact.size) + " · sha256 " + artifact.sha256.slice(0, 10);
      open.append(name, meta); open.addEventListener("click", function () { openCandidate(artifact); });
      var item = candidateItem(view, artifact);
      var select = document.createElement("label"); select.className = "candidate-select";
      var checkbox = document.createElement("input"); checkbox.type = "checkbox";
      checkbox.checked = shortlist.has(shortlistKey(item.view_id, item.id));
      checkbox.addEventListener("change", function () { checkbox.checked = setShortlisted(item, checkbox.checked); });
      select.append(checkbox, document.createTextNode(" Shortlist")); card.append(open, select); list.appendChild(card);
    });
    await openCandidate(candidates[0]);
  }

  function tableUrl(path, offset) {
    return "/compute/api/results/" + encodeURIComponent(task.md5) + "/tables/" +
      path.split("/").map(encodeURIComponent).join("/") + "?offset=" + offset + "&limit=100";
  }

  async function renderEntityTable(view, stage, services) {
    var tableArtifacts = artifactPaths(view, "table");
    if (tableArtifacts.length !== 1) throw new Error("The configured result table is unavailable.");
    var tableArtifact = tableArtifacts[0]; var structures = artifactPaths(view, "structure");
    var structureArtifact = structures[0] || null; var viewerFrame = null; var pendingSelection = null; var offset = 0;
    var layout = document.createElement("div"); layout.className = structureArtifact ? "linked-result-layout" : "linked-result-layout table-only";
    var tableRegion = document.createElement("div"); tableRegion.className = "linked-result-table";
    var viewerStage = document.createElement("div"); viewerStage.className = "linked-result-structure";
    layout.append(tableRegion); if (structureArtifact) layout.append(viewerStage); stage.appendChild(layout);

    async function loadPage() {
      var requestedOffset = offset;
      var page;
      try {
        var response = await A.authFetch(tableUrl(tableArtifact.path, requestedOffset), { signal: services.signal });
        if (!response.ok) throw new Error("Result table could not be loaded.");
        page = await response.json();
      } catch (error) {
        if (requestedOffset !== offset) return;
        throw error;
      }
      if (requestedOffset !== offset) return;
      tableRegion.replaceChildren();
      var wrap = document.createElement("div"); wrap.className = "artifact-table-wrap";
      var table = document.createElement("table"); table.className = "artifact-table-preview entity-result-table";
      var heading = document.createElement("tr");
      page.columns.forEach(function (column) { var th = document.createElement("th"); th.scope = "col"; th.textContent = column; heading.appendChild(th); });
      var pick = document.createElement("th"); pick.scope = "col"; pick.textContent = "Review"; heading.appendChild(pick); table.appendChild(heading);
      var indexes = {}; page.columns.forEach(function (column, index) { indexes[column] = index; });
      page.rows.forEach(function (row) {
        var id = view.mapping.key_columns.map(function (column) { return row[indexes[column]]; }).join(":");
        var label = view.mapping.label_column ? row[indexes[view.mapping.label_column]] + " · " + id : id;
        var item = {
          view_id: view.id, entity: view.mapping.entity, id: id, label: label,
          values: Object.fromEntries((view.mapping.evidence_columns || []).map(function (column) { return [column, row[indexes[column]]]; })),
          artifacts: [tableArtifact, structureArtifact].filter(Boolean).map(function (artifact) { return { path: artifact.path, sha256: artifact.sha256 }; })
        };
        var tr = document.createElement("tr"); tr.tabIndex = 0; tr.setAttribute("aria-selected", "false");
        row.forEach(function (value) { var td = document.createElement("td"); td.textContent = value; tr.appendChild(td); });
        var selectCell = document.createElement("td"); var checkbox = document.createElement("input"); checkbox.type = "checkbox";
        checkbox.setAttribute("aria-label", "Add " + label + " to shortlist"); checkbox.checked = shortlist.has(shortlistKey(item.view_id, item.id));
        checkbox.addEventListener("click", function (event) { event.stopPropagation(); });
        checkbox.addEventListener("change", function () { checkbox.checked = setShortlisted(item, checkbox.checked); });
        selectCell.appendChild(checkbox); tr.appendChild(selectCell);
        function follow() {
          table.querySelectorAll("tr[aria-selected=true]").forEach(function (node) { node.setAttribute("aria-selected", "false"); });
          tr.setAttribute("aria-selected", "true");
          if (!view.mapping.residue_column) return;
          pendingSelection = {
            type: "select-residue", chain: view.mapping.chain_column ? row[indexes[view.mapping.chain_column]] : "",
            residue: Number(row[indexes[view.mapping.residue_column]]), numbering: view.mapping.numbering
          };
          if (viewerFrame) postToShell(viewerFrame, pendingSelection);
        }
        tr.addEventListener("click", follow); tr.addEventListener("keydown", function (event) {
          if (event.key === "Enter") { event.preventDefault(); follow(); }
        }); table.appendChild(tr);
      });
      wrap.appendChild(table); tableRegion.appendChild(wrap);
      var pager = document.createElement("div"); pager.className = "table-pager";
      var previous = document.createElement("button"); previous.type = "button"; previous.className = "btn btn-soft btn-small";
      previous.textContent = "Previous"; previous.disabled = requestedOffset === 0;
      previous.addEventListener("click", function () { offset = Math.max(0, offset - 100); loadPage().catch(showPreviewError); });
      var next = document.createElement("button"); next.type = "button"; next.className = "btn btn-soft btn-small";
      next.textContent = "Next"; next.disabled = !page.has_more;
      next.addEventListener("click", function () { offset += 100; loadPage().catch(showPreviewError); });
      var pageLabel = document.createElement("span"); pageLabel.textContent = "Rows " + (requestedOffset + 1) + "–" + (requestedOffset + page.rows.length);
      pager.append(previous, pageLabel, next); tableRegion.appendChild(pager);
    }
    await loadPage();
    if (structureArtifact) {
      if (exceedsPreviewLimit(structureArtifact, previewRegistry.resolve(structureArtifact), viewerStage)) return;
      try {
        var response = await A.authFetch(structureArtifact.url, { signal: services.signal });
        if (!response.ok) throw new Error("Structure download failed");
        viewerFrame = await renderMolstar(
          await response.text(), structureArtifact, viewerStage, previewHost.generation, true, services.signal
        );
        if (viewerFrame && pendingSelection) postToShell(viewerFrame, pendingSelection);
      } catch (error) {
        if (services.signal.aborted) return;
        var message = document.createElement("p"); message.className = "preview-message";
        message.textContent = "Structure linking unavailable; the result table remains usable."; viewerStage.appendChild(message);
      }
    }
  }

  async function renderEvidenceBundle(view, stage, services) {
    var items = artifactPaths(view, "items"); var list = document.createElement("div"); list.className = "evidence-list";
    var preview = document.createElement("div"); preview.className = "evidence-preview"; stage.append(list, preview);
    var evidenceGeneration = 0;
    async function openEvidence(artifact) {
      var generation = ++evidenceGeneration; var plugin = previewRegistry.resolve(artifact);
      var surface = document.createElement("div"); surface.className = "result-plugin-surface"; preview.replaceChildren(surface);
      if (!plugin) { surface.textContent = "This evidence is available as a download."; return; }
      if (exceedsPreviewLimit(artifact, plugin, surface)) return;
      try { await plugin.render(artifact, surface, services); }
      catch (error) {
        if (generation !== evidenceGeneration || error.name === "AbortError") return;
        surface.replaceChildren(); var message = document.createElement("p"); message.className = "preview-message";
        message.textContent = error.message || "Preview unavailable"; surface.appendChild(message);
      }
    }
    items.forEach(function (artifact) {
      var button = document.createElement("button"); button.type = "button"; button.className = "evidence-item";
      button.textContent = artifact.path; button.addEventListener("click", function () { openEvidence(artifact); }); list.appendChild(button);
    });
    if (items[0]) await openEvidence(items[0]);
    else preview.textContent = "No evidence artifacts are available.";
  }

  function showPreviewError(error) {
    if (error && error.name === "AbortError") return;
    var stage = document.getElementById("artifactPreview");
    stage.innerHTML = '<p class="preview-message"></p>'; stage.firstChild.textContent = error.message || "Preview unavailable";
  }

  previewRegistry = window.REvoComputeResultPreviews.createRegistry({
    structure: async function (artifact, stage, services) {
      stage.hidden = true;
      if (structureHolder) structureHolder.hidden = false;
      try {
        await previewStructure(artifact, stage, services.signal);
      } catch (error) {
        stage.hidden = false;
        if (structureHolder) structureHolder.hidden = true;
        throw error;
      }
    },
    image: previewImage,
    table: previewTable,
    text: previewText,
    "candidate-collection": renderCandidateCollection,
    "entity-table": renderEntityTable,
    "evidence-bundle": renderEvidenceBundle,
    alignment: renderAlignment,
    trajectory: renderTrajectory,
    "metric-series": renderMetricSeries,
    matrix: renderMatrix,
    "scalar-summary": renderScalarSummary
  });
  previewHost = new window.REvoComputeResultPreviews.ResultPreviewHost(
    previewRegistry,
    document.getElementById("artifactPreview"),
    {
      statusNode: document.getElementById("previewStatus"),
      beforeClear: function () { document.getElementById("previewStatus").textContent = ""; }
    }
  );
  structureHolder = document.createElement("div");
  structureHolder.className = "artifact-preview-stage";
  structureHolder.hidden = true;
  document.getElementById("artifactPreview").parentNode.appendChild(structureHolder);

  async function previewArtifact(artifact) {
    document.getElementById("previewTitle").textContent = artifact.path;
    document.getElementById("previewDescription").textContent = artifact.role + " artifact · " + formatBytes(artifact.size);
    var download = document.getElementById("artifactDownload"); download.hidden = false;
    download.href = artifact.url + "?download=1"; download.download = "";
    document.querySelectorAll(".artifact-row").forEach(function (node) {
      var active = node.dataset.path === artifact.path; node.classList.toggle("active", active);
      node.setAttribute("aria-current", active ? "true" : "false");
    });
    var stage = document.getElementById("artifactPreview");
    stage.hidden = false; if (structureHolder) structureHolder.hidden = true;
    try { await previewHost.render(artifact); } catch (error) { showPreviewError(error); }
  }

  async function previewView(view, focusHeading) {
    document.getElementById("previewTitle").textContent = view.title;
    document.getElementById("artifactDownload").hidden = true;
    document.getElementById("previewDescription").textContent = view.description || "";
    document.querySelectorAll(".result-view-tab").forEach(function (node) {
      var active = node.dataset.viewId === view.id; node.setAttribute("aria-pressed", active ? "true" : "false");
    });
    document.getElementById("artifactPreview").hidden = false; if (structureHolder) structureHolder.hidden = true;
    try {
      await previewHost.render(view);
      if (focusHeading) document.getElementById("previewTitle").focus();
    } catch (error) { showPreviewError(error); }
  }

  function artifactButton(artifact) {
    var button = document.createElement("button"); button.type = "button"; button.className = "artifact-row"; button.dataset.path = artifact.path;
    var name = document.createElement("span"); name.className = "artifact-row-name"; name.textContent = artifact.path;
    var size = document.createElement("span"); size.className = "artifact-row-size";
    size.textContent = (artifact.role === "diagnostic" ? "Execution log · " : artifact.role + " · ") + formatBytes(artifact.size);
    button.append(name, size); button.addEventListener("click", function () { previewArtifact(artifact); }); return button;
  }

  function artifactFolder(directory, children) {
    var folder = document.createElement("details"); folder.className = "artifact-folder"; folder.open = true;
    var summary = document.createElement("summary"); summary.className = "artifact-folder-name"; summary.textContent = directory + "/";
    var inner = document.createElement("div"); inner.className = "artifact-folder-children";
    children.forEach(function (child) { inner.appendChild(child); }); folder.append(summary, inner); return folder;
  }

  function buildArtifactTree() {
    var root = { folders: {}, files: [] };
    artifacts.forEach(function (artifact) {
      var node = root; artifact.path.split("/").slice(0, -1).forEach(function (segment) {
        node.folders[segment] = node.folders[segment] || { folders: {}, files: [] }; node = node.folders[segment];
      }); node.files.push(artifact);
    });
    function renderNode(node) {
      var entries = [];
      Object.keys(node.folders).sort().forEach(function (name) { entries.push(artifactFolder(name, renderNode(node.folders[name]))); });
      node.files.slice().sort(function (a, b) { return a.path.localeCompare(b.path); })
        .forEach(function (artifact) { entries.push(artifactButton(artifact)); }); return entries;
    }
    return renderNode(root);
  }

  function renderArtifacts(query) {
    var normalized = String(query || "").trim().toLowerCase(); var list = document.getElementById("artifactList"); list.replaceChildren();
    if (normalized) {
      artifacts.filter(function (artifact) { return artifact.path.toLowerCase().includes(normalized); })
        .forEach(function (artifact) { list.appendChild(artifactButton(artifact)); }); return;
    }
    buildArtifactTree().forEach(function (node) { list.appendChild(node); });
  }

  function renderViewTabs() {
    var tabs = document.getElementById("resultViews"); tabs.replaceChildren();
    resultViews.forEach(function (view) {
      var button = document.createElement("button"); button.type = "button"; button.className = "result-view-tab";
      button.dataset.viewId = view.id; button.textContent = view.title;
      button.addEventListener("click", function () { previewView(view, true); }); tabs.appendChild(button);
    });
  }

  function appendDefinitionList(root, items) {
    items.forEach(function (item) {
      var term = document.createElement("dt"); term.textContent = item[0]; var value = document.createElement("dd"); value.textContent = item[1];
      root.append(term, value);
    });
  }

  function renderScientificRecord(payload) {
    var run = payload.run || {}; var method = run.method || {}; var check = payload.output_check || { state: "not_configured", problems: [] };
    document.getElementById("methodName").textContent = method.name || payload.task_type;
    document.getElementById("resultStatus").textContent = payload.status || task.status;
    var checkText = { passed: "Expected outputs found", failed: "Output mapping incomplete", not_configured: "No principal result mapping", not_assessed: "Outputs were not assessed" };
    document.getElementById("outputCheck").textContent = checkText[check.state] || check.state;
    document.getElementById("outputSummary").textContent = method.output_summary || "Inspect the published artifacts below.";
    var problems = document.getElementById("outputProblems"); problems.replaceChildren();
    (check.problems || []).forEach(function (problem) { var li = document.createElement("li"); li.textContent = problem; problems.appendChild(li); });
    var limitations = document.getElementById("limitationList"); limitations.replaceChildren();
    (payload.limitations || []).forEach(function (text) { var li = document.createElement("li"); li.textContent = text; limitations.appendChild(li); });
    var setup = document.getElementById("runSetup"); setup.replaceChildren();
    appendDefinitionList(setup, [
      ["Submitted", run.submitted_at || "—"], ["Started", run.started_at || "—"], ["Finished", run.finished_at || "—"],
      ["Wall time", run.walltime_seconds == null ? "—" : Math.round(run.walltime_seconds) + " s"]
    ]);
    (run.inputs || []).forEach(function (input) { appendDefinitionList(setup, [["Input", input.path + " · sha256 " + input.sha256]]); });
    (run.parameters || []).forEach(function (parameter) {
      appendDefinitionList(setup, [[parameter.label, String(parameter.value) + (parameter.unit ? " " + parameter.unit : "")]]);
    });
    var citations = document.getElementById("citationList"); citations.replaceChildren();
    (run.citations || []).forEach(function (citation) {
      var li = document.createElement("li"); var link = document.createElement("a"); link.href = "https://doi.org/" + citation.doi;
      link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = citation.title + " · " + citation.doi; li.appendChild(link); citations.appendChild(li);
    });
  }

  async function loadResults() {
    await disposeActiveViewer(); structureTextCache.clear(); structureTextCacheBytes = 0;
    if (structureHolder) structureHolder.hidden = true;
    var response = await A.authFetch("/compute/api/results/" + encodeURIComponent(task.md5));
    var payload = await response.json().catch(function () { return {}; });
    var initialStatus = payload.status || task.status;
    if (window.__revocomputeStatusPoll) clearInterval(window.__revocomputeStatusPoll);
    var terminalStatuses = ["finished", "failed", "cancelled", "deleted", "deleted:finshed", "deleted:cancel"];
    var statusPollInFlight = false;
    if (terminalStatuses.indexOf(initialStatus) === -1) {
      window.__revocomputeStatusPoll = setInterval(async function () {
        if (statusPollInFlight) return; statusPollInFlight = true;
        try {
          var pollResponse = await A.authFetch("/compute/api/running/" + encodeURIComponent(task.md5));
          var pollPayload = await pollResponse.json().catch(function () { return {}; });
          var isTerminal = terminalStatuses.indexOf(pollPayload.status) !== -1;
          if (!pollResponse.ok && !isTerminal) return;
          if (pollPayload.status) document.getElementById("resultStatus").textContent = pollPayload.status;
          if (isTerminal) { clearInterval(window.__revocomputeStatusPoll); window.location.reload(); }
        } catch (error) { /* retry transient failures */ } finally { statusPollInFlight = false; }
      }, 15000);
    }
    if (!response.ok || !Array.isArray(payload.artifacts)) {
      if (response.ok && terminalStatuses.indexOf(initialStatus) === -1) return;
      throw new Error(payload.message || "Results are not available yet");
    }
    if (payload.schema_version !== 3) throw new Error("This result record uses an unsupported schema version.");
    artifacts = payload.artifacts; resultViews = Array.isArray(payload.views) ? payload.views : [];
    renderScientificRecord(payload); renderArtifacts(""); renderViewTabs(); renderShortlist();
    document.getElementById("artifactSummary").textContent = artifacts.length + " files · " + formatBytes(payload.total_size);
    var archiveButton = document.getElementById("archiveButton");
    delete archiveButton.dataset.downloadUrl;
    archiveButton.textContent = "Create ZIP";
    document.getElementById("archiveState").textContent = "Individual manifest-approved files are available now.";
    if (payload.archive && payload.archive.ready) {
      archiveButton.textContent = "Download ZIP"; archiveButton.dataset.downloadUrl = payload.archive.download_url;
      document.getElementById("archiveState").textContent = "The manifest-approved ZIP is ready.";
    }
    var first = resultViews.find(function (view) { return view.role === "primary"; });
    if (first) await previewView(first, false);
    else {
      document.getElementById("previewTitle").textContent = "No principal result view";
      document.getElementById("previewDescription").textContent = "This method has not yet declared a scientific result composition. All published artifacts remain available below.";
      var stage = document.getElementById("artifactPreview"); stage.replaceChildren();
      var empty = document.createElement("p"); empty.className = "preview-message";
      empty.textContent = "Open All artifacts to inspect or download this run."; stage.appendChild(empty);
      var artifactsSection = document.querySelector(".artifact-section");
      if (artifactsSection) artifactsSection.open = true;
    }
  }

  async function archiveAction() {
    var button = document.getElementById("archiveButton");
    if (button.dataset.downloadUrl) { window.location.assign(button.dataset.downloadUrl); return; }
    button.disabled = true;
    try {
      var response = await A.authFetch("/compute/api/results/" + encodeURIComponent(task.md5) + "/archive", { method: "POST" });
      var payload = await response.json().catch(function () { return {}; });
      if (!response.ok && response.status !== 202) throw new Error(payload.error || "Archive request failed");
      document.getElementById("archiveState").textContent = "Archive generation requested. Refresh shortly to download it.";
      showToast("Archive generation requested.", "info");
    } catch (error) { showToast(error.message || "Archive request failed", "error"); }
    finally { button.disabled = false; }
  }

  document.addEventListener("DOMContentLoaded", function () {
    T.initToggle(document.getElementById("themeToggle"));
    document.getElementById("refreshResults").addEventListener("click", function () { window.location.reload(); });
    document.getElementById("artifactSearch").addEventListener("input", function (event) { renderArtifacts(event.target.value); });
    document.getElementById("archiveButton").addEventListener("click", archiveAction);
    document.getElementById("exportShortlist").addEventListener("click", exportShortlist);

    loadResults().catch(function (error) {
      document.getElementById("artifactPreview").innerHTML = '<p class="preview-message"></p>';
      document.getElementById("artifactPreview").firstChild.textContent = error.message || "Results unavailable";
    });
  });
  window.addEventListener("pagehide", function () {
    previewHost.destroy();
  });
})();
