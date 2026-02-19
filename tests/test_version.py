# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


from packaging import version

from REvoDesign import __version__


class TestVersionNumber:
    def test_current_version(self):
        version.parse(__version__)
