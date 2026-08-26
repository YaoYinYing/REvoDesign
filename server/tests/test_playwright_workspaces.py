# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, expect

STATIC_JS = Path(__file__).resolve().parents[1] / "revocompute" / "static" / "js"


def test_native_browser_mounts_and_collects_rfdiffusion_workspace(page: Page) -> None:
    page.set_content('<div id="root"></div><input id="files" type="file">')
    page.add_script_tag(path=STATIC_JS / "plugin-host.js")
    page.add_script_tag(path=STATIC_JS / "input-workspace.js")
    page.add_script_tag(path=STATIC_JS / "input-workspace-rfdiffusion.js")
    page.evaluate(
        """
        window.fetch = function () { return Promise.resolve({ok: true, json: function () {
          return Promise.resolve({summary: "normalized"});
        }}); };
        window.REvoDesignAuth = { authFetch: function (url, options) { return window.fetch(url, options); } };
        window.workspace = new window.REvoComputeInputWorkspace.InputWorkspace(
          document.getElementById("root"),
          {fileInput: document.getElementById("files"), status: function () {}}
        );
        window.workspace.mount({
          name: "rfdiffusion", display_name: "RFdiffusion", runtime_family: "placer-rfdiffusion",
          file_input: {accept: ".pdb", extensions: [".pdb"],
            primary_extensions: [".pdb"], multiple: true, max_files: 64},
          params: [
            {name: "design_mode", type: "str", default: "unconditional"},
            {name: "contig", type: "str", default: "100-100"},
            {name: "hotspot_res", type: "str", default: ""},
            {name: "diffuser_b_0", type: "float", default: 0.01, minimum: 0}
          ],
          input_workspace: {version: 3, steps: [
            {id: "material", title: "Input", description: "", capabilities: [
              {plugin: "files", id: "source_files", title: "Files", options: {primary_required: false}}
            ]},
            {id: "intent", title: "Intent", description: "", capabilities: [
              {plugin: "rfdiffusion-regions", id: "design_regions", title: "Regions", options: {
                syntax: "rfdiffusion", fields: ["design_mode", "contig", "hotspot_res"],
                modes: ["unconditional", "motif_scaffolding", "binder", "expert"]
              }}
            ]},
            {id: "review", title: "Review", description: "", capabilities: [
              {plugin: "review", id: "submission_review", title: "Review", options: {}}
            ]}
          ]}
        });
        """
    )
    expect(page.locator("[data-capability-id=design_regions] select")).to_be_visible()
    collected = page.evaluate("window.workspace.collect().design_regions")
    assert collected["mode"] == "unconditional"
    assert collected["segments"] == [{"kind": "generated", "min_length": 100, "max_length": 100}]
    # Fractional float defaults must satisfy native constraint validation
    # (a bare step=1 would flag 0.01 as a step mismatch).
    assert page.evaluate("window.workspace.validate()") == []


def test_semantic_steps_group_alternative_inputs_and_review(page: Page) -> None:
    page.set_content('<div id="root"></div><input id="files" type="file">')
    page.add_script_tag(path=STATIC_JS / "plugin-host.js")
    page.add_script_tag(path=STATIC_JS / "input-workspace.js")
    page.evaluate(
        """
        window.workspace = new window.REvoComputeInputWorkspace.InputWorkspace(
          document.getElementById("root"),
          {fileInput: document.getElementById("files"), status: function () {}}
        );
        window.workspace.mount({
          name: "example", display_name: "Example",
          file_input: {accept: ".fasta", extensions: [".fasta"], primary_extensions: [".fasta"],
            multiple: false, max_files: 1, max_request_bytes: 16777216},
          params: [],
          input_workspace: {version: 3, steps: [
            {id: "material", title: "Provide sequence", description: "", capabilities: [
              {plugin: "files", id: "source_files", title: "Files", options: {primary_required: true}},
              {plugin: "sequence", id: "sequence_editor", title: "Paste sequence", options: {}}
            ]},
            {id: "review", title: "Review", description: "", capabilities: [
              {plugin: "review", id: "submission_review", title: "Review", options: {}}
            ]}
          ]}
        });
        """
    )
    expect(page.locator(".protocol-step")).to_have_count(2)
    expect(page.locator("#protocol-step-material [data-capability-id=source_files]")).to_be_visible()
    expect(page.locator("#protocol-step-material [data-capability-id=sequence_editor]")).to_be_visible()
    page.get_by_label("Protein sequence").fill(">example\nACDEFG")
    assert page.evaluate("window.workspace.sequence()") == "ACDEFG"
    assert page.evaluate("window.workspace.validate()") == []


