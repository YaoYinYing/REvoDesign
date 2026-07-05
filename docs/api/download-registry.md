# Download Registry

The download registry provides reliable file fetching with retry, mirror
fallback, hash verification, local caching, and extraction of compressed
archives. It is built on the [Pooch](https://www.fatiando.org/pooch/) library.

::: REvoDesign.tools.download_registry.FileDownloadRegistry
    options:
      show_root_heading: true
      show_source: false
      heading_level: 2

::: REvoDesign.tools.download_registry.DownloadedFile
    options:
      show_root_heading: true
      show_source: false
      heading_level: 2

## Usage Pattern

```python
from REvoDesign.tools.download_registry import FileDownloadRegistry

registry = FileDownloadRegistry(
    name="my_data",
    base_url="https://example.com/data/",
    registry={
        "file1.pdb": "md5:abc123def456",
        "file2.pkl": None,            # no hash verification
    },
    alternative_base_urls=["https://mirror.example.com/data/"],
    retry_count=3,
)

# Download with automatic retry and mirror fallback
result = registry.setup("file1.pdb")
print(result.downloaded)            # local path
print(result.url)                   # original URL
print(result.registry)              # hash string

# List available files
print(registry.list_all_files)

# Check if a file is in the registry
print(registry.has("file2.pkl"))

# Extract compressed archives
result.flatten_archive              # extracts to {path}_flatten/
```

## Retry Mechanism

The `FileDownloadRegistry.setup()` method implements a cascading retry
strategy:

1. For each base URL (primary first, then alternatives), Pooch's built-in
   retry mechanism is used (controlled by `retry_count`).
2. If all retries for a URL fail, the next alternative URL is tried.
3. If all URLs are exhausted, a `NetworkError` is raised.

## Process

The `setup()` method returns a `DownloadedFile` dataclass that includes the
local filesystem path. The archive extraction feature (`flatten_archive`) can
automatically unpack `.tar.gz` and `.zip` archives into a `_flatten/`
subdirectory.

## Creating Registries from MD5 Checksums

```python
md5_text = """\
d41d8cd98f00b204e9800998ecf8427e  file1.pdb
e99a18c428cb38d5f260853678922e03  file2.pdb
"""
registry = FileDownloadRegistry.prepare_registry_from_md5(md5_text)
```
