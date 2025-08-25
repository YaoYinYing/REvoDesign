from REvoDesign.citations import CitableModuleAbstract
class ThirdPartyModuleAbstract(CitableModuleAbstract):
    name: str = ""
    installed: bool = False
class TorchModuleAbstract:
    def __init__(self, device: str, **kwargs):
        self.device = device
        ...
    def cleanup(self):
        import torch
        if self.device.startswith("cuda"):
            torch.cuda.empty_cache()
        elif self.device.startswith("mps"):
            torch.mps.empty_cache()
        else:
            return
        print(f"Cleaned up {self.device} memory")