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
          file_input: {accept: ".pdb", extensions: [".pdb"], primary_extensions: [".pdb"], multiple: true, max_files: 64},
          params: [
            {name: "design_mode", type: "str", default: "unconditional"},
            {name: "contig", type: "str", default: "100-100"},
            {name: "hotspot_res", type: "str", default: ""}
          ],
          input_workspace: {version: 2, capabilities: [
            {plugin: "files", id: "source_files", title: "Files", options: {primary_required: false}},
            {plugin: "rfdiffusion-regions", id: "design_regions", title: "Regions", options: {
              syntax: "rfdiffusion", fields: ["design_mode", "contig", "hotspot_res"],
              modes: ["unconditional", "motif_scaffolding", "binder", "expert"]
            }},
            {plugin: "review", id: "submission_review", title: "Review", options: {}}
          ]}
        });
        """
    )
    expect(page.locator("[data-capability-id=design_regions] select")).to_be_visible()
    collected = page.evaluate("window.workspace.collect().design_regions")
    assert collected["mode"] == "unconditional"
    assert collected["segments"] == [{"kind": "generated", "min_length": 100, "max_length": 100}]


def test_structure_plugin_queues_structure_until_shell_ready(page: Page) -> None:
    """A structure selected before the viewer shell loads must not be lost.

    The route deliberately delays the shell page so the FileReader completes
    first — without the shell-ready handshake the structure postMessage lands
    before the shell installs its listener and is dropped.
    """
    import time

    def delayed_shell(route):
        time.sleep(0.8)
        route.fulfill(
            content_type="text/html",
            body=(
                "<script>"
                "parent.postMessage({type: 'shell-ready'}, '*');"
                "window.addEventListener('message', function (e) { parent.postMessage({type: 'echo', payload: e.data}, '*'); });"
                "</script>"
            ),
        )

    # The page needs a real origin so the iframe's relative /compute/viewer-shell
    # resolves to a routable URL (about:blank cannot host relative iframe URLs).
    page.route(
        "https://revocompute.example/**",
        lambda route: route.fulfill(content_type="text/html", body="<html><body></body></html>"),
    )
    page.route("**/compute/viewer-shell", delayed_shell)
    page.goto("https://revocompute.example/")
    page.set_content('<div id="root"></div><input id="files" type="file">')
    page.add_script_tag(path=STATIC_JS / "plugin-host.js")
    page.add_script_tag(path=STATIC_JS / "input-workspace.js")
    page.evaluate(
        """
        window.__echoes = [];
        window.addEventListener("message", function (event) {
          if (event.data && event.data.type === "echo") window.__echoes.push(event.data.payload);
        });
        window.workspace = new window.REvoComputeInputWorkspace.InputWorkspace(
          document.getElementById("root"),
          {fileInput: document.getElementById("files"), status: function () {}}
        );
        window.workspace.mount({
          name: "rfdiffusion", display_name: "RFdiffusion", runtime_family: "placer-rfdiffusion",
          file_input: {accept: ".pdb", extensions: [".pdb"], primary_extensions: [".pdb"], multiple: true, max_files: 64},
          params: [],
          input_workspace: {version: 2, capabilities: [
            {plugin: "files", id: "source_files", title: "Files", options: {primary_required: true}},
            {plugin: "structure", id: "structure_builder", title: "Structure", options: {source: "source_files"}},
            {plugin: "review", id: "submission_review", title: "Review", options: {}}
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
    page.wait_for_function("window.__echoes.length > 0", timeout=10000)
    echoes = page.evaluate("window.__echoes")
    assert any(
        item.get("type") == "structure" and item.get("format") == "pdb" and item.get("selectionEnabled") is True
        for item in echoes
    )


def test_linked_result_layout_collapses_at_mobile_width(page: Page) -> None:
    css = (STATIC_JS.parent / "css" / "task-results.css").read_text(encoding="utf-8")
    page.set_viewport_size({"width": 560, "height": 800})
    page.set_content(f"<style>{css}</style><div class='linked-result-layout'><div>A</div><div>B</div></div>")
    columns = page.locator(".linked-result-layout").evaluate("node => getComputedStyle(node).gridTemplateColumns")
    assert " " not in columns.strip()
