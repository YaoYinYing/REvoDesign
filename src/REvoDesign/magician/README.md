# Magician's Gimmick Orchestration Protocol (MGOP)

## Overview
The **Magician's Gimmick Orchestration Protocol (MGOP)** is a structured framework designed for dynamic management and initialization of "gimmicks" (external designers or scorers) in a singleton-driven environment of **REvoDesign**. MGOP ensures seamless setup, transition, and cooling-down processes for these gimmicks, while maintaining system robustness and flexibility.

[![](https://mermaid.ink/img/pako:eNqFVFFvmzAQ_iuWX5psENGQAEFrpU7dntan7GlCQg5ciFWw6dmoy9L0t88kUJoGGl7An7-773zf4R1NZAo0pEnOlLrnLENWRIKY5x4UzwTg3UppZIkm315su0M_Iy0TiYDfBygh-brUyEVGBCtgmLSSMidcKM3yHNILPHWQjKXItxeYJcLaMHP5DDhI_ZI22GhMFDxVIBKwjiLDMccaRi3_pag0E3p8IaxkWB8wj5vwcSSO3IMlXcTuiBLyrnk3V22dMbtq9z_24-YnyxW0u93BWqTTrVf79-KNkf3SjcRqWPg3Vj26xLZvCTKuQJEfiBI_LeSBZTzhTNwpxVXdT-Mj-WU-Xz_28rUblvhZ4mNrb2-GDPSoPsb4zJLToHpszjOQokFi1kI9YWdmZ7woePLYQ1Wgq9K0pgXbGXgj2bbsKSMkEpMN1Ok1qIHjnsTWA4egQOiGHglq0QKwYDw198DB6ojqDZhfk4bmM4U1q3Id0UjsDZVVWi63IqGhNu5aFGWVbWi4rmfMolWZmkqae-QNLZn4I-XJmoY7-peG7mzi-b7neK4fLGaeG3gW3Ro4mARTxw_mM9fzr10n2Fv03yGDM1m4c9-ZLxznejGdeo5vUUi5lvjQXGT1a_8fQdScCQ?type=png)](https://mermaid.live/edit#pako:eNqFVFFvmzAQ_iuWX5psENGQAEFrpU7dntan7GlCQg5ciFWw6dmoy9L0t88kUJoGGl7An7-773zf4R1NZAo0pEnOlLrnLENWRIKY5x4UzwTg3UppZIkm315su0M_Iy0TiYDfBygh-brUyEVGBCtgmLSSMidcKM3yHNILPHWQjKXItxeYJcLaMHP5DDhI_ZI22GhMFDxVIBKwjiLDMccaRi3_pag0E3p8IaxkWB8wj5vwcSSO3IMlXcTuiBLyrnk3V22dMbtq9z_24-YnyxW0u93BWqTTrVf79-KNkf3SjcRqWPg3Vj26xLZvCTKuQJEfiBI_LeSBZTzhTNwpxVXdT-Mj-WU-Xz_28rUblvhZ4mNrb2-GDPSoPsb4zJLToHpszjOQokFi1kI9YWdmZ7woePLYQ1Wgq9K0pgXbGXgj2bbsKSMkEpMN1Ok1qIHjnsTWA4egQOiGHglq0QKwYDw198DB6ojqDZhfk4bmM4U1q3Id0UjsDZVVWi63IqGhNu5aFGWVbWi4rmfMolWZmkqae-QNLZn4I-XJmoY7-peG7mzi-b7neK4fLGaeG3gW3Ro4mARTxw_mM9fzr10n2Fv03yGDM1m4c9-ZLxznejGdeo5vUUi5lvjQXGT1a_8fQdScCQ)

## Key Features
1. **Dynamic Gimmick Management**:
   - Supports initialization, pre-heating, and cooling-down of gimmicks based on input configurations.
   - Dynamically handles switching between different gimmicks without disrupting workflows.

2. **Singleton Pattern**:
   - Ensures that only one instance of the central `Magician` class exists, providing global access and consistency.

3. **Error Handling and Logging**:
   - Provides detailed error reporting for invalid configurations or initialization failures.
   - Logs all major events, such as gimmick transitions and configuration changes, for transparency and debugging.

4. **Separation of Concerns**:
   - Uses `MagicianAssistant` to offload the responsibilities of managing and initializing gimmicks, maintaining modularity.

## Components
### 1. MagicianAssistant
A utility class for managing third-party design tools wrappers (gimmicks):
- **Attributes**:
  - `installed_worker`: Dynamically populated list of installed and ready-to-use gimmicks.
- **Methods**:
  - `get(name, **kwargs)`: Retrieves and initializes the requested gimmick by its name.

### 2. Magician
The core singleton class responsible for overall gimmick management:
- **Attributes**:
  - `bus`: Configuration bus for retrieving runtime configuration data.
  - `gimmick`: The currently active gimmick.
  - `magician_assistant`: An instance of `MagicianAssistant` for handling gimmicks.
- **Methods**:
  - `singleton_init()`: Initializes the singleton instance.
  - `setup()`: Dynamically configures the gimmick based on input parameters and initializes it if necessary.

## Workflow
1. **Initialization**:
   - The `Magician` instance is automatically initialized as a singleton with `self.magician = Magician()`.
2. **Setup**:
   - Use `self.magician.setup(name_cfg_item="ui.interact.use_external_scorer")` to set up a specific gimmick.
3. **Using the Gimmick**:
   - If a gimmick is available, interact with it using:
     - `self.magician.gimmick.scorer(mutant=mutant_obj)` for scoring tasks.
     - `self.magician.gimmick.designer(**kwargs)` for design tasks.
4. **Cooling Down**:
   - To deactivate the gimmick, call `self.magician.setup()`.

## Example Usage
```python
# Initialize the singleton instance of Magician
self.magician = Magician()

# Setup a gimmick using a configuration item
self.magician.setup(name_cfg_item="ui.interact.use_external_scorer")

# Use the gimmick for scoring
self.magician.gimmick.scorer(mutant=mutant_obj)

# Use the gimmick for designing
self.magician.gimmick.designer(
    num=self.magician_num_samples,
    batch=self.batch,
    temperature=self.magician_temperature,
)

# Cool down the gimmick
self.magician.setup()  # cool it down
```

## Logging and Timing
- All major operations (e.g., gimmick transitions, initialization) are logged for debugging and monitoring purposes.
- Timing for operations like pre-heating is measured and logged to identify performance bottlenecks.

## Error Handling
MGOP uses custom error types to identify and handle issues:
- `KeyError`: Raised when an invalid gimmick name is provided.
- `DependencyError`: Raised for other initialization issues, with detailed context.

## Extensibility
- New gimmicks can be added by extending the `ExternalDesignerAbstract` class and registering them in `implemented_designers`.
- The protocol supports additional configuration sources through `ConfigBus`.

---

For any issues or questions, please contact the maintainer or raise an issue on the project repository.

