# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import Page, expect

STATIC = Path(__file__).resolve().parents[1] / "revocompute" / "static"
TEMPLATE = Path(__file__).resolve().parents[1] / "revocompute" / "templates" / "task_results.html"


def _task_results_html() -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("{{ static_version }}", "test")
    html = html.replace("{{ task.task_type }}", "easifa")
    html = html.replace("{{ task.fasta_fn }}", "enzyme.pdb")
    html = html.replace("{{ task.md5 }}", "0123456789abcdef0123456789abcdef")
    html = html.replace(
        "{{ task | tojson }}",
        json.dumps(
            {
                "task_type": "easifa",
                "fasta_fn": "enzyme.pdb",
                "md5": "0123456789abcdef0123456789abcdef",
                "status": "finished",
            }
        ),
    )
    return html


def _manifest() -> dict:
    artifacts = [
        {
            "path": "active_sites.csv",
            "size": 96,
            "sha256": "a" * 64,
            "media_type": "text/csv",
            "preview": "table",
            "role": "primary",
            "url": "/compute/api/results/task/artifacts/active_sites.csv",
        },
        {
            "path": "enzyme_structure.pdb",
            "size": 80,
            "sha256": "b" * 64,
            "media_type": "chemical/x-pdb",
            "preview": "structure",
            "role": "primary",
            "url": "/compute/api/results/task/artifacts/enzyme_structure.pdb",
        },
        {
            "path": "execution/slurm-job.stdout.log",
            "size": 10,
            "sha256": "c" * 64,
            "media_type": "text/plain",
            "preview": "text",
            "role": "diagnostic",
            "url": "/compute/api/results/task/artifacts/execution/slurm-job.stdout.log",
        },
    ]
    return {
        "schema_version": 3,
        "task_id": "0123456789abcdef0123456789abcdef",
        "task_type": "easifa",
        "status": "finished",
        "run": {
            "method": {
                "id": "easifa",
                "name": "EasIFA2 Active Sites",
                "summary": "Active-site annotation.",
                "output_summary": "Residue-level active-site annotations linked to the submitted enzyme structure.",
            },
            "inputs": [{"path": "enzyme.pdb", "sha256": "d" * 64}],
            "parameters": [{"name": "reaction_smiles", "label": "Reaction context", "value": "", "unit": ""}],
            "submitted_at": "2026-08-26T08:00:00+00:00",
            "started_at": "2026-08-26T08:01:00+00:00",
            "finished_at": "2026-08-26T08:02:00+00:00",
            "walltime_seconds": 60,
            "citations": [],
        },
        "output_check": {"state": "passed", "checks": [], "problems": []},
        "limitations": ["Predictions require biochemical interpretation."],
        "views": [
            {
                "id": "active_sites",
                "plugin": "entity-table",
                "role": "primary",
                "title": "Active-site mapping",
                "description": "Predicted active-site residues in the submitted enzyme structure.",
                "sources": {"table": ["active_sites.csv"], "structure": ["enzyme_structure.pdb"]},
                "mapping": {
                    "entity": "residue",
                    "key_columns": ["chain", "residue_index"],
                    "label_column": "site_name",
                    "chain_column": "chain",
                    "residue_column": "residue_index",
                    "numbering": "label_seq_id",
                    "evidence_columns": ["site_class", "probabilities"],
                },
            }
        ],
        "artifacts": artifacts,
        "total_size": sum(item["size"] for item in artifacts),
        "archive": {"ready": False, "request_url": "/archive", "download_url": None},
    }


