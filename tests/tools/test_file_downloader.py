import pytest
import os
from unittest.mock import patch, MagicMock
from REvoDesign.tools.dl_weights import FileDownloadRegistry, DownloadedFile

class TestFileDownloadRegistry:
    """Test cases for FileDownloadRegistry class"""
    
    @pytest.mark.parametrize("a_string, hash_type, expected", [
        ("md5:abc123", "md5", "md5:abc123"),
        ("abc123", "md5", "md5:abc123"),
        (None, "md5", None),
        ("", "md5", None),
        ("sha256:def456", "md5", "sha256:def456"),
    ])
    def test_complete_varify_string(self, a_string, hash_type, expected):
        """Test _complete_varify_string method with various inputs"""
        result = FileDownloadRegistry._complete_varify_string(a_string, hash_type)
        assert result == expected
    
    @pytest.mark.parametrize("registry, expected", [
        (
            {"file1.txt": "md5:abc123", "file2.txt": "def456"},
            {"file1.txt": "md5:abc123", "file2.txt": "md5:def456"}
        ),
        (
            {"file1.txt": None, "file2.txt": ""},
            {"file1.txt": None, "file2.txt": None}
        ),
        (
            {"file1.txt": "sha256:abc123"},
            {"file1.txt": "sha256:abc123"}
        ),
    ])
    def test_preprocess_registry(self, registry, expected):
        """Test preprocess_registry method with various registry inputs"""
        result = FileDownloadRegistry.preprocess_registry(registry)
        assert result == expected
    
    @pytest.mark.parametrize("md5_contents, expected", [
        (
            "abc123 file1.txt\ndef456 file2.txt",
            {"file1.txt": "md5:abc123", "file2.txt": "md5:def456"}
        ),
        (
            "abc123 file1.txt\n\ndef456 file2.txt",
            {"file1.txt": "md5:abc123", "file2.txt": "md5:def456"}
        ),
        (
            "malformed-line\nabc123 file1.txt",
            {"file1.txt": "md5:abc123"}
        ),
        (
            "",
            {}
        ),
    ])
    def test_prepare_registry_from_md5(self, md5_contents, expected):
        """Test prepare_registry_from_md5 method with various MD5 content inputs"""
        result = FileDownloadRegistry.prepare_registry_from_md5(md5_contents)
        assert result == expected
    
    @patch('REvoDesign.tools.dl_weights.user_data_dir')
    @patch('REvoDesign.tools.dl_weights.pooch.create')
    def test_init_with_custom_directory(self, mock_pooch_create, mock_user_data_dir):
        """Test FileDownloadRegistry initialization with custom directory"""
        mock_user_data_dir.return_value = "/default/path"
        
        registry = FileDownloadRegistry(
            name="test_module",
            base_url="http://example.com",
            registry={"file.txt": "md5:abc123"},
            version="1.0",
            customized_directory="/custom/path"
        )
        
        assert registry.name == "test_module"
        assert registry.base_url == "http://example.com"
        assert registry.version == "1.0"
        assert registry.customized_directory == "/custom/path"
        mock_pooch_create.assert_called_once_with(
            path="/custom/path",
            version="1.0",
            base_url="http://example.com",
            registry={"file.txt": "md5:abc123"},
            retry_if_failed=99,
        )
    
    @patch('REvoDesign.tools.dl_weights.user_data_dir')
    @patch('REvoDesign.tools.dl_weights.pooch.create')
    def test_init_without_custom_directory(self, mock_pooch_create, mock_user_data_dir):
        """Test FileDownloadRegistry initialization without custom directory"""
        mock_user_data_dir.return_value = "/default/path"
        
        registry = FileDownloadRegistry(
            name="test_module",
            base_url="http://example.com",
            registry={"file.txt": "md5:abc123"},
            version="1.0"
        )
        
        assert registry.customized_directory == "/default/path"
        mock_pooch_create.assert_called_once_with(
            path="/default/path",
            version="1.0",
            base_url="http://example.com",
            registry={"file.txt": "md5:abc123"},
            retry_if_failed=99,
        )
    
    @pytest.mark.parametrize("item, registry_files, expected", [
        ("file1.txt", ["file1.txt", "file2.txt"], True),
        ("file3.txt", ["file1.txt", "file2.txt"], False),
    ])
    @patch('REvoDesign.tools.dl_weights.user_data_dir')
    @patch('REvoDesign.tools.dl_weights.pooch.create')
    def test_has_method(self, mock_pooch_create, mock_user_data_dir, item, registry_files, expected):
        """Test has method to check if file exists in registry"""
        mock_user_data_dir.return_value = "/default/path"
        mock_pooch = MagicMock()
        mock_pooch.registry_files = registry_files
        mock_pooch_create.return_value = mock_pooch
        
        registry = FileDownloadRegistry(
            name="test_module",
            base_url="http://example.com",
            registry={},
        )
        
        assert registry.has(item) == expected
    
    @patch('REvoDesign.tools.dl_weights.user_data_dir')
    @patch('REvoDesign.tools.dl_weights.pooch.create')
    def test_list_all_files(self, mock_pooch_create, mock_user_data_dir):
        """Test list_all_files property"""
        mock_user_data_dir.return_value = "/default/path"
        mock_pooch = MagicMock()
        mock_pooch.registry_files = ["file1.txt", "file2.txt"]
        mock_pooch_create.return_value = mock_pooch
        
        registry = FileDownloadRegistry(
            name="test_module",
            base_url="http://example.com",
            registry={},
        )
        
        assert registry.list_all_files == ["file1.txt", "file2.txt"]
    
    @patch('REvoDesign.tools.dl_weights.user_data_dir')
    @patch('REvoDesign.tools.dl_weights.pooch.create')
    def test_setup_success(self, mock_pooch_create, mock_user_data_dir):
        """Test setup method for successful file download"""
        mock_user_data_dir.return_value = "/default/path"
        mock_pooch = MagicMock()
        mock_pooch.registry = {"file.txt": "md5:abc123"}
        mock_pooch.fetch.return_value = "/downloaded/path/file.txt"
        mock_pooch_create.return_value = mock_pooch
        
        registry = FileDownloadRegistry(
            name="test_module",
            base_url="http://example.com",
            registry={"file.txt": "md5:abc123"},
        )
        
        result = registry.setup("file.txt")
        
        assert isinstance(result, DownloadedFile)
        assert result.name == "file.txt"
        assert result.version == registry.version
        assert result.url == "http://example.com/file.txt"
        assert result.downloaded == "/downloaded/path/file.txt"
        assert result.registry == "md5:abc123"
        mock_pooch.fetch.assert_called_once_with("file.txt", progressbar=True)
    
    @patch('REvoDesign.tools.dl_weights.user_data_dir')
    @patch('REvoDesign.tools.dl_weights.pooch.create')
    def test_setup_failure(self, mock_pooch_create, mock_user_data_dir):
        """Test setup method when file download fails"""
        mock_user_data_dir.return_value = "/default/path"
        mock_pooch = MagicMock()
        mock_pooch.fetch.side_effect = Exception("Network error")
        mock_pooch_create.return_value = mock_pooch
        
        registry = FileDownloadRegistry(
            name="test_module",
            base_url="http://example.com",
            registry={"file.txt": "md5:abc123"},
        )
        
        with pytest.raises(Exception):
            registry.setup("file.txt")


