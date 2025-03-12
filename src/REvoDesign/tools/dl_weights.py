'''
Utils for fetching pretrained model weights
'''

import os
from dataclasses import dataclass
from functools import cached_property
from typing import Optional

import pooch
from platformdirs import user_cache_dir, user_data_dir

from REvoDesign.common import file_extensions as Fext
from REvoDesign.tools.utils import extract_archive


@dataclass(frozen=True)
class ModelFetchSetting:
    """
    Configuration class for fetching and managing a model.

    Attributes:
        name (str): The name of the model.
        version (str): The version of the model.
        url (str): The URL to download the model from.
        md5sum (str): The MD5 checksum used to verify the integrity of the downloaded file.
    """
    name: str
    version: str
    url: str
    md5sum: Optional[str]=None

    disable_unflatten: bool = False
    unflatten_to_dir: Optional[str] = None

    @cached_property
    def downloaded_basename(self):
        return os.path.basename(self.url)

    @cached_property
    def need_flatten(self):
        """
        Property to check if the model needs to be flattened.
        """
        return any(
            self.downloaded_basename.endswith(e) or self.downloaded_basename.endswith(e.upper())
            for e in Fext.Compressed.list_dot_ext
        ) and not self.disable_unflatten

    @property
    def basename(self):
        """
        Property to get the base filename of the model without the .zip extension.

        Returns:
            str: Base filename of the model.
        """
        if self.need_flatten:
            return Fext.Compressed.basename_stem(self.downloaded_basename)
        return self.downloaded_basename

    @property
    def weight_path(self):
        """
        Property to get the path where the model weights are stored.

        Returns:
            str: Path to the directory containing the model weights.
        """
        return os.path.join(
            user_data_dir(
                self.name,
                version=self.version,
                ensure_exists=True),
            self.unflatten_to_dir or self.basename)

    @property
    def ready(self):
        """
        Property to check if the model weights are already downloaded and available.

        Returns:
            bool: True if the model weights exist and are not empty, False otherwise.
        """
        if self.need_flatten:
            return os.path.exists(self.weight_path) and os.listdir(self.weight_path)
        return os.path.exists(self.weight_path) and os.path.isfile(self.weight_path)

    def flatten_archieve(self, downloaded: str):
        # Check if the destination directory is empty
        dist_dir = os.path.dirname(self.weight_path)
        expanded_dirs = os.listdir(dist_dir)
        if not expanded_dirs:
            print(f'Extracting {downloaded} to {dist_dir}')
            extract_archive(downloaded, dist_dir)

        extracted_files = os.listdir(dist_dir)
        print(f'Extracted {extracted_files}')
        return self.weight_path

    def setup(self):
        """
        Method to set up the model by downloading and extracting it if necessary.

        Returns:
            str: Path to the directory containing the model weights.
        """
        if self.ready:
            print(f'Already downloaded {self.basename} to {self.weight_path}')
            return self.weight_path

        print(f'Downloading {self.basename}...')
        downloaded = pooch.retrieve(
            self.url,
            known_hash=f'md5:{self.md5sum}' if self.md5sum else None,
            path=user_cache_dir(
                f'downloading_{self.name}_weights',
                ensure_exists=True) if self.need_flatten else os.path.dirname(self.weight_path),
            fname=self.basename,
            progressbar=True)

        if not self.need_flatten:
            return downloaded
        return self.flatten_archieve(downloaded)

    