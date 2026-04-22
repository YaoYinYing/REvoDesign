# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

import sys
import types


def test_dlpacker_pytorch_runner_policy_and_device_override(monkeypatch, tmp_path):
    from REvoDesign.sidechain.mutate_runner.DLPackerPytorch import DLPackerPytorch_worker

    model_init_args: dict[str, str | None] = {"device": None}
    dlpacker_init_args: dict[str, str | None] = {"rotamer_policy": None, "weights_filename": None}

    fake_pkg = types.ModuleType("dlpacker_pytorch")
    fake_utils = types.ModuleType("dlpacker_pytorch.utils")

    class FakeDLPModel:
        def __init__(self, device=None):
            model_init_args["device"] = device

    class FakeDLPacker:
        def __init__(self, str_pdb, model, weights_filename, rotamer_policy):
            dlpacker_init_args["rotamer_policy"] = rotamer_policy
            dlpacker_init_args["weights_filename"] = weights_filename

    fake_pkg.DLPacker = FakeDLPacker
    fake_utils.DLPModel = FakeDLPModel
    monkeypatch.setitem(sys.modules, "dlpacker_pytorch", fake_pkg)
    monkeypatch.setitem(sys.modules, "dlpacker_pytorch.utils", fake_utils)

    monkeypatch.setattr(
        "REvoDesign.sidechain.mutate_runner.DLPackerPytorch.reload_config_file",
        lambda _: {
            "sidechain-solver": types.SimpleNamespace(
                inference=types.SimpleNamespace(device="cpu", rotamer_policy="hybrid", weights_prefix="")
            )
        },
    )
    monkeypatch.setattr(
        "REvoDesign.sidechain.mutate_runner.DLPackerPytorch.set_cache_dir",
        lambda: str(tmp_path),
    )

    runner = DLPackerPytorch_worker(pdb_file="fake.pdb", use_model="tf")
    runner._build_worker()

    assert runner.rotamer_policy == "tf"
    assert model_init_args["device"] == "cpu"
    assert dlpacker_init_args["rotamer_policy"] == "tf"
    assert dlpacker_init_args["weights_filename"] == f"{tmp_path}/weights/DLPacker/DLPacker_weights"
