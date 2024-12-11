# SingletonAbstract: A Versatile Singleton Implementation

The `SingletonAbstract` class provides a robust implementation of the Singleton design pattern in Python. It ensures that only one instance of the class is created, while also supporting dynamic derivation and flexible instance initialization or updates.

## Key Features

- **Singleton Pattern**: Ensures a single instance of the class.
- **Dynamic Derivation**: Allows developers to create derived singleton classes with independent instances.
- **Custom Initialization**: Subclasses define their initialization logic using the `singleton_init` method.
- **Update Variables**: Existing instances can be updated dynamically via the `initialize` method.
- **Reset Support**: Reset the singleton instance with `reset_instance`.

---

## Workflow: Life of Singleton

The following diagram represents the lifecycle of a singleton instance managed by `SingletonAbstract`.

[![](https://mermaid.ink/img/pako:eNqNVF1T4jAU_SuZvDjjoIMirfCwO9iq6xeugA-7xWFie4GMbcIkqYjAf980_YZ1Z_OUj3PuuffmJGvs8wBwF88EWczRyB0zpEfPc0IKTCFHnyKHhKFEQ8pmISjOeq9SCeKrF3R09G2THk4mDJaTyQZdrF0Oek2ZVIT5gC4_qFTft2ncC0Pp8w1yPEcAUYD6sEQ3OXhJ1RzJeAEij_iSEp2EiFyvJyWdsTpJ8VIug7sGfuklyelIlFE1maApF5pFFSUh_SSKcpbBLw38ynPm4L8hOkUHNIdBcIB6Sgn6GqusGJmxropirlMhmXfICBo5J5aKR39XvTaqP7whqC8FdW0jEUNN8RfIDbrxhm90sRMY3fMZ9V-qvc7AA1CxYGn-OsuiebVUbnNYcdW7uJv_wKVIGb-mlnJXjETURy4I-m6yTAHJeChsZkwUJBBAGp_rGZDR7Ff9YmJBgJyQSJkr6BCrCq1vaI-mu3V86U3d3T5nVbFHw_qZF7gnlkGBBXuFFlcBSF_88yJIss37Uio81Wsu7z01_yERM9lAh4dvy2RWSe3JpDb45_tKxqCw5TD3v3lJSbVZD3dutWQZt4y8LPlSpDCkTLPcS25oknv2Kk3Yf9gJBxEW7NNHqa--bu4AJKiac0vyXb2jIoHufggGZ0TujSO-8kBF-9bAH6qLuzHDDRyBiAgN9Ke5Tg7HWM0hgjHu6mkAUxKHaozHbKuhJFZ8uGI-7ir9ihtY8Hg2x90pCaVexabNLiW6xqjYXRD2m_Mop-gl7q7xB-4enXSax-1W0z61ztut8855p4FXeltPj1uW3bbsltU-sztn2wb-NBFOj0_aZy29a9nNjmXbVruBIaCKi4f01zef__YP1JLtqg?type=png)](https://mermaid.live/edit#pako:eNqNVF1T4jAU_SuZvDjjoIMirfCwO9iq6xeugA-7xWFie4GMbcIkqYjAf980_YZ1Z_OUj3PuuffmJGvs8wBwF88EWczRyB0zpEfPc0IKTCFHnyKHhKFEQ8pmISjOeq9SCeKrF3R09G2THk4mDJaTyQZdrF0Oek2ZVIT5gC4_qFTft2ncC0Pp8w1yPEcAUYD6sEQ3OXhJ1RzJeAEij_iSEp2EiFyvJyWdsTpJ8VIug7sGfuklyelIlFE1maApF5pFFSUh_SSKcpbBLw38ynPm4L8hOkUHNIdBcIB6Sgn6GqusGJmxropirlMhmXfICBo5J5aKR39XvTaqP7whqC8FdW0jEUNN8RfIDbrxhm90sRMY3fMZ9V-qvc7AA1CxYGn-OsuiebVUbnNYcdW7uJv_wKVIGb-mlnJXjETURy4I-m6yTAHJeChsZkwUJBBAGp_rGZDR7Ff9YmJBgJyQSJkr6BCrCq1vaI-mu3V86U3d3T5nVbFHw_qZF7gnlkGBBXuFFlcBSF_88yJIss37Uio81Wsu7z01_yERM9lAh4dvy2RWSe3JpDb45_tKxqCw5TD3v3lJSbVZD3dutWQZt4y8LPlSpDCkTLPcS25oknv2Kk3Yf9gJBxEW7NNHqa--bu4AJKiac0vyXb2jIoHufggGZ0TujSO-8kBF-9bAH6qLuzHDDRyBiAgN9Ke5Tg7HWM0hgjHu6mkAUxKHaozHbKuhJFZ8uGI-7ir9ihtY8Hg2x90pCaVexabNLiW6xqjYXRD2m_Mop-gl7q7xB-4enXSax-1W0z61ztut8855p4FXeltPj1uW3bbsltU-sztn2wb-NBFOj0_aZy29a9nNjmXbVruBIaCKi4f01zef__YP1JLtqg)

---

## Usage Example

### Define a Subclass

```python
class ServerControl(SingletonAbstract):
    def singleton_init(self, name=None):
        self.name = name
        self.run_state = False

    def on(self):
        self.run_state = True

    def off(self):
        self.run_state = False

    def status(self):
        return self.run_state
```

### Create and Use Singleton Instances

```python
# Initialize the singleton
ServerControl.initialize(name="Server A")
server_a = ServerControl()

print(server_a.name)  # Output: Server A

# Update the instance
ServerControl.initialize(name="Updated Server A")
print(server_a.name)  # Output: Updated Server A

# Reset the instance
ServerControl.reset_instance()
ServerControl.initialize(name="New Server A")
new_server_a = ServerControl()

print(new_server_a.name)  # Output: New Server A
```

### Dynamic Derivation

The `derive` method in `SingletonAbstract` allows you to dynamically create new classes with independent singleton behavior. Each derived class manages its own singleton instance, enabling clean separation between different singletons while leveraging shared logic.

#### How It Works

```python
@classmethod
def derive(cls: Type[T], name: str) -> Type[T]:
    """
    Dynamically creates a derived class with independent singleton behavior.

    Args:
        name: The name of the derived class.

    Returns:
        A dynamically created subclass with singleton behavior.
    """
    class DerivedSingleton(cls):
        _instance = None  # Independent instance tracking for the derived class

        def __init__(self, *args, **kwargs):
            if not hasattr(self, 'initialized'):
                self.singleton_init(*args, **kwargs)
                self.initialized = True

    DerivedSingleton.__name__ = name
    return cast(Type[T], DerivedSingleton)
```

#### Example Usage

```python
# Dynamically create derived singleton classes
ServerAController = ServerControl.derive("ServerAController")
ServerBController = ServerControl.derive("ServerBController")

# Use the derived singletons
server_a = ServerAController(name="Server A")
server_b = ServerBController(name="Server B")

print(server_a.name)  # Output: Server A
print(server_b.name)  # Output: Server B

# Confirm they are independent
assert server_a is not server_b, "Each derived singleton should manage its own instance."
```

This functionality makes `SingletonAbstract` flexible and extensible, enabling dynamic creation of distinct singleton types for various use cases.
