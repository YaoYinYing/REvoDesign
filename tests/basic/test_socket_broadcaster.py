# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from REvoDesign.clients.QtSocketConnector import Broadcaster


def test_received_decodes_each_message_stack_item():
    broadcaster = Broadcaster()
    stacked_messages = [
        broadcaster.compose_dict("hello", "Text"),
        broadcaster.compose_dict("client-id", "UUID"),
    ]
    packed_message = broadcaster.pack(broadcaster.compose_dict(stacked_messages, "MessageStack"))

    assert broadcaster.received(packed_message) == (
        "MessageStack",
        [{"Text": "hello"}, {"UUID": "client-id"}],
    )


def test_received_discards_message_stack_with_invalid_item_type():
    broadcaster = Broadcaster()
    invalid_item = broadcaster.compose_dict(42, "Text")
    packed_message = broadcaster.pack(broadcaster.compose_dict([invalid_item], "MessageStack"))

    assert broadcaster.received(packed_message) == (None, None)
