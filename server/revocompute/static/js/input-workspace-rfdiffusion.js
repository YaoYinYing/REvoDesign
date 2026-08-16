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
      var mode = element("select", "text-input");
      (definition.options.modes || []).forEach(function (name) { var option = element("option", "", name.replaceAll("_", " ")); option.value = name; mode.appendChild(option); });
      var raw = element("input", "text-input"); raw.value = "100-100"; raw.placeholder = "RFdiffusion contig";
      var minimum = element("input", "text-input"); minimum.type = "number"; minimum.min = "1"; minimum.value = "100";
      var maximum = element("input", "text-input"); maximum.type = "number"; maximum.min = "1"; maximum.value = "100";
      var motif = element("button", "btn btn-soft btn-small", "Use selection as motif"); motif.type = "button";
      var targetButton = element("button", "btn btn-soft btn-small", "Use selection as target"); targetButton.type = "button";
      var hotspot = element("button", "btn btn-soft btn-small", "Use selection as hotspots"); hotspot.type = "button";
      var normalized = element("p", "param-help", "Server normalization runs before submission.");
      target.append(mode, element("label", "param-label", "Generated length minimum"), minimum,
        element("label", "param-label", "Generated length maximum"), maximum,
        element("label", "param-label", "Expert contig"), raw,
        element("p", "param-help", "Select residues in the structure viewer, then apply them below."),
        motif, targetButton, hotspot, normalized);
      var fixed = []; var hotspots = []; var controller = null;

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
      function value() {
        var generated = { kind: "generated", min_length: Number(minimum.value), max_length: Number(maximum.value) };
        var segments = [generated];
        if (mode.value === "motif_scaffolding") segments = [generated].concat(fixed, [generated]);
        if (mode.value === "binder") segments = fixed.concat([{ kind: "chain_break" }, generated]);
        return { version: 1, mode: mode.value, segments: segments, hotspots: hotspots, raw_contig: mode.value === "expert" ? raw.value : null };
      }
      function normalize() {
        if (controller) controller.abort(); controller = new AbortController();
        global.REvoDesignAuth.authFetch("/compute/api/types/" + encodeURIComponent(context.form.name) + "/workspace/normalize", {
          method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
          body: JSON.stringify({ capability_id: definition.id, value: value() })
        }).then(function (response) { return response.json().then(function (body) { return { ok: response.ok, body: body }; }); })
          .then(function (result) { normalized.textContent = result.ok ? result.body.summary : result.body.error; })
          .catch(function (error) { if (error.name !== "AbortError") normalized.textContent = "Normalization unavailable"; });
      }
      function useFixed() { fixed = selectedRanges(); context.changed(); normalize(); }
      function useHotspots() { hotspots = selections(); context.changed(); normalize(); }
      motif.addEventListener("click", useFixed); targetButton.addEventListener("click", useFixed); hotspot.addEventListener("click", useHotspots);
      [mode, raw, minimum, maximum].forEach(function (node) { node.addEventListener("change", function () { context.changed(); normalize(); }); });
      return { readValue: value, validate: function () { return []; }, destroy: function () { if (controller) controller.abort(); } };
    }
  });
})(window);