def _add_protocol_fixtures(manifest: dict) -> None:
    fixtures = [
        ("confidence.json", "application/json", "text", 80),
        ("pae.json", "application/json", "text", 80),
        ("summary.json", "application/json", "text", 80),
        ("input.a3m", "application/octet-stream", "text", 40),
        ("topology.pdb", "chemical/x-pdb", "structure", 80),
        ("samples.xtc", "application/octet-stream", None, 24),
    ]
    for index, (path, media_type, preview, size) in enumerate(fixtures):
        manifest["artifacts"].append(
            {
                "path": path,
                "size": size,
                "sha256": chr(ord("d") + index) * 64,
                "media_type": media_type,
                "preview": preview,
                "role": "evidence",
                "url": f"/compute/api/results/task/artifacts/{path}",
            }
        )
    manifest["views"].extend(
        [
            {
                "id": "confidence",
                "plugin": "metric-series",
                "role": "evidence",
                "title": "Residue confidence",
                "description": "Per-residue confidence.",
                "sources": {"series": ["confidence.json"]},
                "mapping": {
                    "format": "json",
                    "value_path": "values",
                    "x_label": "Residue",
                    "y_label": "pLDDT",
                    "unit": "score",
                    "direction": "higher",
                    "missing": "null",
                    "y_min": 0,
                    "y_max": 100,
                },
            },
            {
                "id": "pae",
                "plugin": "matrix",
                "role": "evidence",
                "title": "Predicted aligned error",
                "description": "Pairwise error.",
                "sources": {"matrices": ["pae.json"]},
                "mapping": {
                    "format": "json",
                    "value_path": "values",
                    "x_label": "Aligned residue",
                    "y_label": "Scored residue",
                    "unit": "Å",
                    "direction": "lower",
                    "scale": "sequential",
                    "scale_min": 0,
                    "scale_max": 30,
                },
            },
            {
                "id": "summary",
                "plugin": "scalar-summary",
                "role": "evidence",
                "title": "Global confidence",
                "description": "Global confidence values.",
                "sources": {"data": ["summary.json"]},
                "mapping": {"fields": [{"path": "ptm", "label": "pTM", "unit": "score", "direction": "higher"}]},
            },
            {
                "id": "alignment",
                "plugin": "alignment",
                "role": "evidence",
                "title": "Input alignment",
                "description": "Aligned sequences.",
                "sources": {"alignment": ["input.a3m"]},
                "mapping": {"format": "a3m", "numbering": "sequence"},
            },
            {
                "id": "ensemble",
                "plugin": "trajectory",
                "role": "evidence",
                "title": "Conformational ensemble",
                "description": "Sampled conformations.",
                "sources": {"topology": ["topology.pdb"], "coordinates": ["samples.xtc"]},
                "mapping": {"coordinate_format": "xtc", "frame_unit": "sample", "timestep": 1, "association": "single"},
            },
        ]
    )
    manifest["total_size"] = sum(item["size"] for item in manifest["artifacts"])


