/* REvoCompute — RFdiffusion structure-region workspace plugin */
/* SPDX-License-Identifier: GPL-3.0-only */

(function (global) {
  "use strict";
  var registry = global.REvoComputeInputWorkspace.registry;

  function element(tag, className, text) {
    var node = document.createElement(tag); node.className = className || "";
    if (text != null) node.textContent = text; return node;
  }

  registry.register({
    id: "rfdiffusion-regions",
    mount: function (target, definition, context) {
      var modeWrap = element("div", "rfd-mode-row");
      var modeLabel = element("label", "param-label", "Design mode");
      modeLabel.htmlFor = "rfd_mode";
      var mode = element("select", "text-input"); mode.id = "rfd_mode";
      (definition.options.modes || []).forEach(function (name) { var option = element("option", "", name.replaceAll("_", " ")); option.value = name; mode.appendChild(option); });
      modeWrap.append(modeLabel, mode);

      // One plain sentence per mode — the user picks what to make, not a syntax name.
      var intents = {
        unconditional: "Generate a new backbone from scratch. No input structure needed.",
        motif_scaffolding: "Extend a motif: pick the motif residues in the structure, then grow the rest of the protein.",
        binder: "Design a binder: pick the target surface, then grow a binder chain against it.",
        expert: "Write the RFdiffusion contig yourself."
      };
      var intent = element("p", "rfd-intent");

      // Step 1 — guided modes only. The primary button's label follows the mode.
      var guided = element("div", "rfd-step");
      var applyRow = element("div", "rfd-apply-row");
      var apply = element("button", "btn btn-soft btn-small", "Use selection as motif"); apply.type = "button";
      var hotspot = element("button", "btn btn-soft btn-small", "Use selection as hotspots"); hotspot.type = "button";
      var feedback = element("p", "rfd-feedback");
      var guidedHelp = element("p", "param-help", "1. Select residues in the viewer — click in the 3D view or the sequence strip — then apply them below.");
      applyRow.append(apply, hotspot);
      guided.append(guidedHelp, applyRow, feedback);

      // Step 2 — size; the only remaining control for unconditional mode.
      var lengthRow = element("div", "rfd-step");
      var lengthTitle = element("p", "rfd-step-title");
      var lengthFields = element("div", "rfd-length-fields");
      var minLabel = element("label", "param-label", "Minimum length"); minLabel.htmlFor = "rfd_min";
      var minimum = element("input", "text-input"); minimum.type = "number"; minimum.min = "1"; minimum.id = "rfd_min"; minimum.value = "100";
      var maxLabel = element("label", "param-label", "Maximum length"); maxLabel.htmlFor = "rfd_max";
      var maximum = element("input", "text-input"); maximum.type = "number"; maximum.min = "1"; maximum.id = "rfd_max"; maximum.value = "100";
      lengthFields.append(minLabel, minimum, maxLabel, maximum);
      lengthRow.append(lengthTitle, lengthFields);

      // Expert mode — raw contig only.
      var expert = element("div", "rfd-step");
      var expertTitle = element("p", "rfd-step-title", "Write the contig");
      var rawLabel = element("label", "param-label", "Expert contig"); rawLabel.htmlFor = "rfd_contig";
      var raw = element("input", "text-input"); raw.value = "100-100"; raw.placeholder = "RFdiffusion contig"; raw.id = "rfd_contig";
      var expertHelp = element("p", "param-help", "e.g. A1-150/0 70-100 extends chain A with a 70–100 residue chain.");
      expert.append(expertTitle, rawLabel, raw, expertHelp);

      // The normalized plan (or the error that must be fixed) — one line.
      var status = element("p", "rfd-status", "Server normalization runs before submission.");
      target.append(modeWrap, intent, guided, lengthRow, expert, status);

      var fixed = []; var hotspots = []; var controller = null; var normalizationError = null;

      function selections() {
        return (context.structureSelections ? context.structureSelections() : []).map(function (item) {
          return { chain: String(item.chain || item.auth_asym_id || "A"), residue: Number(item.residue || item.auth_seq_id || item.label_seq_id) };
        }).filter(function (item) { return Number.isInteger(item.residue); });
      }
      function selectedRanges() {
        var ranges = [];
        selections().sort(function (a, b) { return a.chain.localeCompare(b.chain) || a.residue - b.residue; }).forEach(function (item) {
          var last = ranges[ranges.length - 1];
          if (last && last.chain === item.chain && item.residue <= last.end + 1) last.end = Math.max(last.end, item.residue);
          else ranges.push({ kind: "fixed", chain: item.chain, start: item.residue, end: item.residue });
        });
        return ranges;
      }
      function describeRanges(ranges) {
        return ranges.map(function (range) {
          return range.chain + range.start + (range.end > range.start ? "–" + range.end : "");
        }).join(", ");
      }
      function describeSelections(items) {
        return items.map(function (item) { return item.chain + item.residue; }).join(", ");
      }
      function applyLabel() {
        if (mode.value === "binder") return "Use selection as target";
        return "Use selection as motif";
      }
      function value() {
        var generated = { kind: "generated", min_length: Number(minimum.value), max_length: Number(maximum.value) };
        var segments = [generated];
        if (mode.value === "motif_scaffolding") segments = [generated].concat(fixed, [generated]);
        if (mode.value === "binder") segments = fixed.concat([{ kind: "chain_break" }, generated]);
        return { version: 1, mode: mode.value, segments: segments, hotspots: hotspots, raw_contig: mode.value === "expert" ? raw.value : null };
      }
      function normalize() {
        var auth = global.REvoDesignAuth;
        if (!auth || typeof auth.authFetch !== "function") {
          normalizationError = "Normalization unavailable";
          status.textContent = normalizationError; status.className = "rfd-status rfd-status-error";
          return;
        }
        if (controller) controller.abort(); controller = new AbortController();
        auth.authFetch("/compute/api/types/" + encodeURIComponent(context.form.name) + "/workspace/normalize", {
          method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
          body: JSON.stringify({ capability_id: definition.id, value: value() })
        }).then(function (response) { return response.json().then(function (body) { return { ok: response.ok, body: body }; }); })
          .then(function (result) {
            normalizationError = result.ok ? null : result.body.error;
            // A fresh binder mode shows the server's requirements before the
            // user has had a chance to act: present it as guidance, not a
            // failure. Submission is still blocked until the flow is done.
            var needsWork = !result.ok && mode.value === "binder" && !fixed.length && !hotspots.length;
            status.textContent = needsWork
              ? "Binder design needs a target and hotspots — select residues in the viewer, then use the buttons below."
              : (result.ok ? result.body.summary : result.body.error);
            status.className = "rfd-status" + (!result.ok && !needsWork ? " rfd-status-error" : "");
            context.changed();
          })
          .catch(function (error) {
            if (error.name === "AbortError") return;
            normalizationError = "Normalization unavailable";
            status.textContent = normalizationError; status.className = "rfd-status rfd-status-error";
          });
      }
      function useFixed() {
        var ranges = selectedRanges();
        if (!ranges.length) { feedback.textContent = "Select residues in the viewer first."; feedback.className = "rfd-feedback rfd-feedback-error"; return; }
        fixed = ranges;
        feedback.textContent = (mode.value === "binder" ? "Target: " : "Motif: ") + describeRanges(ranges);
        feedback.className = "rfd-feedback";
        context.changed(); normalize();
      }
      function useHotspots() {
        var picked = selections();
        if (!picked.length) { feedback.textContent = "Select residues in the viewer first."; feedback.className = "rfd-feedback rfd-feedback-error"; return; }
        hotspots = picked;
        feedback.textContent = "Hotspots: " + describeSelections(picked);
        feedback.className = "rfd-feedback";
        context.changed(); normalize();
      }
      function applyMode() {
        intent.textContent = intents[mode.value] || "";
        apply.textContent = applyLabel();
        guided.hidden = mode.value === "expert" || mode.value === "unconditional";
        lengthRow.hidden = mode.value === "expert";
        lengthTitle.textContent = mode.value === "unconditional" ? "Generated length" : "2. Choose the generated length";
        expert.hidden = mode.value !== "expert";
        if (mode.value === "unconditional") hotspots = [];
        if (mode.value === "expert") { fixed = []; hotspots = []; }
        feedback.textContent = ""; feedback.className = "rfd-feedback";
        context.changed(); normalize();
      }
      apply.addEventListener("click", useFixed); hotspot.addEventListener("click", useHotspots);
      mode.addEventListener("change", applyMode);
      [raw, minimum, maximum].forEach(function (node) { node.addEventListener("change", function () { context.changed(); normalize(); }); });
      applyMode();
      return { readValue: value, validate: function () { return normalizationError ? [normalizationError] : []; }, destroy: function () { if (controller) controller.abort(); } };
    }
  });
})(window);
