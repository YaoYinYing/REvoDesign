/* REvoCompute — contract tests for plugin host, input workspace, and result previews */
/* SPDX-License-Identifier: GPL-3.0-only */
/* Run: node server/tests/js/test_contracts.js */

"use strict";

// ---------------------------------------------------------------------------
// minimal DOM shim — just enough surface for the plugin hosts to run
// ---------------------------------------------------------------------------

function fakeNode(tag) {
  var node = {
    _tag: tag || "div",
    className: "",
    textContent: "",
    id: "",
    htmlFor: "",
    type: "",
    value: "",
    checked: false,
    selected: false,
    disabled: false,
    hidden: false,
    placeholder: "",
    multiple: false,
    accept: "",
    min: "",
    max: "",
    step: "",
    required: false,
    href: "",
    download: "",
    dataset: {},
    children: [],
    childNodes: [],
    _listeners: {},
    _attributes: {},
    appendChild: function (child) { this.children.push(child); this.childNodes.push(child); return child; },
    append: function () {
      for (var i = 0; i < arguments.length; i++) this.appendChild(arguments[i]);
    },
    replaceChildren: function () { this.children = []; this.childNodes = []; },
    remove: function () {},
    querySelector: function (_sel) { return null; },
    querySelectorAll: function (_sel) { return []; },
    addEventListener: function (event, fn) {
      if (!this._listeners[event]) this._listeners[event] = [];
      this._listeners[event].push(fn);
    },
    removeEventListener: function (event, fn) {
      var list = this._listeners[event];
      if (list) this._listeners = list.filter(function (f) { return f !== fn; });
    },
    dispatchEvent: function (event) {
      var list = this._listeners[event.type] || [];
      list.forEach(function (fn) { fn(event); });
    },
    click: function () { this.dispatchEvent({ type: "click", bubbles: true }); },
    setAttribute: function (name, value) { this._attributes[name] = value; },
    getAttribute: function (name) { return this._attributes[name] || null; },
    removeAttribute: function (name) { delete this._attributes[name]; },
    cloneNode: function () { return fakeNode(this._tag); },
    closest: function (_sel) { return null; },
    classList: {
      add: function () {},
      remove: function () {},
      toggle: function () {},
      contains: function () { return false; }
    },
    style: {},
    checkValidity: function () {
      if (this.required && !String(this.value).trim()) return false;
      return true;
    },
    get validationMessage() { return this.checkValidity() ? "" : "invalid value"; }
  };
  return node;
}

var mockDocument = fakeNode("document");
mockDocument.createElement = function (tag) { return fakeNode(tag); };
mockDocument.createTextNode = function (text) { var n = fakeNode("#text"); n.textContent = text; return n; };
mockDocument.getElementById = function (_id) { return null; };
mockDocument.querySelector = function (_sel) { return null; };
mockDocument.querySelectorAll = function (_sel) { return []; };

var mockWindow = {
  document: mockDocument,
  location: { assign: function () {}, href: "" },
  URL: { createObjectURL: function () { return "blob:mock"; }, revokeObjectURL: function () {} },
  DataTransfer: function DataTransfer() { this.items = { add: function () {} }; this.files = []; },
  File: function File(_parts, _name, _opts) { this.name = _name; this.webkitRelativePath = ""; },
  FormData: function FormData() { this._data = []; this.append = function (k, v) { this._data.push([k, v]); }; },
  Event: function Event(type) { this.type = type; this.bubbles = true; },
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout,
  Promise: Promise,
  Object: Object,
  Array: Array,
  String: String,
  Number: Number,
  Boolean: Boolean,
  Map: Map,
  Set: Set,
  Math: Math,
  JSON: JSON,
  Error: Error,
  TypeError: TypeError,
  fetch: function () { return Promise.reject(new Error("fetch not available in test")); },
  REvoDesignAuth: { getToken: function () { return "test-token"; }, authFetch: function () { return Promise.reject(new Error("no authFetch")); } },
  REvoDesignTheme: { initToggle: function () {} }
};

