import pytest

from src.json_repair.utils.string_file_wrapper import StringFileWrapper


def test_string_file_wrapper_handles_multibyte(tmp_path):
    text = "\u0800"
    file_path = tmp_path / "multibyte.json"
    file_path.write_text(text, encoding="utf-8")
    with file_path.open("r", encoding="utf-8") as handle:
        wrapper = StringFileWrapper(handle, chunk_length=2)
        assert wrapper[0:1] == text
        assert wrapper[0:2] == text
        assert wrapper[0] == text


def test_string_file_wrapper_invalid_buffer_access(tmp_path):
    file_path = tmp_path / "buffer.json"
    file_path.write_text("ab", encoding="utf-8")
    with file_path.open("r", encoding="utf-8") as handle:
        wrapper = StringFileWrapper(handle, chunk_length=1)
        with pytest.raises(IndexError):
            wrapper.get_buffer(-1)
        # Build chunk metadata and then request the chunk that resides past EOF.
        len(wrapper)
        with pytest.raises(IndexError):
            wrapper.get_buffer(2)


def test_string_file_wrapper_slice_variations(tmp_path):
    file_path = tmp_path / "slice.json"
    file_path.write_text("abcd", encoding="utf-8")
    with file_path.open("r", encoding="utf-8") as handle:
        wrapper = StringFileWrapper(handle, chunk_length=2)
        assert wrapper[-2:4] == "cd"
        assert wrapper[0:-1] == "abc"
        assert wrapper[3:1] == ""
        assert wrapper[0:4:2] == "ac"
        with pytest.raises(ValueError, match="slice step cannot be zero"):
            _ = wrapper[::0]


def test_string_file_wrapper_negative_indices(tmp_path):
    file_path = tmp_path / "index.json"
    file_path.write_text("xyz", encoding="utf-8")
    with file_path.open("r", encoding="utf-8") as handle:
        wrapper = StringFileWrapper(handle, chunk_length=2)
        assert wrapper[-1] == "z"
        with pytest.raises(IndexError):
            _ = wrapper[-10]


def test_string_file_wrapper_ensure_chunk_position_raises(tmp_path):
    file_path = tmp_path / "ensure.json"
    file_path.write_text("foo", encoding="utf-8")
    with file_path.open("r", encoding="utf-8") as handle:
        wrapper = StringFileWrapper(handle, chunk_length=1)
        with pytest.raises(IndexError):
            wrapper._ensure_chunk_position(10)