def _open_result_page(page: Page, delay_second_viewer: bool = False, protocols: bool = False) -> None:
    page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
    html = _task_results_html()
    manifest = _manifest()
    if protocols:
        _add_protocol_fixtures(manifest)
    pdb = "ATOM      1  CA  GLY A  28      10.000  10.000  10.000  1.00 20.00           C\nEND\n"
    shell = """<script>
    parent.postMessage({type: 'shell-ready'}, '*');
    window.addEventListener('message', function (event) {
      if (event.data.type === 'structure') parent.postMessage({type: 'ready', requestId: event.data.requestId}, '*');
      if (event.data.type === 'trajectory') parent.postMessage({type: 'trajectory-ready', requestId: event.data.requestId, frame: 0, frameCount: 3}, '*');
      if (event.data.type === 'trajectory-control') parent.postMessage({type: 'trajectory-frame', frame: event.data.action === 'set' ? event.data.value : 1, frameCount: 3}, '*');
      if (event.data.type === 'select-residue') parent.postMessage({type: 'selected', payload: event.data}, '*');
      if (event.data.type === 'dispose') parent.postMessage({type: 'disposed'}, '*');
    });
    </script>"""
    page.route(
        "https://revocompute.example/compute/results/*",
        lambda route: route.fulfill(content_type="text/html", body=html),
    )
    page.route(
        "https://revocompute.example/static/js/*",
        lambda route: route.fulfill(
            content_type="application/javascript",
            body=(STATIC / "js" / route.request.url.split("/static/js/", 1)[1].split("?", 1)[0]).read_text(
                encoding="utf-8"
            ),
        ),
    )
    page.route(
        "https://revocompute.example/static/css/*",
        lambda route: route.fulfill(
            content_type="text/css",
            body=(STATIC / "css" / route.request.url.split("/static/css/", 1)[1].split("?", 1)[0]).read_text(
                encoding="utf-8"
            ),
        ),
    )
    page.route(
        "https://revocompute.example/compute/api/auth/token", lambda route: route.fulfill(json={"token": "test-token"})
    )
    page.route(
        "https://revocompute.example/compute/api/results/*/tables/active_sites.csv*",
        lambda route: route.fulfill(
            json={
                "columns": ["chain", "residue_index", "residue", "site_class", "site_name", "probabilities"],
                "rows": [["A", "28", "G", "active", "Binding site", "[0.1,0.9]"]],
                "offset": 0,
                "limit": 100,
                "has_more": False,
            }
        ),
    )
    page.route(
        "https://revocompute.example/compute/api/results/task/artifacts/enzyme_structure.pdb*",
        lambda route: route.fulfill(content_type="chemical/x-pdb", body=pdb),
    )
    page.route(
        "https://revocompute.example/compute/api/results/task/artifacts/confidence.json*",
        lambda route: route.fulfill(json={"values": [72, 84, 91]}),
    )
    page.route(
        "https://revocompute.example/compute/api/results/task/artifacts/pae.json*",
        lambda route: route.fulfill(json={"values": [[1, 8], [7, 2]]}),
    )
    page.route(
        "https://revocompute.example/compute/api/results/task/artifacts/summary.json*",
        lambda route: route.fulfill(json={"ptm": 0.82}),
    )
    page.route(
        "https://revocompute.example/compute/api/results/task/artifacts/input.a3m*",
        lambda route: route.fulfill(body=">query\nACDE\n>homolog\nAC-E\n"),
    )
    page.route(
        "https://revocompute.example/compute/api/results/task/artifacts/topology.pdb*",
        lambda route: route.fulfill(content_type="chemical/x-pdb", body=pdb),
    )
    page.route(
        "https://revocompute.example/compute/api/results/task/artifacts/samples.xtc*",
        lambda route: route.fulfill(content_type="application/octet-stream", body=b"mock-xtc"),
    )
    page.route("https://revocompute.example/compute/api/results/*", lambda route: route.fulfill(json=manifest))
    viewer_requests = 0

    def serve_viewer(route):
        nonlocal viewer_requests
        viewer_requests += 1
        body = "<script></script>" if delay_second_viewer and viewer_requests == 2 else shell
        route.fulfill(content_type="text/html", body=body)

    page.route("https://revocompute.example/compute/viewer-shell", serve_viewer)
    page.goto("https://revocompute.example/compute/results/0123456789abcdef0123456789abcdef")


def test_result_page_opens_principal_view_and_exports_shortlist(page: Page) -> None:
    _open_result_page(page)
    expect(page.get_by_text("EasIFA2 Active Sites")).to_be_visible()
    expect(page.get_by_text("Expected outputs found")).to_be_visible()
    expect(page.get_by_role("heading", name="Active-site mapping")).to_be_visible()
    expect(page.get_by_text("Binding site")).to_be_visible()

    page.get_by_label("Add Binding site · A:28 to shortlist").check()
    expect(page.locator("#shortlistCount")).to_have_text("1 selected")
    page.get_by_label("Add Binding site · A:28 to shortlist").uncheck()
    expect(page.locator("#shortlistCount")).to_have_text("0 selected")
    page.get_by_label("Add Binding site · A:28 to shortlist").check()
    with page.expect_download() as download:
        page.get_by_role("button", name="Export shortlist").click()
    assert download.value.suggested_filename == "shortlist.json"


