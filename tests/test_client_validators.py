import pytest
from unittest.mock import patch

from client.exceptions import ClientValidationError
from client.validators import (
    require_existing_file,
    require_metadata_url,
    require_text,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("mario", "mario"),
        ("  mario  ", "mario"),
        (123, "123"),
    ],
)
def test_require_text_returns_stripped_text(value, expected):
    assert require_text(value, "username") == expected


@pytest.mark.parametrize("value", [None, "", "   "])
def test_require_text_rejects_missing_values(value):
    with pytest.raises(ClientValidationError, match="username is required"):
        require_text(value, "username")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://metadata:5000", "http://metadata:5000"),
        ("https://example.com/", "https://example.com"),
    ],
)
def test_require_metadata_url_accepts_http_urls(value, expected):
    assert require_metadata_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "metadata:5000",
        "ftp://metadata:5000",
        "http:///missing-host",
        "",
    ],
)
def test_require_metadata_url_rejects_invalid_urls(value):
    with pytest.raises(ClientValidationError):
        require_metadata_url(value)


def test_require_existing_file_accepts_existing_file():
    with patch("client.validators.os.path.isfile", return_value=True):
        assert require_existing_file("sample.txt") == "sample.txt"


def test_require_existing_file_rejects_missing_file():
    with patch("client.validators.os.path.isfile", return_value=False):
        with pytest.raises(ClientValidationError, match="file does not exist"):
            require_existing_file("missing.txt")