// ---------------------------------------------------------------------------
// load source modules into the mock window
// ---------------------------------------------------------------------------

var fs = require("fs");
var path = require("path");

var jsDir = path.resolve(__dirname, "../../revocompute/static/js");

function loadSourceInto(filename, target) {
  var code = fs.readFileSync(path.join(jsDir, filename), "utf8");
  // Modules pass window to IIFE; supply global/window/document aliases so
  // bare document references inside the IIFE resolve.
  var wrapped = new Function("global", "window", "document", code);
  wrapped(target, target, target.document);
}

loadSourceInto("plugin-host.js", mockWindow);
loadSourceInto("result-preview-plugins.js", mockWindow);
loadSourceInto("input-workspace.js", mockWindow);

var PluginRegistry = mockWindow.REvoComputePlugins.PluginRegistry;
var PluginHost = mockWindow.REvoComputePlugins.PluginHost;
var ResultPreviews = mockWindow.REvoComputeResultPreviews;
var InputWorkspace = mockWindow.REvoComputeInputWorkspace;

// ---------------------------------------------------------------------------
// assert helper
// ---------------------------------------------------------------------------

var passed = 0, failed = 0;

function assert(condition, message) {
  if (condition) { passed += 1; }
  else { failed += 1; console.error("FAIL: " + message); }
}

function assertEqual(actual, expected, message) {
  if (actual === expected) { passed += 1; }
  else { failed += 1; console.error("FAIL: " + message + " (got " + JSON.stringify(actual) + ", expected " + JSON.stringify(expected) + ")"); }
}

function assertDeepEqual(actual, expected, message) {
  var a = JSON.stringify(actual), b = JSON.stringify(expected);
  if (a === b) { passed += 1; }
  else { failed += 1; console.error("FAIL: " + message + " (got " + a + ", expected " + b + ")"); }
}

function assertThrows(fn, pattern, message) {
  try { fn(); failed += 1; console.error("FAIL: " + message + " (did not throw)"); }
  catch (e) {
    if (e.message && e.message.indexOf(pattern) >= 0) { passed += 1; }
    else { failed += 1; console.error("FAIL: " + message + " (wrong error: " + e.message + ")"); }
  }
}

// ===================================================================
// PluginRegistry tests
// ===================================================================

(function () {
  console.log("--- PluginRegistry ---");

  var registry = new PluginRegistry("test");
  assert(registry instanceof PluginRegistry, "constructs");
  assertEqual(registry.kind, "test", "stores kind");

  registry.register({ id: "alpha", mount: function () {} });
  assert(registry.get("alpha") !== null, "register and get");
  assertEqual(registry.get("nope"), null, "get unknown returns null");

  assertThrows(function () { registry.register({ id: "", mount: function () {} }); }, "non-empty id", "rejects empty id");
  assertThrows(function () { registry.register({ id: "alpha", mount: function () {} }); }, "Duplicate", "rejects duplicate id");
  assertThrows(function () { registry.register({ id: "bad" }); }, "mount() or render()", "rejects plugin without mount/render");

  // resolve by explicit plugin field
  var found = registry.resolve({ plugin: "alpha" });
  assert(found !== null, "resolve by plugin field");

  // resolve by supports
  registry.register({ id: "beta", mount: function () {}, supports: function (s) { return s && s.role === "special"; } });
  var found2 = registry.resolve({ role: "special" });
  assert(found2 !== null && found2.id === "beta", "resolve by supports");
  var found3 = registry.resolve({ role: "normal" });
  assert(found3 === null || found3.id === "alpha", "resolve fallback when no supports match");
})();

// ===================================================================
// PluginHost tests
// ===================================================================

