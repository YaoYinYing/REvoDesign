"""
Utils for fetching files from the internet

"""

import os
from dataclasses import dataclass
from urllib.parse import urljoin

import pooch
from platformdirs import user_data_dir

from REvoDesign import issues
from REvoDesign.citations import CitableModuleAbstract
from REvoDesign.tools.utils import extract_archive, get_cited

from ..logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


@dataclass(frozen=True)
class DownloadedFile:
    """
    Represents a downloaded file with its metadata

    Attributes:
        name (str): Name of the file
        version (Optional[str]): Version of the file, can be None
        url (str): Download URL of the file
        downloaded (str): Local path where the file is downloaded
        registry (Optional[str]): Registry information, defaults to None
    """

    name: str
    version: str | None
    url: str
    downloaded: str

    registry: str | None = None

    @property
    def flatten_dir(self) -> str:
        """
        Get or create the flatten directory path

        Creates directory if it doesn't exist, with name based on downloaded path plus '_flatten' suffix

        Returns:
            str: Path to the flatten directory
        """
        flatten_dir = f"{self.downloaded}_flatten/"
        os.makedirs(flatten_dir, exist_ok=True)
        return flatten_dir

    @property
    def flatten_archieve(self):
        """
        Extract archive file to flatten directory

        If flatten directory is empty, extracts the downloaded archive file to that directory
        and returns the list of extracted files

        Returns:
            List[str]: List of extracted file names
        """
        dist_dir = self.flatten_dir
        # Check if destination directory is empty, if so extract archive
        extracted_files: list[str] = os.listdir(dist_dir)
        if not extracted_files:
            print(f"Extracting {self.downloaded} to {dist_dir}")
            extract_archive(self.downloaded, dist_dir)

        extracted_files: list[str] = os.listdir(dist_dir)
        print(f"Extracted {extracted_files}")
        return extracted_files


class FileDownloadRegistry(CitableModuleAbstract):
    """
    A file download registry manager for handling remote file resources.

    This class implements automatic file downloading, verification, and cache management based on the pooch library.
    It supports specifying file hash values through a registry and provides convenient methods to fetch and verify remote files.

    :param name: Module name, used to construct the default data directory path.
    :param base_url: Base URL for remote files.
    :param registry: File registry where keys are filenames and values are corresponding hash values (optional).
    :param version: Optional version number for creating versioned data directories.
    :param customized_directory: Optional custom download directory path. If not provided, uses the default user data directory.
    :param alternative_base_urls: Optional list of alternative base URLs for downloading files.
    :param retry_count: Number of retries for downloading files.

    Retry mechanism:
        The function will run a nested loop to retry downloading files.
        It firstly tries to download files from the primary base URL.
        If the download fails, it will retry with the alternative base URLs if provided.
        For each base url, a certain number of retries will be attempted.

    """

    def __init__(
        self,
        name: str,
        base_url: str,
        registry: dict[str, str | None],
        version: str | None = None,
        alternative_base_urls: list[str] | None = None,
        customized_directory: str | None = None,
        retry_count: int = 5,
    ):
        self.name = name
        self.base_url = base_url
        self.alternative_base_urls = alternative_base_urls
        self.retry_count = retry_count
        self.version = version

        # Preprocess registry to ensure all hash values are in correct format
        self.registry = FileDownloadRegistry.preprocess_registry(registry=registry)

        # Set download directory, use default user data directory if not provided
        self.customized_directory = customized_directory or user_data_dir(
            self.name, version=self.version, ensure_exists=True
        )

        all_base_urls = [self.base_url]
        if self.alternative_base_urls:
            all_base_urls.extend(self.alternative_base_urls)

        self.pooches: list[pooch.Pooch] = []

        for base_url in all_base_urls:
            my_pooch = pooch.create(
                path=self.customized_directory,
                version=self.version,
                base_url=base_url,
                registry=self.registry,
                retry_if_failed=self.retry_count,
            )
            self.pooches.append(my_pooch)

    @staticmethod
    def _complete_varify_string(a_string: str | None = None, hash_type: str = "md5") -> str | None:
        """
        Complete hash string format, return directly if not provided or already contains type prefix.

        :param a_string: Original hash string.
        :param hash_type: Default hash type (e.g., 'md5').
        :return: Formatted hash string in 'type:value' format.
        """
        if not a_string:
            return None
        if ":" in a_string:
            return a_string
        return f"{hash_type}:{a_string}"

    @staticmethod
    def preprocess_registry(registry: dict[str, str | None]) -> dict[str, str | None]:
        """
        Preprocess registry to ensure all hash values conform to pooch requirements.

        :param registry: Original registry.
        :return: Processed registry.
        """
        return {k: FileDownloadRegistry._complete_varify_string(v) for k, v in registry.items()}

    @get_cited
    def setup(self, item: str) -> DownloadedFile:
        """
        Download and return the local path and related information of the specified file.

        :param item: Filename to download.
        :return: DownloadedFile object containing file information.
        :raises NetworkError: Raises network error exception if download fails.
        """
        for my_pooch in self.pooches:
            url = urljoin(self.base_url.rstrip("/") + "/", item)
            try:
                # each-base-url retry will be performed sequentially in pooch
                downloaded_path = my_pooch.fetch(item, progressbar=True)
            except Exception as e:
                logging.error(f"Failed to fetch {item}: {e}")
                # all retries failed, use the next base url
                continue

            # download succeeded and return early
            registry_entry = my_pooch.registry.get(item, None)
            return DownloadedFile(
                name=item, version=self.version, url=url, downloaded=downloaded_path, registry=registry_entry
            )

        # all retry attempts failed, raise an error
        raise issues.NetworkError(f"Failed to download {item}")

    @property
    def list_all_files(self) -> list[str]:
        """
        Get a list of all files in the registry.

        :return: List of filenames.
        """
        return self.pooches[0].registry_files

    def has(self, item: str) -> bool:
        """
        Check if the specified file exists in the registry.

        :param item: Filename.
        :return: True if exists, False otherwise.
        """
        return item in self.pooches[0].registry_files

    @staticmethod
    def prepare_registry_from_md5(md5_contents: str) -> dict[str, str | None]:
        """
        Parse and generate registry from MD5 content string.

        :param md5_contents: String containing MD5 values and filenames, each line in 'hash filename' format.
        :return: Parsed registry dictionary.
        """
        registry = {}
        for item in md5_contents.split("\n"):
            if not item:
                continue
            logging.debug(f"Processing item: {item}")
            parts = item.split()
            if len(parts) != 2:
                logging.warning(f"Skipping malformed line: {item}")
                continue
            hash_val, filename = parts
            registry[filename] = f"md5:{hash_val}"
        logging.debug(f"Registry: {registry}")
        return registry

    __bibtex__ = {
        "Pooch": """
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
