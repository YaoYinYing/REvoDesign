import os
from dataclasses import dataclass
from typing import Union
from .. import issues
@dataclass(frozen=True)
class FileExtension:
    ext: str
    description: str
    @property
    def filter_string(self) -> str:
        return f"{self.description} ( *.{self.ext} )"
@dataclass(frozen=True)
class FileExtensionCollection:
    extensions: tuple[FileExtension, ...]
    def __add__(self, extension_collection: 'FileExtensionCollection') -> 'FileExtensionCollection':
        return FileExtensionCollection(tuple(set(self.extensions + extension_collection.extensions)))
    def __contains__(self, extension: Union[FileExtension, str]) -> bool:
        if isinstance(extension, FileExtension):
            return extension in self.extensions
        return extension in [e.ext for e in self.extensions]
    @property
    def list_all(self) -> list[str]:
        return [e.ext for e in self.extensions]
    @property
    def list_dot_ext(self) -> list[str]:
        return [f".{e.ext}" for e in self.extensions]
    def match(self, ext: Union[FileExtension, str]) -> bool:
        if isinstance(ext, FileExtension):
            return ext in self.extensions
        if not ext.startswith('.'):
            return ext in self.list_all
        return ext in self.list_dot_ext
    @classmethod
    def squeeze(cls, exts: tuple['FileExtensionCollection', ...]) -> 'FileExtensionCollection':
        ec = []
        for e in exts:
            for _e in e.extensions:
                if _e in ec:
                    continue
                ec.append(_e)
        return cls(tuple(ec))
    @property
    def filter_string(self) -> str:
        return ";;".join([e.filter_string for e in self.extensions])
    def basename_stem(self, fname: str):
        fname = os.path.basename(fname)
        matched = [ext for ext in self.list_dot_ext if fname.endswith(ext)]
        if len(matched) == 1:
            return fname[:-len(matched[0])]
        if len(matched) > 1:
            matched_ext = sorted(matched, key=lambda x: len(x), reverse=True)[0]
            return fname[:-len(matched_ext[0])]
        raise issues.InternalError(
            f'Unexpect error in file extension collection: {fname} does not match any extension of {self.list_dot_ext}')
    @classmethod
    def from_dict(cls, dic: dict, prefix: str = '') -> 'FileExtensionCollection':
        return cls(tuple([FileExtension(d[0], f'{prefix}{d[1].lstrip("*.")}') for d in dic.items()]))