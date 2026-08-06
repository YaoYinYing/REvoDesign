# SingletonAbstract: A Versatile Singleton Implementation

The `SingletonAbstract` class provides a reusable Singleton implementation. It ensures that only one instance of each concrete class is created and supports explicit initialization, updates, and reset.

## Key Features

- **Singleton Pattern**: Ensures a single instance of the class.
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
