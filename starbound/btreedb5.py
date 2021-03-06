# -*- coding: utf-8 -*-

import binascii
import io
import struct

from starbound import sbon


# Override range with xrange when running Python 2.x.
try:
    range = xrange
except:
    pass


HEADER = '>8si16si?ixxxixixixxxixi446x'
HEADER_SIZE = struct.calcsize(HEADER)
# Constants for the different block types.
FREE = b'FF'
INDEX = b'II'
LEAF = b'LL'


class BTreeDB5(object):
    def __init__(self, stream):
        self.stream = stream

    def get(self, key):
        if not hasattr(self, 'key_size'):
            self.read_header()
        assert len(key) == self.key_size, 'Invalid key length'
        # Traverse the B-tree until we reach a leaf.
        offset = HEADER_SIZE + self.block_size * self.root
        entry_size = self.key_size + 4
        s = self.stream
        while True:
            s.seek(offset)
            block_type = s.read(2)
            if block_type != INDEX:
                break
            # Read the index header and scan for the closest key.
            lo, (_, hi, block) = 0, struct.unpack('>Bii', s.read(9))
            offset += 11
            while lo < hi:
                mid = (lo + hi) // 2
                s.seek(offset + entry_size * mid)
                if key < s.read(self.key_size):
                    hi = mid
                else:
                    lo = mid + 1
            if lo > 0:
                s.seek(offset + entry_size * (lo - 1) + self.key_size)
                block, = struct.unpack('>i', s.read(4))
            offset = HEADER_SIZE + self.block_size * block
        assert block_type == LEAF, 'Did not reach a leaf'
        # Scan leaves for the key, then read the data.
        reader = LeafReader(self)
        num_keys, = struct.unpack('>i', reader.read(4))
        for i in range(num_keys):
            cur_key = reader.read(self.key_size)
            length = sbon.read_varint(reader)
            if key == cur_key:
                return reader.read(length)
            reader.seek(length, 1)
        # None of the keys in the leaf node matched.
        raise KeyError(binascii.hexlify(key))

    def read_header(self):
        self.stream.seek(0)
        data = struct.unpack(HEADER, self.stream.read(HEADER_SIZE))
        assert data[0] == b'BTreeDB5', 'Invalid header'
        self.block_size = data[1]
        self.name = data[2].rstrip(b'\0').decode('utf-8')
        self.key_size = data[3]
        self.root, self.other_root = data[7], data[10]
        self.use_other_root = False
        if data[4]:
            self.swap_root()

    def swap_root(self):
        self.root, self.other_root = self.other_root, self.root
        self.use_other_root = not self.use_other_root


class LeafReader(object):
    def __init__(self, db):
        # The stream offset must be right after an "LL" marker.
        self.db = db
        self.offset = 2

    def read(self, size=-1):
        if size < 0:
            raise NotImplemented('Can only read specific amount')
        with io.BytesIO() as data:
            for length in self._traverse(size):
                data.write(self.db.stream.read(length))
            return data.getvalue()

    def seek(self, offset, whence=0):
        if whence != 1 or offset < 0:
            raise NotImplemented('Can only seek forward relatively')
        for length in self._traverse(offset):
            self.db.stream.seek(length, 1)

    def _traverse(self, length):
        block_end = self.db.block_size - 4
        while True:
            if self.offset + length <= block_end:
                yield length
                self.offset += length
                break
            delta = block_end - self.offset
            yield delta
            block, = struct.unpack('>i', self.db.stream.read(4))
            assert block >= 0, 'Could not traverse to next block'
            self.db.stream.seek(HEADER_SIZE + self.db.block_size * block)
            assert self.db.stream.read(2) == LEAF, 'Did not reach a leaf'
            self.offset = 2
            length -= delta
