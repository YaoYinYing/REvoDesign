'''
Utils for fetching pretrained model weights

'''

import os
from dataclasses import dataclass
from typing import List, Optional


import pooch
from platformdirs import  user_data_dir
from REvoDesign.citations import CitableModuleAbstract

from REvoDesign.tools.utils import extract_archive,get_cited

from ..logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


@dataclass(frozen=True)
class DownloadedFile:
    name: str
    version: Optional[str]
    url: str
    downloaded: str

    registry: Optional[str]=None

    @property
    def flatten_dir(self) -> str:
        dir=f'{self.downloaded}_flatten/'
        os.makedirs(dir, exist_ok=True)
        return dir
    
    @property
    def flatten_archieve(self):
        dist_dir=self.flatten_dir
        # Check if the destination directory is empty
        extracted_files: List[str] = os.listdir(dist_dir)
        if not extracted_files:
            print(f'Extracting {self.downloaded} to {dist_dir}')
            extract_archive(self.downloaded, dist_dir)

        extracted_files: List[str] = os.listdir(dist_dir)
        print(f'Extracted {extracted_files}')
        return extracted_files


class FileDownloadRegistry(CitableModuleAbstract):
    """
    Class for fetching and managing a model.

    Attributes:

    """
    def __init__(
            self, 
            name: str, 
            base_url: str, 
            registry: dict[str, Optional[str]], 
            version: Optional[str] = None,  
            customized_directory: Optional[str] = None):
        self.name =name
        self.base_url=base_url
        self.version=version

        self.registry=FileDownloadRegistry.preprocess_registry(registry=registry)

        self.customized_directory=customized_directory or user_data_dir(self.name, version=self.version, ensure_exists=True)

        self.pooch: pooch.Pooch = pooch.create(
            path=self.customized_directory,
            version=self.version,
            base_url=self.base_url,
            registry=self.registry,
            retry_if_failed=99,
            )
        
    @staticmethod
    def _complete_varify_string(a_string: Optional[str], hash_type: str='md5')-> Optional[str]:
        if not a_string:
            return None
        if ":" in a_string:
            return a_string
        return f"{hash_type}:{a_string}"
    @staticmethod
    def preprocess_registry(registry: dict[str, Optional[str]]) -> dict[str, Optional[str]]:

        return {k:FileDownloadRegistry._complete_varify_string(v) for k, v in registry.items()}
    
    @get_cited
    def setup(self, item:str) ->DownloadedFile:
        
        return DownloadedFile(
            name=item, 
            version=self.version, 
            url=os.path.join(self.base_url.rstrip('/'), item),
            downloaded=self.pooch.fetch(item,progressbar=True),
            registry=self.pooch.registry.get(item, None))
    
    @property
    def list_all_files(self) -> list[str]:
        """
        Returns:
        list[str]: A list of all items in the ExtrasGroups instance.
        """
        return self.pooch.registry_files
    
    def has(self, item: str) -> bool:
        return item in self.pooch.registry_files
    
    @staticmethod
    def prepare_registry_from_md5(md5_contents: str)->dict[str, Optional[str]]:
        registry = {}
        for item in md5_contents.split('\n'):
            if not item:
                continue
            logging.debug(f"Processing item: {item}")
            k, v = item.split()
            registry.update({v:f'md5:{k}'})
        logging.debug(f"Registry: {registry}")
        return registry

    __bibtex__ = {
        'Pooch': """
@article{uieda2020,
  title = {{Pooch}: {A} friend to fetch your data files},
  author = {Leonardo Uieda and Santiago Soler and R{\'{e}}mi Rampin and Hugo van Kemenade and Matthew Turk and Daniel Shapero and Anderson Banihirwe and John Leeman},
  year = {2020},
  doi = {10.21105/joss.01943},
  url = {https://doi.org/10.21105/joss.01943},
  month = jan,
  publisher = {The Open Journal},
  volume = {5},
  number = {45},
  pages = {1943},
  journal = {Journal of Open Source Software}
}
"""
    }