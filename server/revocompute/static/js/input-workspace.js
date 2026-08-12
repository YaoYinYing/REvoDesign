/* REvoCompute — composable scientific input workspace */
/* SPDX-License-Identifier: GPL-3.0-only */

(function (global) {
  "use strict";
  var Core = global.REvoComputePlugins;
  if (!Core) throw new Error("plugin-host.js must be loaded before input-workspace.js");

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function pathFor(file) { return file.webkitRelativePath || file.name; }
  function lowerName(file) { return String(file.name || "").toLowerCase(); }
  function matchesExtension(file, extensions) {
    return (extensions || []).some(function (extension) {
      return lowerName(file).endsWith(String(extension).toLowerCase());
    });
  }

  function normalizeSequence(raw) {
    return String(raw || "").toUpperCase().replace(/[^A-Z]/g, "");
  }

  function sequenceSummary(sequence) {
    if (!sequence) return "No pasted sequence. A selected FASTA file will be used.";
    var groups = [];
    for (var index = 0; index < sequence.length; index += 10) groups.push(sequence.slice(index, index + 10));
    return groups.join(" ") + "\n" + sequence.length + " residues";
  }

  function parsePdb(text) {
    var chains = new Set(); var residues = new Map(); var atoms = 0; var heteroAtoms = 0;
    String(text).split(/\r?\n/).forEach(function (line) {
      if (!line.startsWith("ATOM  ") && !line.startsWith("HETATM")) return;
      if (line.startsWith("ATOM  ")) atoms += 1; else heteroAtoms += 1;
      var chain = line.slice(21, 22).trim() || "_";
      var number = line.slice(22, 27).trim();
      var name = line.slice(17, 20).trim() || "UNK";
      chains.add(chain);
      if (number) residues.set(chain + number, { id: chain + number, chain: chain, name: name, number: number });
    });
    return { atoms: atoms, heteroAtoms: heteroAtoms, chains: Array.from(chains), residues: Array.from(residues.values()) };
  }

  function parseCif(text) {
    var chains = new Set(); var residues = new Map(); var atoms = 0;
    String(text).split(/\r?\n/).forEach(function (line) {
      var fields = line.trim().split(/\s+/);
      if (fields[0] !== "ATOM" && fields[0] !== "HETATM") return;
      atoms += 1;
      var name = fields[5] || "UNK";
      var chain = fields[6] || "_";
      var number = fields[8] || fields[7] || String(atoms);
      chains.add(chain);
      residues.set(chain + number, { id: chain + number, chain: chain, name: name, number: number });
    });
    return { atoms: atoms, heteroAtoms: 0, chains: Array.from(chains), residues: Array.from(residues.values()) };
  }

  function workspaceCard(definition) {
    var section = element("section", "workspace-card");
    section.dataset.capabilityId = definition.id;
    var heading = element("div", "workspace-card-heading");
    heading.appendChild(element("span", "workspace-plugin-badge", definition.plugin));
    heading.appendChild(element("h2", "workspace-card-title", definition.title || definition.id));
    section.appendChild(heading);
    if (definition.description) section.appendChild(element("p", "workspace-card-description", definition.description));
    var body = element("div", "workspace-card-body");
    section.appendChild(body);
    return { section: section, body: body };
  }

  function renderParam(parameter, context) {
    var wrap = element("div", "param-field");
    var labelRow = element("div", "param-label-row");
    var label = element("label", "param-label", parameter.label || parameter.name);
    label.htmlFor = "param_" + parameter.name;
    if (parameter.unit) label.textContent += " (" + parameter.unit + ")";
    labelRow.appendChild(label);
    if (parameter.help) {
      var tip = element("span", "param-tooltip", "?");
      var bubble = element("span", "param-tooltip-bubble", parameter.help);
      tip.appendChild(bubble);
      labelRow.appendChild(tip);
    }
    wrap.appendChild(labelRow);
    function isBinaryChoice(choices) {
      if (!choices || choices.length !== 2) return false;
      var set = String(choices[0]) + "," + String(choices[1]);
      return set === "0,1" || set === "1,0" || set === "true,false" || set === "false,true";
    }

    var control;
    if (isBinaryChoice(parameter.choices)) {
      var onValue = String(parameter.choices[0]), offValue = String(parameter.choices[1]);
      control = element("span", "param-toggle-wrap");
      var hidden = element("input", "");
      hidden.type = "hidden"; hidden.value = parameter.default === onValue || parameter.default === true ? onValue : offValue;
      hidden.id = "param_" + parameter.name; hidden.dataset.paramName = parameter.name;
      var checkbox = element("input", "param-toggle");
      checkbox.type = "checkbox"; checkbox.checked = hidden.value === onValue;
      checkbox.addEventListener("change", function () {
        hidden.value = checkbox.checked ? onValue : offValue;
        context.changed();
      });
      control.appendChild(hidden);
      control.appendChild(checkbox);
    } else if (parameter.type === "bool") {
      control = element("span", "param-toggle-wrap");
      var hiddenB = element("input", "");
      hiddenB.type = "hidden"; hiddenB.value = parameter.default === true ? "true" : "false";
      hiddenB.id = "param_" + parameter.name; hiddenB.dataset.paramName = parameter.name;
      var checkboxB = element("input", "param-toggle");
      checkboxB.type = "checkbox"; checkboxB.checked = parameter.default === true;
      checkboxB.addEventListener("change", function () {
        hiddenB.value = checkboxB.checked ? "true" : "false";
        context.changed();
      });
      control.appendChild(hiddenB);
      control.appendChild(checkboxB);
    } else if (parameter.choices && parameter.choices.length) {
      control = element("select", "text-input");
      parameter.choices.forEach(function (choice) {
        var option = element("option", "", String(choice)); option.value = choice;
        option.selected = choice === parameter.default; control.appendChild(option);
      });
    } else {
      control = element("input", "text-input");
      control.type = parameter.type === "int" || parameter.type === "float" ? "number" : "text";
      control.value = parameter.default == null ? "" : parameter.default;
      if (parameter.minimum != null) control.min = parameter.minimum;
      if (parameter.maximum != null) control.max = parameter.maximum;
      if (parameter.step != null) control.step = parameter.step;
      control.required = Boolean(parameter.required);
      control.id = "param_" + parameter.name;
      control.dataset.paramName = parameter.name;
    }
    var error = element("p", "param-error"); error.id = "param_error_" + parameter.name; error.hidden = true;
    if (parameter.type !== "bool") {
      control.setAttribute("aria-describedby", error.id);
      control.addEventListener("input", function () {
        control.removeAttribute("aria-invalid"); error.hidden = true; error.textContent = ""; context.changed();
      });
    }
    wrap.appendChild(control);
    if (parameter.description) wrap.appendChild(element("p", "param-help", parameter.description));
    wrap.appendChild(error);
    return wrap;
  }

  function validateParameters(parameters) {
    var errors = [];
    (parameters || []).forEach(function (parameter) {
      var control = document.getElementById("param_" + parameter.name);
      var message = document.getElementById("param_error_" + parameter.name);
      if (!control || control.checkValidity()) return;
      control.setAttribute("aria-invalid", "true");
      if (message) { message.textContent = control.validationMessage || "Check this value."; message.hidden = false; }
      errors.push((parameter.label || parameter.name) + ": " + (control.validationMessage || "invalid value"));
    });
    return errors;
  }

  var registry = new Core.PluginRegistry("input");

  registry.register({
    id: "files",
    mount: function (target, definition, context) {
      var input = context.fileInput;
      var row = element("div", "file-upload-row");
      var button = element("button", "btn btn-soft", context.form.file_input.multiple ? "Choose files" : "Choose file"); button.type = "button";
      var folderButton = null; var folderInput = null;
      if (context.form.file_input.multiple) {
        folderButton = element("button", "btn btn-soft", "Choose folder"); folderButton.type = "button";
        folderInput = element("input"); folderInput.type = "file"; folderInput.multiple = true;
        folderInput.className = "sr-only"; folderInput.accept = context.form.file_input.accept;
        folderInput.setAttribute("webkitdirectory", "");
      }
      var summary = element("span", "file-name muted", "No files selected");
      row.appendChild(button);
      if (folderButton) row.appendChild(folderButton);
      row.appendChild(summary); target.appendChild(row);
      if (folderInput) target.appendChild(folderInput);
      var hint = element("p", "param-help"); target.appendChild(hint);
      var fileList = element("div", "input-file-list"); target.appendChild(fileList);
      var fileError = element("p", "param-error"); fileError.id = "file_error"; fileError.hidden = true;
      target.appendChild(fileError);

      function refresh() {
        var files = context.files();
        button.removeAttribute("aria-invalid");
        fileError.hidden = true; fileError.textContent = "";
        summary.textContent = files.length ? files.length + " file(s) selected" : "No files selected";
        hint.textContent = "Accepted: " + context.form.file_input.extensions.join(", ") +
          ". Maximum " + context.form.file_input.max_files + ". Nested relative paths are preserved.";
        fileList.replaceChildren();
        files.forEach(function (file, index) {
          var item = element("label", "input-file-item");
          var radio = element("input"); radio.type = "radio"; radio.name = "primary_input";
          radio.checked = index === context.primaryIndex;
          radio.disabled = !matchesExtension(file, context.form.file_input.primary_extensions);
          radio.addEventListener("change", function () { context.primaryIndex = index; refresh(); context.filesChanged(); });
          var details = element("span", "input-file-details");
          details.append(element("strong", "", pathFor(file)), element("small", "", (index === context.primaryIndex ? "Primary · " : "Auxiliary · ") + file.size + " bytes"));
          item.append(radio, details); fileList.appendChild(item);
        });
      }
      function choose() { input.click(); }
      function changed() { context.setFiles(Array.from(input.files || [])); context.ensurePrimary(); refresh(); context.filesChanged(); }
      function folderChanged() { context.setFiles(Array.from(folderInput.files || [])); context.ensurePrimary(); refresh(); context.filesChanged(); }
      function chooseFolder() { folderInput.click(); }
      button.addEventListener("click", choose); input.addEventListener("change", changed);
      if (folderButton) folderButton.addEventListener("click", chooseFolder);
      if (folderInput) folderInput.addEventListener("change", folderChanged);
      refresh();
      return {
        refresh: refresh,
        readValue: function () { return context.orderedFiles().map(pathFor); },
        validate: function () {
          var files = context.files(); var errors = [];
          fileError.hidden = true; fileError.textContent = "";
          if (!files.length && !context.sequence()) errors.push("Choose an input file or provide a sequence.");
          if (files.length > context.form.file_input.max_files) errors.push("Too many input files selected.");
          if (files.some(function (file) { return !matchesExtension(file, context.form.file_input.extensions); })) errors.push("One or more files has an unsupported extension.");
          if (files.length && !matchesExtension(files[context.primaryIndex], context.form.file_input.primary_extensions)) errors.push("Choose a supported primary input.");
          if (errors.length) { button.setAttribute("aria-invalid", "true"); fileError.textContent = errors[0]; fileError.hidden = false; }
          return errors;
        },
        destroy: function () {
          button.removeEventListener("click", choose); input.removeEventListener("change", changed);
          if (folderButton) folderButton.removeEventListener("click", chooseFolder);
          if (folderInput) folderInput.removeEventListener("change", folderChanged);
        }
      };
    }
  });

  registry.register({
    id: "sequence",
    mount: function (target, definition, context) {
      var name = element("input", "text-input"); name.type = "text"; name.placeholder = "Sequence name";
      var textarea = element("textarea", "sequence-input"); textarea.placeholder = "Paste protein sequence letters (A-Z)";
      var preview = element("pre", "preview", sequenceSummary(""));
      var seqError = element("p", "param-error"); seqError.id = "sequence_error"; seqError.hidden = true;
      target.append(name, textarea, preview, seqError);
      context.sequenceNameInput = name; context.sequenceInput = textarea;
      function refresh() { textarea.removeAttribute("aria-invalid"); seqError.hidden = true; seqError.textContent = ""; preview.textContent = sequenceSummary(context.sequence()); context.changed(); }
      textarea.addEventListener("input", refresh); name.addEventListener("input", context.changed);
      return {
        readValue: function () { return { name: name.value.trim(), sequence: context.sequence() }; },
        validate: function () {
          var errors = [];
          if (context.sequence() && context.files().length) errors.push("Use either the pasted sequence or uploaded FASTA files, not both.");
          if (!context.sequence() && !context.files().length) errors.push("Enter a sequence or choose a FASTA file.");
          if (errors.length) { textarea.setAttribute("aria-invalid", "true"); seqError.textContent = errors[0]; seqError.hidden = false; }
          return errors;
        },
        destroy: function () { textarea.removeEventListener("input", refresh); name.removeEventListener("input", context.changed); }
      };
    }
  });

  registry.register({
    id: "structure",
    mount: function (target, definition, context) {
      var status = element("p", "structure-status", "Choose a PDB or mmCIF file to inspect it locally.");
      var chains = element("div", "structure-chain-list");
      var residues = element("select", "text-input structure-residue-select"); residues.multiple = true; residues.hidden = true;
      target.append(status, chains, residues);
      var generation = 0;
      // ponytail: generation guard prevents stale DOM writes but doesn't
      // cancel in-flight file.text() reads. If large local files (>50 MiB)
      // cause noticeable UI jank during rapid primary switches, upgrade to
      // AbortController.
      function refresh() {
        generation += 1; var current = generation;
        var file = context.primaryFile();
        chains.replaceChildren(); residues.replaceChildren(); residues.hidden = true; context.structure = null;
        if (!file || !matchesExtension(file, [".pdb", ".cif", ".mmcif"])) {
          status.textContent = "Choose a PDB or mmCIF primary file to inspect it locally."; return;
        }
        status.textContent = "Reading " + pathFor(file) + "…";
        file.text().then(function (text) {
          if (current !== generation) return;
          var parsed = lowerName(file).endsWith(".pdb") ? parsePdb(text) : parseCif(text);
          context.structure = parsed;
          status.textContent = pathFor(file) + " · " + parsed.atoms + " coordinate records · " + parsed.residues.length + " residues";
          parsed.chains.forEach(function (chain) {
            if (definition.options && definition.options.select_chains) {
              var label = element("label", "structure-chain");
              var checkbox = element("input"); checkbox.type = "checkbox"; checkbox.value = chain;
              checkbox.addEventListener("change", context.changed);
              label.append(checkbox, document.createTextNode(" Chain " + chain)); chains.appendChild(label);
            } else {
              chains.appendChild(element("span", "structure-chain", "Chain " + chain));
            }
          });
          if (definition.options && definition.options.select_residues && parsed.residues.length) {
            parsed.residues.slice(0, 5000).forEach(function (residue) {
              var option = element("option", "", residue.id + " · " + residue.name); option.value = residue.id; residues.appendChild(option);
            });
            residues.hidden = false;
          }
          context.changed();
        }).catch(function () { status.textContent = "This structure could not be read locally; the runner will validate it."; });
      }
      context.structureSelections = function () { return Array.from(residues.selectedOptions || []).map(function (option) { return option.value; }); };
      context.structureChains = function () { return Array.from(chains.querySelectorAll("input:checked")).map(function (input) { return input.value; }); };
      residues.addEventListener("change", context.changed);
      return { refresh: refresh, readValue: function () { return { selected_chains: context.structureChains(), selected_residues: context.structureSelections() }; }, destroy: function () { generation += 1; } };
    }
  });

  registry.register({
    id: "regions",
    mount: function (target, definition, context) {
      var fields = (definition.options && definition.options.fields) || [];
      var params = context.form.params.filter(function (param) { return fields.includes(param.name); });
      params.forEach(function (parameter) { target.appendChild(renderParam(parameter, context)); });
      if (definition.options && definition.options.source &&
          definition.options.syntax === "rfdiffusion" && fields.includes("hotspot_res")) {
        var insert = element("button", "btn btn-soft btn-small", "Set selected residues as hotspots"); insert.type = "button";
        insert.addEventListener("click", function () {
          var selected = context.structureSelections ? context.structureSelections() : [];
          var control = document.getElementById("param_hotspot_res");
          if (!control || !selected.length) return context.status("Select one or more structure residues first.", "error");
          control.value = "[" + selected.join(",") + "]";
          control.dispatchEvent(new Event("input", { bubbles: true }));
        });
        target.appendChild(insert);
      }
      return {
        readValue: function () { return fields.reduce(function (values, name) { var input = document.getElementById("param_" + name); if (input) values[name] = input.value; return values; }, {}); },
        validate: function () { return validateParameters(params); }
      };
    }
  });

  registry.register({
    id: "parameters",
    mount: function (target, definition, context) {
      var regionFields = new Set();
      context.capabilities.forEach(function (capability) {
        if (capability.plugin === "regions") ((capability.options && capability.options.fields) || []).forEach(function (name) { regionFields.add(name); });
      });
      var params = context.form.params.filter(function (parameter) { return !regionFields.has(parameter.name); });
      var basic = params.filter(function (parameter) { return !parameter.advanced; });
      var advanced = params.filter(function (parameter) { return Boolean(parameter.advanced); });
      basic.forEach(function (parameter) { target.appendChild(renderParam(parameter, context)); });
      if (advanced.length) {
        var details = element("details", "advanced-params");
        details.appendChild(element("summary", "", "Advanced parameters (" + advanced.length + ")"));
        var grid = element("div", "advanced-params-grid");
        advanced.forEach(function (parameter) { grid.appendChild(renderParam(parameter, context)); });
        details.appendChild(grid); target.appendChild(details);
      }
      if (!params.length) target.appendChild(element("p", "muted", "This task has no adjustable parameters."));
      return {
        readValue: function () { return context.paramValues(); },
        validate: function () { return validateParameters(params); }
      };
    }
  });

  registry.register({
    id: "review",
    mount: function (target, definition, context) {
      var summary = element("dl", "submission-review"); target.appendChild(summary);
      function refresh() {
        var files = context.orderedFiles(); var params = context.paramValues();
        var resources = context.form.resources || {};
        var resourceText = resources.cpus
          ? resources.cpus + " CPU · " + resources.memory + " · " + Math.ceil(resources.max_runtime_seconds / 60) + " min" + (resources.gres ? " · " + resources.gres : "")
          : (context.form.gpus ? "GPU task (resolved at submission)" : "CPU task (resolved at submission)");
        summary.replaceChildren();
        [["Task", context.form.display_name], ["Runtime", context.form.runtime_family], ["Inputs", files.length ? files.map(pathFor).join(", ") : (context.sequence() ? "Pasted FASTA sequence" : "None")], ["Parameters", Object.keys(params).length ? Object.keys(params).length + " configured" : "Defaults only"], ["Resources", resourceText]].forEach(function (row) {
          summary.append(element("dt", "", row[0]), element("dd", "", row[1]));
        });
      }
      return { refresh: refresh, readValue: function () { return { task_type: context.form.name, files: context.orderedFiles().map(pathFor), params: context.paramValues() }; } };
    }
  });

  function InputWorkspace(root, options) {
    this.root = root; this.options = options; this.form = null; this.primaryIndex = 0;
    this.context = null;
    this.host = new Core.PluginHost(registry, root, {
      createTarget: function (definition) {
        var card = workspaceCard(definition); root.appendChild(card.section); return card.body;
      },
      onUnsupported: function (definition) { options.status("Unsupported input component: " + definition.plugin, "error"); }
    });
  }

  InputWorkspace.prototype.mount = function (formDefinition) {
    var workspace = this; this.form = formDefinition; this.primaryIndex = 0;
    this.options.fileInput.value = "";
    var selectedFiles = [];
    var capabilities = formDefinition.input_workspace && formDefinition.input_workspace.capabilities;
    if (!capabilities || !capabilities.length) throw new Error("Task form has no input workspace capabilities");
    this.context = {
      form: formDefinition,
      capabilities: capabilities,
      fileInput: this.options.fileInput,
      primaryIndex: 0,
      files: function () { return selectedFiles.slice(); },
      setFiles: function (files) { selectedFiles = Array.from(files || []); },
      primaryFile: function () { return this.files()[this.primaryIndex] || null; },
      ensurePrimary: function () {
        var files = this.files(); var primary = formDefinition.file_input.primary_extensions;
        if (!files[this.primaryIndex] || !matchesExtension(files[this.primaryIndex], primary)) {
          var index = files.findIndex(function (file) { return matchesExtension(file, primary); }); this.primaryIndex = index < 0 ? 0 : index;
        }
      },
      orderedFiles: function () {
        var files = this.files(); if (!files.length || this.primaryIndex === 0) return files;
        return [files[this.primaryIndex]].concat(files.filter(function (_, index) { return index !== workspace.context.primaryIndex; }));
      },
      sequence: function () { return normalizeSequence(this.sequenceInput ? this.sequenceInput.value : ""); },
      paramValues: function () {
        var values = {};
        formDefinition.params.forEach(function (parameter) { var input = document.getElementById("param_" + parameter.name); if (input && input.value !== "") values[parameter.name] = input.value; });
        return values;
      },
      status: this.options.status,
      changed: function () {
        workspace.host.instances.forEach(function (mounted) {
          if (mounted.definition.plugin === "review" && typeof mounted.instance.refresh === "function") mounted.instance.refresh();
        });
      },
      filesChanged: function () {
        workspace.host.instances.forEach(function (mounted) {
          if (["structure", "review"].includes(mounted.definition.plugin) && typeof mounted.instance.refresh === "function") mounted.instance.refresh();
        });
      }
    };
    this.host.mount(capabilities, this.context); this.host.refresh();
  };

  InputWorkspace.prototype.files = function () { return this.context ? this.context.orderedFiles() : []; };
  InputWorkspace.prototype.sequence = function () { return this.context ? this.context.sequence() : ""; };
  InputWorkspace.prototype.sequenceName = function () { return this.context && this.context.sequenceNameInput ? this.context.sequenceNameInput.value : ""; };
  InputWorkspace.prototype.paramValues = function () { return this.context ? this.context.paramValues() : {}; };
  InputWorkspace.prototype.validate = function () { return this.host.validate(); };
  InputWorkspace.prototype.refresh = function () { this.host.refresh(); };
  InputWorkspace.prototype.destroy = function () { this.host.destroy(); this.context = null; };

  global.REvoComputeInputWorkspace = Object.freeze({ InputWorkspace: InputWorkspace, registry: registry });
})(window);