def test_structure_plugin_queues_structure_until_shell_ready(page: Page) -> None:
    """A structure selected before the viewer shell loads must not be lost.

    The route deliberately delays the shell page so the FileReader completes
    first — without the shell-ready handshake the structure postMessage lands
    before the shell installs its listener and is dropped.
    """

    def delayed_shell(route):
        route.fulfill(
            content_type="text/html",
            body=(
                "<script>"
                "window.addEventListener('message', function (e) { "
                "parent.postMessage({type: 'echo', payload: e.data}, '*'); });"
                "setTimeout(function () { parent.postMessage({type: 'shell-ready'}, '*'); }, 800);"
                "</script>"
            ),
        )

    # The page needs a real origin so the iframe's relative /compute/viewer-shell
    # resolves to a routable URL (about:blank cannot host relative iframe URLs).
    page.route(
        "https://revocompute.example/",
        lambda route: route.fulfill(
            content_type="text/html", body='<div id="root"></div><input id="files" type="file">'
        ),
    )
    page.route("**/compute/viewer-shell", delayed_shell)
    page.goto("https://revocompute.example/")
    page.add_script_tag(path=STATIC_JS / "plugin-host.js")
    page.add_script_tag(path=STATIC_JS / "input-workspace.js")
    page.evaluate(
        """
        window.__echoes = [];
        window.__shellReady = false;
        window.addEventListener("message", function (event) {
          if (event.data && event.data.type === "shell-ready") window.__shellReady = true;
          if (event.data && event.data.type === "echo") window.__echoes.push(event.data.payload);
        });
        window.workspace = new window.REvoComputeInputWorkspace.InputWorkspace(
          document.getElementById("root"),
          {fileInput: document.getElementById("files"), status: function () {}}
        );
        window.workspace.mount({
          name: "rfdiffusion", display_name: "RFdiffusion",
          runtime_family: "placer-rfdiffusion",
          file_input: {accept: ".pdb", extensions: [".pdb"],
            primary_extensions: [".pdb"], multiple: true, max_files: 64},
          params: [],
          input_workspace: {version: 3, steps: [
            {id: "material", title: "Input", description: "", capabilities: [
              {plugin: "files", id: "source_files", title: "Files", options: {primary_required: true}},
              {plugin: "structure", id: "structure_builder", title: "Structure", options: {source: "source_files", select_residues: true}}
            ]},
            {id: "review", title: "Review", description: "", capabilities: [
              {plugin: "review", id: "submission_review", title: "Review", options: {}}
            ]}
          ]}
        });
        """
    )
    page.set_input_files(
        "#files",
        {
            "name": "model.pdb",
            "mimeType": "chemical/x-pdb",
            "buffer": b"ATOM      1  CA  GLY A   1      10.000  10.000  10.000  1.00 20.00           C\nEND\n",
        },
    )
    # Yield through the synthetic shell's deliberate delay. Playwright's sync
    # route callbacks are dispatched during this browser wait.
    page.wait_for_timeout(1_000)
    assert page.evaluate("window.__shellReady") is True
    page.wait_for_function("window.__echoes.length > 0", timeout=10000)
    echoes = page.evaluate("window.__echoes")
    assert any(
        item.get("type") == "structure" and item.get("format") == "pdb" and item.get("selectionEnabled") is True
        for item in echoes
    )


def test_real_molstar_sequence_strip_reports_selected_residue(page: Page) -> None:
    """The pinned Mol* bundle selects sequence residues in input-workbench mode."""
    shell_source = (STATIC_JS / "viewer-shell.js").read_text(encoding="utf-8")
    shell_html = """<!doctype html><html><body>
      <div id="shellState">Waiting</div><div id="viewerHost" hidden></div>
      <script src="/static/js/viewer-shell.js"></script>
    </body></html>"""
    page.route(
        "https://revocompute.example/static/js/viewer-shell.js*",
        lambda route: route.fulfill(content_type="application/javascript", body=shell_source),
    )
    page.route(
        "https://revocompute.example/compute/viewer-shell*",
        lambda route: route.fulfill(content_type="text/html", body=shell_html),
    )
    page.goto("https://revocompute.example/compute/viewer-shell")
    page.evaluate(
        """
        window.__reports = [];
        window.addEventListener("message", function (event) {
          if (event.data && typeof event.data === "object") window.__reports.push(event.data);
        });
        """
    )
    pdb = (Path(__file__).resolve().parents[2] / "tests/data/pdb/2KL8.pdb").read_text(encoding="utf-8")
    page.evaluate(
        """
        text => window.postMessage({
          type: "structure", requestId: "sequence-probe", text: text,
          format: "pdb", label: "probe.pdb", selectionEnabled: true,
          showControls: true
        }, "*")
        """,
        pdb,
    )
    page.wait_for_function(
        'window.__reports.some(function (item) { return item.type === "ready"; })',
        timeout=90_000,
    )

    # Selection mode is enabled by the shell, so clicking residue 5 in the
    # sequence strip must update structure.selection and report it upstream.
    assert "msp-btn-link-toggle-on" in (page.get_by_title("Toggle Selection Mode").get_attribute("class") or "")
    page.locator(".msp-sequence-present").nth(4).click()
    page.wait_for_function(
        """
        window.__reports.some(function (item) {
          return item.type === "selection" && item.residues && item.residues.length > 0;
        })
        """,
        timeout=10_000,
    )
    selection = page.evaluate('window.__reports.filter(function (item) { return item.type === "selection"; }).at(-1)')
    assert selection["residues"] == [{"chain": "A", "auth_seq_id": 5, "label_seq_id": 5, "residue": 5}]


def test_linked_result_layout_collapses_at_mobile_width(page: Page) -> None:
    css = (STATIC_JS.parent / "css" / "task-results.css").read_text(encoding="utf-8")
    page.set_viewport_size({"width": 560, "height": 800})
    page.set_content(f"<style>{css}</style><div class='linked-result-layout'><div>A</div><div>B</div></div>")
    columns = page.locator(".linked-result-layout").evaluate("node => getComputedStyle(node).gridTemplateColumns")
    assert " " not in columns.strip()
