# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

import os
import sys
import types


def _install_fake_diffpack_modules(monkeypatch, tmp_path):
    captured: dict[str, object] = {
        "prepare_calls": [],
        "request": None,
        "backend_selected": None,
        "validate_calls": 0,
    }

    fake_util = types.ModuleType("diffpack.util")
    config_fp = tmp_path / "inference_confidence.yaml"
    config_fp.write_text("backend: native\n", encoding="utf-8")
    fake_util.get_default_config_path = lambda name="inference_confidence.yaml": str(config_fp)

    fake_schedule = types.ModuleType("diffpack.schedule_cache")

    def _validate(_cache_root):
        captured["validate_calls"] = int(captured["validate_calls"]) + 1
        if captured["validate_calls"] == 1:
            return {"errors": [{"pi": 3.1415, "errors": ["missing"]}]}
        return {"errors": []}

    def _prepare(cache_root, pi, force=False):
        captured["prepare_calls"].append((cache_root, pi, force))
        return {"status": "built"}

    fake_schedule.resolve_cache_root = lambda cache_root: str(tmp_path / "diffpack_cache")
    fake_schedule.validate_required_schedule_caches = _validate
    fake_schedule.prepare_schedule_cache = _prepare
    fake_schedule.required_schedule_pis = lambda: [3.1415, 1.5707]

    fake_backends = types.ModuleType("diffpack.backends")

    class FakeRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _FakeAdapter:
        def run_inference(self, request):
            captured["request"] = request
            output_fp = os.path.join(request.output_dir, os.path.basename(request.pdb_files[0]))
            os.makedirs(request.output_dir, exist_ok=True)
            with open(output_fp, "w", encoding="utf-8") as f:
                f.write("ATOM\n")
            return {"output_files": [output_fp]}

    def _get_backend_adapter(name):
        captured["backend_selected"] = name
        return _FakeAdapter()

    fake_backends.InferenceRequest = FakeRequest
    fake_backends.get_backend_adapter = _get_backend_adapter

    monkeypatch.setitem(sys.modules, "diffpack.util", fake_util)
    monkeypatch.setitem(sys.modules, "diffpack.schedule_cache", fake_schedule)
    monkeypatch.setitem(sys.modules, "diffpack.backends", fake_backends)
    return captured


def test_diffpack_runner_cache_prepare_and_request_and_rename(monkeypatch, tmp_path):
    captured = _install_fake_diffpack_modules(monkeypatch, tmp_path)

    monkeypatch.setattr(
        "REvoDesign.sidechain.mutate_runner.DiffPack.reload_config_file",
        lambda _: {
            "sidechain-solver": types.SimpleNamespace(
                inference=types.SimpleNamespace(
                    backend="native",
                    device="cpu",
                    config="inference_confidence.yaml",
                    hetero_policy="exclude",
                    fast=False,
                    memory_mode="quality",
                    cache_root="",
                )
            )
        },
    )

    from REvoDesign.sidechain.mutate_runner.DiffPack import DiffPack_worker

    runner = DiffPack_worker(pdb_file="input_wt.pdb", radius=0.0, use_model="pyg")
    mutant = types.SimpleNamespace(
        short_mutant_id="A1G_0.0",
        mutations=[types.SimpleNamespace(chain_id="A", wt_res="A", position=1, mut_res="G")],
    )

    output_fp = runner.run_mutate(mutant)
    req = captured["request"]

    assert captured["backend_selected"] == "pyg"
    assert len(captured["prepare_calls"]) == 2
    assert req is not None
    assert req.repack_radius == -1.0
    assert req.mutations == "AA1G"
    assert req.cache_read_only is True
    assert output_fp.endswith(f"{mutant.short_mutant_id}.pdb")
    assert os.path.exists(output_fp)


def test_diffpack_runner_parallel_caps_to_one_mutant_one_core(monkeypatch, tmp_path):
    _ = _install_fake_diffpack_modules(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "REvoDesign.sidechain.mutate_runner.DiffPack.reload_config_file",
        lambda _: {
            "sidechain-solver": types.SimpleNamespace(
                inference=types.SimpleNamespace(
                    backend="native",
                    device="cpu",
                    config="inference_confidence.yaml",
                    hetero_policy="exclude",
                    fast=False,
                    memory_mode="quality",
                    cache_root="",
                )
            )
        },
    )

    from REvoDesign.sidechain.mutate_runner.DiffPack import DiffPack_worker

    runner = DiffPack_worker(pdb_file="input_wt.pdb", radius=5.0)
    runner.run_mutate = lambda mutant: mutant.short_mutant_id  # type: ignore

    captured_n_jobs: dict[str, int | None] = {"value": None}

    class FakeParallel:
        def __init__(self, n_jobs, return_as):
            captured_n_jobs["value"] = n_jobs

        def __call__(self, tasks):
            return [func(*args, **kwargs) for func, args, kwargs in tasks]

    monkeypatch.setattr("REvoDesign.sidechain.mutate_runner.DiffPack.Parallel", FakeParallel)
    monkeypatch.setattr("REvoDesign.sidechain.mutate_runner.DiffPack.os.cpu_count", lambda: 4)

    mutants = [types.SimpleNamespace(short_mutant_id=f"M{i}") for i in range(10)]
    outputs = runner.run_mutate_parallel(mutants, nproc=99)

    assert captured_n_jobs["value"] == 4
    assert outputs == [m.short_mutant_id for m in mutants]
