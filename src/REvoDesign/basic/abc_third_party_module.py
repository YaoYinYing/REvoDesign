# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Abstract Third-Party module.
"""

from REvoDesign.citations import CitableModuleAbstract


class ThirdPartyModuleAbstract(CitableModuleAbstract):
    """
    Abstract class for third-party modules.

    Attributes:
        name (str): The name of the third-party module.
        installed (bool): A flag indicating whether the module is installed.
        __bibtex__ (dict): A dictionary containing the BibTeX entries for the module.
    """

    name: str = ""
    installed: bool = False


class TorchModuleAbstract:
    """
    An abstract class for managing PyTorch modules on different devices.

    Args:
        device (str): The device on which the module will run, e.g., "cuda", "mps".
        **kwargs: Additional keyword arguments for future extensions or subclass-specific parameters.
    """

    def __init__(self, device: str, **kwargs):
        """
        Initializes the TorchModuleAbstract instance with the specified device.

        Args:
            device (str): The device on which the module will run, e.g., "cuda", "mps".
            **kwargs: Additional keyword arguments.
        """
        self.device = device
        ...

    def cleanup(self):
        """
        Cleans up the memory cache on the specified device if it is a CUDA or MPS device.

        This method checks the device type and clears the respective memory cache using PyTorch's utility functions.
        It prints a confirmation message after cleaning up the memory.
        """
        import torch

        # Clear the memory cache based on the device type
        if self.device.startswith("cuda"):
            torch.cuda.empty_cache()

        elif self.device.startswith("mps"):
            torch.mps.empty_cache()
        else:
            return

        print(f"Cleaned up {self.device} memory")
