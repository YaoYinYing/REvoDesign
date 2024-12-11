import pytest
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


def test_singleton_behavior():
    """
    Test that a singleton instance is created and reused.
    """
    ServerAController = ServerControl.derive("ServerAController")
    server_a1 = ServerAController(name="Server A")
    server_a2 = ServerAController()

    assert server_a1 is server_a2, "ServerAController should behave as a singleton."
    assert server_a1.name == "Server A", "Singleton instance should retain its name."
    assert hasattr(server_a1, "run_state"), "Singleton instance should have 'run_state' attribute."


def test_dynamic_derivation():
    """
    Test that dynamically derived singleton classes are independent.
    """
    ServerAController = ServerControl.derive("ServerAController")
    ServerBController = ServerControl.derive("ServerBController")

    server_a = ServerAController(name="Server A")
    server_b = ServerBController(name="Server B")

    assert server_a is not server_b, "ServerAController and ServerBController should have independent instances."
    assert server_a.name == "Server A", "ServerAController instance should retain its unique name."
    assert server_b.name == "Server B", "ServerBController instance should retain its unique name."


def test_instance_methods():
    """
    Test that instance methods work as expected.
    """
    ServerAController = ServerControl.derive("ServerAController")
    server_a = ServerAController(name="Server A")

    server_a.off()
    assert not server_a.status(), "ServerAController should be OFF after calling off()."

    server_a.on()
    assert server_a.status(), "ServerAController should be ON after calling on()."


def test_reset_instance():
    """
    Test that resetting the singleton instance works as expected.
    """
    ServerAController = ServerControl.derive("ServerAController")
    ServerBController = ServerAController.derive("ServerBController")
    ServerCController = ServerBController.derive("ServerCController")

    # Create an instance
    server_a = ServerAController(name="Server A")
    server_b = ServerBController(name="Server B")
    server_c = ServerCController(name="Server C")

    assert server_a is not server_b, "Server A and B should be different instances"
    assert server_b is not server_c, "Server B and C should be different instances"

    server_a.on()
    assert server_a.status(), "ServerAController should be ON after calling on()."
    assert not server_b.status(), "ServerBController should be OFF since we don't call on()."
    assert not server_c.status(), "ServerCController should be OFF since we don't call on()."
    
    # Reset instance
    ServerAController.reset_instance()

    assert ServerAController._instance is None, "Instance should be reset after calling reset_instance()."
    assert ServerBController._instance is not None, "Instance of B should not be reset after A calling reset_instance()."
    assert ServerCController._instance is not None, "Instance of C should not be reset after A calling reset_instance()."

    # Create a new instance and verify it is independent
    new_server_a = ServerAController(name="New Server A")

    assert new_server_a is not server_a, "Original server_a is now an orphan object and should not be used anymore."
    assert new_server_a.name == "New Server A", "New ServerAController instance should have the new name."
    assert not new_server_a.status(), "New ServerAController instance should be OFF by default."

    ServerAController.reset_instance()
    assert ServerAController._instance is None, "Instance of A should be reset after calling reset_instance() again."


@pytest.fixture
def reset_all_instances():
    """
    Fixture to reset all singleton instances before each test.
    """
    ServerControl.reset_instance()
    yield
    ServerControl.reset_instance()


@pytest.mark.usefixtures("reset_all_instances")
def test_reset_with_fixture():
    """
    Test singleton reset using a pytest fixture.
    """
    ServerAController = ServerControl.derive("ServerAController")
    ServerBController = ServerControl.derive("ServerBController")

    server_a = ServerAController(name="Server A")
    server_b = ServerBController(name="Server B")

    assert server_a.name == "Server A", "ServerAController instance should retain its unique name."
    assert server_b.name == "Server B", "ServerBController instance should retain its unique name."

    # Reset and ensure new instances are created
    ServerAController.reset_instance()
    ServerBController.reset_instance()

    new_server_a = ServerAController(name="New Server A")
    new_server_b = ServerBController(name="New Server B")

    assert new_server_a is not server_a, "ServerAController should have a new instance after reset."
    assert new_server_b is not server_b, "ServerBController should have a new instance after reset."
    assert new_server_a.name == "New Server A"
    assert new_server_b.name == "New Server B"
