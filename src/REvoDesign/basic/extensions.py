'''
Data classes with file extensions used in the REvoDesign plugin.
'''
from dataclasses import dataclass
from typing import Union

from .. import issues


@dataclass(frozen=True)
class FileExtension:
    """
    Represents a file extension, including its technical details and human-readable description.

    Attributes:
        ext (str): The file extension, such as 'txt', 'md', etc.
        description (str): A brief description of the file type, such as 'Text File' or 'Markdown File'.
    """

    ext: str
    description: str

    @property
    def filter_string(self) -> str:
        """
        Generates a file filter string for this file extension.

        Returns:
            str: A file filter string in the format 'Description (*.[ext])', used in file dialog filters.
        """
        return f"{self.description} ( *.{self.ext} )"


@dataclass(frozen=True)
class FileExtensionCollection:
    """
    Represents a collection of file extensions, used to manage multiple file types.

    Attributes:
        extensions (tuple[FileExtension, ...]): A tuple containing a series of FileExtension objects.
    """

    extensions: tuple[FileExtension, ...]

    def __add__(self, extension_collection: 'FileExtensionCollection') -> 'FileExtensionCollection':
        return FileExtensionCollection(tuple(set(self.extensions + extension_collection.extensions)))

    def __contains__(self, extension: Union[FileExtension, str]) -> bool:
        """
        Check if the given extension is present in the current object's list of extensions.

        Parameters:
        - extension (Union[FileExtension, str]): The file extension to check, can be a FileExtension enum or a string.

        Returns:
        - bool: True if the extension is found in the current object's list of extensions, False otherwise.
        """
        # Check if the extension is a FileExtension enum and if it exists in the list of extensions
        if isinstance(extension, FileExtension):
            return extension in self.extensions
        # Check if the extension is a string and if it exists in the list of string representations of extensions
        return extension in [e.ext for e in self.extensions]

    @property
    def list_all(self) -> list[str]:
        """
        Returns a list of all file extensions.

        This property method iterates over the `self.extensions` list, extracting the 'ext' attribute from each extension object.
        """
        return [e.ext for e in self.extensions]

    @property
    def list_dot_ext(self) -> list[str]:
        """
        Returns a list of string extensions prefixed with a dot.

        Returns:
            list[str]: A list of string extensions, each prefixed with a dot.
        """
        # Generate the list of extensions with a leading dot
        return [f".{e.ext}" for e in self.extensions]

    def match(self, ext: Union[FileExtension, str]) -> bool:
        """
        Check if the given file extension matches any of the extensions in the current object's list.

        Parameters:
        ext (Union[FileExtension, str]): The file extension to check, can be a FileExtension enum or a string.

        Returns:
        bool: True if the extension matches, False otherwise.
        """
        # Check if ext is an instance of FileExtension
        if isinstance(ext, FileExtension):
            return ext in self.extensions

        # Check if ext is a string without a leading dot
        if not ext.startswith('.'):
            return ext in self.list_all

        # Check if ext is a string with a leading dot
        return ext in self.list_dot_ext

    @classmethod
    def squeeze(cls, exts: tuple['FileExtensionCollection', ...]) -> 'FileExtensionCollection':
        """
        Merge file extensions from multiple FileExtensionCollection instances and remove duplicates.

        This method takes a tuple of FileExtensionCollection instances and combines their extensions
        using set union operations to ensure that the resulting collection contains only unique extensions.

        Parameters:
        exts (tuple[FileExtensionCollection]): A tuple containing multiple FileExtensionCollection instances
                                            whose extensions are to be merged.

        Returns:
        FileExtensionCollection: A new FileExtensionCollection instance containing all unique extensions
                                from the input instances.
        """
        # Combine all extensions from each FileExtensionCollection instance using set union
        ec = []
        for e in exts:
            for _e in e.extensions:
                if _e in ec:
                    continue
                ec.append(_e)

        return cls(tuple(ec))

    @property
    def filter_string(self) -> str:
        """
        Generates a combined file filter string for all file extensions in the collection.

        Returns:
            str: A combined file filter string, with each file extension's filter string separated by ';;'.
        """
        return ";;".join([e.filter_string for e in self.extensions])
    

    def basename_stem(self, fname: str):
        """
        Extracts the stem (base name without extension) from a file name.

        Parameters:
        fname (str): The file name to extract the stem from.

        Returns:
        str: The base name (stem) of the file name without the extension.
        """
        matched=[ext for ext in self.list_dot_ext if fname.endswith(ext) ]
        if len(matched) ==1:
            return fname.rstrip(matched[0])
        
        if len(matched) > 1:
            # the longest win
            return fname.rstrip(sorted(matched, key=len, reverse=True)[0])

        # otherwise, raise no match error
        raise issues.InternalError(f'Unexpect error in file extension collection: {fname} does not match any extension of {self.list_dot_ext}')
