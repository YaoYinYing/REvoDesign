'''
Utils for fetching pretrained model weights
'''

import os
import zipfile
from dataclasses import dataclass

import pooch
from platformdirs import user_cache_dir, user_data_dir

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
    md5sum: str

    @property
    def basename(self):
        """
        Property to get the base filename of the model without the .zip extension.

        Returns:
            str: Base filename of the model.
        """
        return os.path.basename(self.url).rstrip('.zip')

    @property
    def weight_path(self):
        """
        Property to get the path where the model weights are stored.

        Returns:
            str: Path to the directory containing the model weights.
        """
        return os.path.join(user_data_dir(self.name, version=self.version, ensure_exists=True), self.basename)

    @property
    def ready(self):
        """
        Property to check if the model weights are already downloaded and available.

        Returns:
            bool: True if the model weights exist and are not empty, False otherwise.
        """
        return os.path.exists(self.weight_path) and os.listdir(self.weight_path)

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
            known_hash=f'md5:{self.md5sum}',
            path=user_cache_dir(
                f'downloading_{self.name}_weights',
                ensure_exists=True),
            progressbar=True)

        # Check if the destination directory is empty
        dist_dir = os.path.dirname(self.weight_path)
        expanded_dirs = os.listdir(dist_dir)
        if not expanded_dirs:
            print(f'Extracting {downloaded} to {dist_dir}')

            # Extract the zip file to the destination directory
            with zipfile.ZipFile(downloaded, mode="r") as z:
                z.extractall(path=dist_dir)

        extracted_files = os.listdir(dist_dir)
        print(f'Extracted {extracted_files}')
        return self.weight_path