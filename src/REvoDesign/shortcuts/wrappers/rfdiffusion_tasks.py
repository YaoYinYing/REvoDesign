


from REvoDesign.shortcuts.tools.rfdiffusion_tasks import (RFDIFFUSION_CONFIG_DIR,
                                       list_all_config_preset,
                                       list_all_rfd_models,
                                       run_general_rfdiffusion_task,
                                       visualize_substrate_potentials)



from REvoDesign.shortcuts.utils import DialogWrapperRegistry

# Initialize the registry for the 'rfdiffusion' category
registry = DialogWrapperRegistry("rfdiffusion")

# Register the Substrate Potential Visualizer
wrapped_visualize_substrate_potentials = registry.register(
    "visualize_substrate_potentials",
    visualize_substrate_potentials
)

# Register the General RFdiffusion Task
wrapped_general_rfdiffusion_task = registry.register(
    "general_rfdiffusion_task",
    run_general_rfdiffusion_task
)
