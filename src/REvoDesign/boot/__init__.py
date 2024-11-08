import os
import hydra
from .post_installed import (WITH_DEPENDENCIES, experiment_config,
                             reload_config_file, save_configuration,
                             set_cache_dir, set_REvoDesign_config_file)


# 2. initialize config file
REVODESIGN_CONFIG_FILE = set_REvoDesign_config_file()
hydra.initialize_config_dir(
    version_base=None, config_dir=os.path.dirname(REVODESIGN_CONFIG_FILE)
)



# 7. initialize experiments directory, depending on config
EXPERIMENTS_CONFIG_DIR = experiment_config()

__all__ = [
    'experiment_config',
    'set_REvoDesign_config_file',
    'WITH_DEPENDENCIES',
    'reload_config_file',
    'set_cache_dir',
    'save_configuration',
    'REVODESIGN_CONFIG_FILE',
    'EXPERIMENTS_CONFIG_DIR'
]