def test_result_page_keeps_artifacts_fallback_and_native_space(page: Page) -> None:
    _open_result_page(page)
    all_artifacts = page.get_by_text("All artifacts and diagnostics")
    all_artifacts.click()
    search = page.get_by_label("Filter result artifacts")
    search.fill("stdout")
    search.press("Space")
    expect(search).to_have_value("stdout ")
    log_button = page.get_by_role("button", name="execution/slurm-job.stdout.log Execution log · 10 B")
    expect(log_button).to_be_visible()
    log_button.click()
    expect(page.get_by_role("heading", name="execution/slurm-job.stdout.log")).to_be_visible()
    expect(page.get_by_role("link", name="Download file")).to_be_visible()

    search.fill("enzyme_structure")
    page.locator(".artifact-row", has_text="enzyme_structure.pdb").click()
    expect(page.get_by_role("heading", name="enzyme_structure.pdb")).to_be_visible()
    expect(page.locator("iframe.artifact-molstar-preview")).to_be_visible()


def test_result_page_collapses_workspace_at_mobile_width(page: Page) -> None:
    page.set_viewport_size({"width": 560, "height": 900})
    _open_result_page(page)
    columns = page.locator(".result-workspace").evaluate("node => getComputedStyle(node).gridTemplateColumns")
    tracks = columns.strip().split()
    assert len(tracks) == 1 and tracks[0] != "none", columns
    assert page.locator(".preview-workspace").evaluate(
        """node => node.compareDocumentPosition(document.querySelector('.decision-rail')) &
        Node.DOCUMENT_POSITION_FOLLOWING"""
    )


def test_result_page_cancels_delayed_warm_viewer_on_artifact_switch(page: Page) -> None:
    _open_result_page(page, delay_second_viewer=True)
    expect(page.get_by_role("heading", name="Active-site mapping")).to_be_visible()
    page.get_by_text("All artifacts and diagnostics").evaluate("node => node.parentNode.open = true")
    page.locator(".artifact-row", has_text="enzyme_structure.pdb").evaluate("node => node.click()")
    expect(page.locator("iframe.artifact-molstar-preview")).to_have_count(1)
    page.locator(".artifact-row", has_text="execution/slurm-job.stdout.log").evaluate("node => node.click()")
    expect(page.get_by_role("heading", name="execution/slurm-job.stdout.log")).to_be_visible()
    expect(page.locator("iframe.artifact-molstar-preview")).to_have_count(0, timeout=3000)


def test_scientific_protocol_views_are_interactive_and_accessible(page: Page) -> None:
    _open_result_page(page, protocols=True)

    page.get_by_role("button", name="Residue confidence").click()
    expect(page.get_by_role("img", name="pLDDT by Residue")).to_be_visible()
    expect(page.get_by_text("Higher is favourable")).to_be_visible()

    page.get_by_role("button", name="Predicted aligned error").click()
    matrix = page.get_by_role("grid", name="Predicted aligned error; use arrow keys to inspect cells")
    matrix.focus()
    matrix.press("ArrowRight")
    expect(page.get_by_role("status").filter(has_text="Aligned residue 2")).to_be_visible()

    page.get_by_role("button", name="Global confidence").click()
    expect(page.get_by_text("0.82 score")).to_be_visible()

    page.get_by_role("button", name="Input alignment").click()
    expect(page.get_by_text("Columns use sequence numbering")).to_be_visible()

    page.get_by_role("button", name="Conformational ensemble").click()
    expect(page.get_by_label("Trajectory frame")).to_have_attribute("max", "2")
    page.get_by_role("button", name="Next").click()
    expect(page.get_by_text("2 / 3 · 1 sample")).to_be_visible()
