# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


from REvoDesign.basic import SingletonAbstract


class ServerControl(SingletonAbstract):
    def singleton_init(self, name=None):
        """
        Initializes the server control instance.
        """
        self.name = name
        self.run_state = False

    def on(self):
        """Turn on the server."""
        self.run_state = True

    def off(self):
        """Turn off the server."""
        self.run_state = False

    def status(self):
        """Get the current run state of the server."""
        return self.run_state


def test_initialize_creates_instance():
    """
    Test that initialize creates a singleton instance when none exists.
    """
    ServerControl.reset_instance()
    ServerControl.initialize(name="Server A")
    server = ServerControl()

    assert server.name == "Server A", "Instance should be initialized with the provided name."
    assert isinstance(server, ServerControl), "Instance should be of type ServerControl."
    assert id(server) == id(ServerControl()), "The instance IDs should match for singleton behavior."


def test_initialize_updates_instance():
    """
    Test that initialize updates attributes of an existing singleton instance.
    """
    ServerControl.reset_instance()
    ServerControl.initialize(name="Server A")
    server = ServerControl()

    # Update the name attribute
    ServerControl.initialize(name="Updated Server A")
    assert server.name == "Updated Server A", "Existing instance should be updated with the new name."
    assert id(server) == id(ServerControl()), "The instance ID should remain the same."


def test_initialize_does_not_reinitialize():
    """
    Test that initialize does not reinitialize the instance if it already exists.
    """
    ServerControl.reset_instance()
    ServerControl.initialize(name="Server A")
    server = ServerControl()

    # Call initialize with no changes
    ServerControl.initialize()
    assert server.name == "Server A", "Instance should retain its name if no updates are provided."
    assert server is ServerControl(), "Singleton instance should remain the same."
    assert id(server) == id(ServerControl()), "The instance ID should remain unchanged."


def test_reset_and_reinitialize():
    """
    Test that resetting the instance allows reinitialization with new attributes.
    """
    ServerControl.reset_instance()
    ServerControl.initialize(name="Server A")
    server = ServerControl()
    first_instance_id = id(server)

    ServerControl.reset_instance()
    ServerControl.initialize(name="New Server A")
    new_server = ServerControl()

    assert new_server is not server, "Resetting should create a new instance."
    assert new_server.name == "New Server A", "New instance should be initialized with the new name."
    assert isinstance(new_server, ServerControl), "New instance should be of type ServerControl."
    assert id(new_server) != first_instance_id, "The instance ID should change after reset."