(function () {
  console.log("--- PluginHost ---");

  var registry = new PluginRegistry("host-test");
  var order = [];

  registry.register({ id: "first", mount: function (target) { order.push("first"); return { id: "first-inst" }; } });
  registry.register({ id: "second", mount: function (target) { order.push("second"); return { id: "second-inst", destroy: function () { order.push("second-destroy"); } }; } });

  var root = fakeNode("div");
  var host = new PluginHost(registry, root);

  var defs = [{ plugin: "first", id: "first" }, { plugin: "second", id: "second" }];
  var instances = host.mount(defs);
  assertEqual(instances.length, 2, "mounts two plugins");
  assertDeepEqual(order, ["first", "second"], "mounts in definition order");

  host.destroy();
  assertDeepEqual(order, ["first", "second", "second-destroy"], "destroy in reverse order, skips plugins without destroy");
  assertEqual(root.children.length, 0, "clearRoot replaces children by default");
})();

// ===================================================================
// PluginHost collect and validate
// ===================================================================

(function () {
  console.log("--- PluginHost collect/validate ---");

  var registry = new PluginRegistry("collect-test");
  registry.register({
    id: "collector",
    mount: function () {
      return {
        readValue: function () { return { count: 42 }; },
        validate: function () { return []; }
      };
    }
  });
  registry.register({
    id: "invalid",
    mount: function () {
      return {
        readValue: function () { return {}; },
        validate: function () { return ["bad input", "also bad"]; }
      };
    }
  });

  var host = new PluginHost(registry, fakeNode("div"));
  host.mount([{ plugin: "collector", id: "collector" }, { plugin: "invalid", id: "invalid" }]);

  var values = host.collect();
  assertDeepEqual(values, { collector: { count: 42 }, invalid: {} }, "collect gathers readValue from all plugins");

  var errors = host.validate();
  assert(errors.length >= 2, "validate aggregates errors");
  assert(errors.indexOf("bad input") >= 0, "validate includes first error");
})();

// ===================================================================
// PluginHost onUnsupported and createTarget
// ===================================================================

(function () {
  console.log("--- PluginHost services ---");

  var registry = new PluginRegistry("service-test");
  registry.register({ id: "present", mount: function (target) { target.textContent = "mounted"; return {}; } });

  var unsupportedLog = [];
  var host = new PluginHost(registry, fakeNode("div"), {
    onUnsupported: function (def) { unsupportedLog.push(def.plugin); },
    createTarget: function (def) { var n = fakeNode("section"); n.dataset.capabilityId = def.id; return n; }
  });

  host.mount([{ plugin: "present", id: "cap-1" }, { plugin: "missing", id: "cap-2" }]);

  assertEqual(unsupportedLog.length, 1, "calls onUnsupported for missing plugin");
  assertEqual(unsupportedLog[0], "missing", "onUnsupported receives definition");
  assertEqual(host.instances.length, 1, "only mounts resolved plugins");
  assertEqual(host.instances[0].target.dataset.capabilityId, "cap-1", "createTarget receives definition");
  assertEqual(host.instances[0].target.textContent, "mounted", "mount still writes to target");
})();

// ===================================================================
// ResultPreviewHost tests
// ===================================================================

