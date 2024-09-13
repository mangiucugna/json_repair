import os
from typing import TextIO, Union


class StringFileWrapper:
    # This is a trick to simplify the code, transform the filedescriptor handling into a string handling
    def __init__(self, fd: TextIO, CHUNK_LENGTH: int) -> None:
        self.fd = fd
        self.length: int = 0
        # Buffers are 1MB strings that are read from the file
        # and kept in memory to keep reads low
        self.buffers: dict[int, str] = {}
        # CHUNK_LENGTH is in bytes
        if not CHUNK_LENGTH or CHUNK_LENGTH < 2:
            CHUNK_LENGTH = 1_000_000
        self.buffer_length = CHUNK_LENGTH

    def get_buffer(self, index: int) -> str:
        if self.buffers.get(index) is None:
            self.fd.seek(index * self.buffer_length)
            self.buffers[index] = self.fd.read(self.buffer_length)
            # Save memory by keeping max 2MB buffer chunks and min 2 chunks
            if len(self.buffers) > max(2, 2_000_000 / self.buffer_length):
                oldest_key = next(iter(self.buffers))
                if oldest_key != index:
                    self.buffers.pop(oldest_key)
        return self.buffers[index]

    def __getitem__(self, index: Union[int, slice]) -> str:
        # The buffer is an array that is seek like a RAM:
        # self.buffers[index]: the row in the array of length 1MB, index is `i` modulo CHUNK_LENGTH
        # self.buffures[index][j]: the column of the row that is `i` remainder CHUNK_LENGTH
        if isinstance(index, slice):
            buffer_index = index.start // self.buffer_length
            buffer_end = index.stop // self.buffer_length
            if buffer_index == buffer_end:
                return self.get_buffer(buffer_index)[
                    index.start % self.buffer_length : index.stop % self.buffer_length
                ]
            else:
                start_slice = self.get_buffer(buffer_index)[
                    index.start % self.buffer_length :
                ]
                end_slice = self.get_buffer(buffer_end)[
                    : index.stop % self.buffer_length
                ]
                middle_slices = [
                    self.get_buffer(i) for i in range(buffer_index + 1, buffer_end)
                ]
                return start_slice + "".join(middle_slices) + end_slice
        else:
            buffer_index = index // self.buffer_length
            return self.get_buffer(buffer_index)[index % self.buffer_length]

    def __len__(self) -> int:
        if self.length < 1:
            current_position = self.fd.tell()
            self.fd.seek(0, os.SEEK_END)
            self.length = self.fd.tell()
            self.fd.seek(current_position)
        return self.length