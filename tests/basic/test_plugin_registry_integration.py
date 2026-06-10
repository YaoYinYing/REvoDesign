# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from REvoDesign.clusters.cluster_sequence import (
    ALL_CLUSTER_METHOD_CLASSES,
    CLUSTER_METHOD_REGISTRY,
    IMPLEMENTED_CLUSTER_METHOD,
)
from REvoDesign.magician import ALL_DESIGNER_CLASSES, DESIGNER_REGISTRY, IMPLEMENTED_DESIGNERS
from REvoDesign.sidechain.sidechain_solver import ALL_RUNNER_CLASSES, IMPLEMENTED_RUNNER, RUNNER_REGISTRY


def test_sidechain_registry_compat_symbols_match():
    assert list(RUNNER_REGISTRY.all_classes) == ALL_RUNNER_CLASSES
    assert dict(RUNNER_REGISTRY.implemented_map) == dict(IMPLEMENTED_RUNNER)


def test_magician_registry_compat_symbols_match():
    assert list(DESIGNER_REGISTRY.all_classes) == ALL_DESIGNER_CLASSES
    assert dict(DESIGNER_REGISTRY.implemented_map) == dict(IMPLEMENTED_DESIGNERS)


def test_cluster_registry_compat_symbols_match():
    assert list(CLUSTER_METHOD_REGISTRY.all_classes) == ALL_CLUSTER_METHOD_CLASSES
    assert dict(CLUSTER_METHOD_REGISTRY.implemented_map) == dict(IMPLEMENTED_CLUSTER_METHOD)

