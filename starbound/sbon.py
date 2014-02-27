import collections
import struct

Document = collections.namedtuple('Document', ['name', 'version', 'data'])

Tile = collections.namedtuple('Tile', [
    'foreground_material',
    'foreground_hue_shift',
    'foreground_variant',
    'foreground_sprite',
    'foreground_sprite_hue_shift',
    'background_material',
    'background_hue_shift',
    'background_variant',
    'background_sprite',
    'background_sprite_hue_shift',
    'liquid',
    'liquid_pressure',
    'collision',
    'dungeon',
    'biome',
    'biome_2',
    'indestructible',
])

def read_bytes(stream):
    length = read_varlen_number(stream)
    return stream.read(length)

def read_document(stream, repair=False):
    name = read_string(stream)

    # Not sure what this part is.
    assert stream.read(1) == '\x01'

    version = struct.unpack('>i', stream.read(4))[0]
    data = read_dynamic(stream, repair)

    return Document(name, version, data)

def read_document_list(stream):
    length = read_varlen_number(stream)
    return [read_document(stream) for _ in xrange(length)]

def read_dynamic(stream, repair=False):
    type = ord(stream.read(1))

    try:
        if type == 1:
            return None
        elif type == 2:
            format = '>d'
        elif type == 3:
            format = '?'
        elif type == 4:
            return read_varlen_number_signed(stream)
        elif type == 5:
            return read_string(stream)
        elif type == 6:
            return read_list(stream, repair)
        elif type == 7:
            return read_map(stream, repair)
        else:
            raise ValueError('Unknown dynamic type 0x%02X' % type)
    except:
        if repair:
            return None
        raise

    # Anything that passes through is assumed to have set a format to unpack.
    return struct.unpack(format, stream.read(struct.calcsize(format)))[0]

def read_fixlen_string(stream, length):
    return stream.read(length).rstrip('\x00').decode('utf-8')

def read_list(stream, repair=False):
    length = read_varlen_number(stream)
    return [read_dynamic(stream, repair) for _ in xrange(length)]

def read_map(stream, repair=False):
    length = read_varlen_number(stream)

    value = dict()
    for _ in xrange(length):
        key = read_string(stream)
        value[key] = read_dynamic(stream, repair)

    return value

def read_string(stream):
    return read_bytes(stream).decode('utf-8')

def read_string_list(stream):
    """Optimized structure that doesn't have a type byte for every item.

    """
    length = read_varlen_number(stream)
    return [read_string(stream) for _ in xrange(length)]

def read_string_digest_map(stream):
    """Special structure of string/digest pairs, used by the assets database.

    """
    length = read_varlen_number(stream)

    value = dict()
    for _ in xrange(length):
        path = read_string(stream)
        # Unnecessary whitespace.
        stream.seek(1, 1)
        digest = stream.read(32)
        value[path] = digest

    return value

def read_tile(stream):
    values = struct.unpack('>hBBhBhBBhBBHBhBB?', stream.read(23))
    return Tile(*values)

def read_varlen_number(stream):
    """Read while the most significant bit is set, then put the 7 least
    significant bits of all read bytes together to create a number.

    """
    value = 0
    while True:
        byte = ord(stream.read(1))
        if not byte & 0b10000000:
            return value << 7 | byte
        value = value << 7 | (byte & 0b01111111)

def read_varlen_number_signed(stream):
    value = read_varlen_number(stream)

    # Least significant bit represents the sign.
    if value & 1:
        return -(value >> 1)
    else:
        return value >> 1
