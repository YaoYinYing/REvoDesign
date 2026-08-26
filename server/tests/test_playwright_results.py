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


def _open_result_page(page: Page) -> None:
    html = _task_results_html()
    manifest = _manifest()
    pdb = "ATOM      1  CA  GLY A  28      10.000  10.000  10.000  1.00 20.00           C\nEND\n"
    shell = """<script>
    parent.postMessage({type: 'shell-ready'}, '*');
    window.addEventListener('message', function (event) {
      if (event.data.type === 'structure') parent.postMessage({type: 'ready', requestId: event.data.requestId}, '*');
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
    page.route("https://revocompute.example/compute/api/results/*", lambda route: route.fulfill(json=manifest))
    page.route(
        "https://revocompute.example/compute/viewer-shell",
        lambda route: route.fulfill(content_type="text/html", body=shell),
    )
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


def test_result_page_collapses_workspace_at_mobile_width(page: Page) -> None:
    page.set_viewport_size({"width": 560, "height": 900})
    _open_result_page(page)
    columns = page.locator(".result-workspace").evaluate("node => getComputedStyle(node).gridTemplateColumns")
    assert " " not in columns.strip()
    assert page.locator(".preview-workspace").evaluate(
        """node => node.compareDocumentPosition(document.querySelector('.decision-rail')) &
        Node.DOCUMENT_POSITION_FOLLOWING"""
    )
