"""Tests for URL/search target resolution (offline helper)."""

import pytest

# file_source imports soundfile; skip cleanly if it is not installed.
sf = pytest.importorskip("soundfile")  # noqa: F841

from bandfoss.capture.file_source import is_url, resolve_target


def test_is_url():
    assert is_url("https://youtube.com/watch?v=abc")
    assert is_url("http://example.com")
    assert not is_url("we are the champions")
    assert not is_url("/home/user/song.mp3")


def test_track_url_passes_through():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert resolve_target(url) == url


def test_free_text_becomes_ytsearch():
    assert resolve_target("we are the champions") == "ytsearch1:we are the champions"


def test_search_url_extracts_query():
    url = "https://music.youtube.com/search?q=bohemian+rhapsody"
    assert resolve_target(url) == "ytsearch1:bohemian rhapsody"


def test_search_url_with_search_query_param():
    url = "https://www.youtube.com/results?search_query=stairway"
    assert resolve_target(url) == "ytsearch1:stairway"