(function () {
  console.log("--- ResultPreviewHost ---");

  var registry = ResultPreviews.createRegistry({
    structure: function () { return Promise.resolve(); },
    image: function () { return Promise.resolve(); },
    table: function () { return Promise.resolve(); },
    text: function (_artifact, stage) { stage.textContent = "text preview"; return Promise.resolve(); }
  });

  assert(registry.get("structure") !== null, "createRegistry registers structure preview");
  assert(registry.get("image") !== null, "createRegistry registers image preview");
  assert(registry.get("table") !== null, "createRegistry registers table preview");
  assert(registry.get("text") !== null, "createRegistry registers text preview");

  var stage = fakeNode("div");
  var beforeClearCalls = [];
  var host = new ResultPreviews.ResultPreviewHost(registry, stage, {
    beforeClear: function () { beforeClearCalls.push(1); }
  });

  // supports-based resolution
  var structurePlugin = registry.resolve({ preview: "structure" });
  assert(structurePlugin !== null && structurePlugin.id === "structure", "resolve structure by preview field");

  var unknownPlugin = registry.resolve({ preview: "unknown" });
  assert(unknownPlugin === null || unknownPlugin.id !== "unknown", "no match for unknown preview type");

  // size guard
  assert(structurePlugin.maxBytes === 64 * 1024 * 1024, "structure max 64 MiB");
  assertEqual(registry.get("image").maxBytes, 32 * 1024 * 1024, "image max 32 MiB");

  // byte-limit enforcement: check maxBytes is accessible on plugin
  var tooBig = { path: "big.pdb", preview: "structure", size: 128 * 1024 * 1024, url: "/fake" };
  var resolvedPlugin = registry.resolve(tooBig);
  assert(resolvedPlugin !== null, "artifact resolves to plugin");
  assert(resolvedPlugin.maxBytes !== null && tooBig.size > resolvedPlugin.maxBytes, "oversized artifact detected");

  // generation guard = destroy cancels stale renders
  host.destroy();
  assert(beforeClearCalls.length >= 1, "destroy calls beforeClear");
  assertEqual(stage.children.length, 0, "destroy clears stage");

  // second destroy is idempotent
  beforeClearCalls = [];
  host.generation = 0;
  host.destroy();
  assertEqual(stage.children.length, 0, "double destroy is harmless");
})();

// ===================================================================
// Input workspace helpers — pure functions from the module
// ===================================================================

(function () {
  console.log("--- Input workspace pure helpers ---");

  // Access internal helpers via a temporary mount
  // pathFor
  var fakeFile1 = { name: "model.pdb", webkitRelativePath: "nested/model.pdb" };
  var fakeFile2 = { name: "seq.fasta", webkitRelativePath: "" };

  // We can test through the workspace's public API
  var root = fakeNode("div");
  var ws = new InputWorkspace.InputWorkspace(root, {
    fileInput: fakeNode("input"),
    status: function () {}
  });

  // mount a gremlin-like form
  ws.mount({
    name: "gremlin", display_name: "PSSM-GREMLIN", runtime_family: "gremlin", gpus: false,
    file_input: { accept: ".fasta", extensions: [".fasta"], primary_extensions: [".fasta"], label: "FASTA", required: true, multiple: false, max_files: 1 },
    params: [],
    input_workspace: { version: 1, capabilities: [
      { plugin: "files", id: "source_files", title: "FASTA", options: { roles: ["primary"], primary_required: true } },
      { plugin: "review", id: "submission_review", title: "Review", options: {} }
    ]}
  });

  assertEqual(ws.files().length, 0, "empty workspace has no files");
  assertEqual(ws.sequence(), "", "empty workspace has no sequence");
  assertDeepEqual(ws.paramValues(), {}, "empty workspace has no params");

  // destroy
  ws.destroy();
  assertEqual(ws.context, null, "destroy clears context");
})();

// ===================================================================
// Plugin failure isolation
// ===================================================================

(function () {
  console.log("--- Plugin failure isolation ---");

  var registry = new PluginRegistry("isolation-test");
  registry.register({
    id: "stable",
    mount: function () { return { readValue: function () { return "ok"; } }; }
  });
  registry.register({
    id: "flaky",
    mount: function () {
      return {
        readValue: function () { throw new Error("plugin crash"); }
      };
    }
  });

  var host = new PluginHost(registry, fakeNode("div"));
  host.mount([{ plugin: "stable", id: "stable" }, { plugin: "flaky", id: "flaky" }]);

  // collect — flaky plugin should not kill host
  var values;
  try { values = host.collect(); } catch (_e) {
    assert(false, "collect should not throw even if a plugin crashes");
  }
  assert(values !== undefined, "collect returns object");
})();

// ===================================================================
// Summary
// ===================================================================

console.log("");
console.log(passed + " passed, " + failed + " failed");
process.exit(failed > 0 ? 1 : 0);