class TestDownloadedFile:
    """Test cases for DownloadedFile dataclass"""
    
    def test_downloaded_file_creation(self,test_tmp_dir):
        """Test DownloadedFile object creation"""
        downloaded_file = DownloadedFile(
            name="test.txt",
            version="1.0",
            url="http://example.com/test.txt",
            downloaded=f"{test_tmp_dir}/test.txt",
            registry="md5:abc123"
        )
        
        assert downloaded_file.name == "test.txt"
        assert downloaded_file.version == "1.0"
        assert downloaded_file.url == "http://example.com/test.txt"
        assert downloaded_file.downloaded == f"{test_tmp_dir}/test.txt"
        assert downloaded_file.registry == "md5:abc123"
    
    @patch('REvoDesign.tools.dl_weights.os.makedirs')
    @patch('REvoDesign.tools.dl_weights.os.listdir')
    def test_flatten_dir(self, mock_listdir, mock_makedirs, test_tmp_dir):
        
        """Test flatten_dir property"""
        downloaded_file = DownloadedFile(
            name="test.txt",
            version="1.0",
            url="http://example.com/test.txt",
            downloaded=f"{test_tmp_dir}/test.txt"
        )
        
        mock_listdir.return_value = []
        flatten_dir = downloaded_file.flatten_dir
        
        expected_dir = f"{test_tmp_dir}/test.txt_flatten/"
        assert flatten_dir == expected_dir
        mock_makedirs.assert_called_once_with(expected_dir, exist_ok=True)
    
    @patch('REvoDesign.tools.dl_weights.extract_archive')
    @patch('REvoDesign.tools.dl_weights.os.listdir')
    def test_flatten_archieve_with_empty_dir(self, mock_listdir, mock_extract_archive,test_tmp_dir):
        """Test flatten_archieve property when directory is empty"""
        downloaded_file = DownloadedFile(
            name="test.zip",
            version="1.0",
            url="http://example.com/test.zip",
            downloaded=f"{test_tmp_dir}/test.zip"
        )
        
        # First call returns empty list (directory is empty)
        # Second call returns list of extracted files
        mock_listdir.side_effect = [
            [],  # First call - directory empty
            ["file1.txt", "file2.txt"]  # Second call - after extraction
        ]
        
        extracted_files = downloaded_file.flatten_archieve
        
        assert extracted_files == ["file1.txt", "file2.txt"]
        mock_extract_archive.assert_called_once_with(f"{test_tmp_dir}/test.zip", f"{test_tmp_dir}/test.zip_flatten/")
    
    @patch('REvoDesign.tools.dl_weights.extract_archive')
    @patch('REvoDesign.tools.dl_weights.os.listdir')
    def test_flatten_archieve_with_non_empty_dir(self, mock_listdir, mock_extract_archive,test_tmp_dir):
        """Test flatten_archieve property when directory is not empty"""
        downloaded_file = DownloadedFile(
            name="test.zip",
            version="1.0",
            url="http://example.com/test.zip",
            downloaded=f"{test_tmp_dir}/test.zip"
        )
        
        # Directory already has files
        mock_listdir.return_value = ["file1.txt", "file2.txt"]
        
        extracted_files = downloaded_file.flatten_archieve
        
        assert extracted_files == ["file1.txt", "file2.txt"]
        mock_extract_archive.assert_not_called()