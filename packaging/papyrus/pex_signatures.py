"""Prints the function signatures of a compiled Skyrim Papyrus script (.pex).
Used to check declarations written by hand against a script whose source is not available.

Usage: python packaging/papyrus/pex_signatures.py <file.pex> [name filter]
"""
import struct
import sys

# number of fixed arguments per opcode; opcodes in VARIADIC take a further count followed by that many arguments
OPCODE_ARGS = [0, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 1, 2, 2, 3, 2, 3, 1, 3, 3, 3, 2, 2, 3, 3, 4, 4]
VARIADIC = {23, 24, 25}


class Reader:
    def __init__(self, data: bytes):
        self.data, self.pos, self.strings = data, 0, []

    def read(self, fmt: str):
        size = struct.calcsize(fmt)
        value = struct.unpack_from(fmt, self.data, self.pos)[0]
        self.pos += size
        return value

    def u8(self): return self.read('>B')
    def u16(self): return self.read('>H')
    def u32(self): return self.read('>I')

    def wstring(self) -> str:
        length = self.u16()
        value = self.data[self.pos:self.pos + length].decode('latin-1')
        self.pos += length
        return value

    def name(self) -> str:
        return self.strings[self.u16()]

    def value(self):
        kind = self.u8()
        if kind in (1, 2): return self.name()
        if kind in (3, 4): return self.u32()
        if kind == 5: return self.u8()
        return None

    def function(self) -> tuple[str, list[tuple[str, str]], int]:
        return_type = self.name()
        self.u16(); self.u32()                       # doc string, user flags
        flags = self.u8()
        params = [(self.name(), self.name()) for _ in range(self.u16())]
        for _ in range(self.u16()): self.u16(); self.u16()   # locals
        for _ in range(self.u16()):                   # instructions
            opcode = self.u8()
            for _ in range(OPCODE_ARGS[opcode]): self.value()
            if opcode in VARIADIC:
                for _ in range(self.value()): self.value()
        return return_type, params, flags


def get_signatures(path: str) -> list[str]:
    r = Reader(open(path, 'rb').read())
    assert r.u32() == 0xFA57C0DE, 'not a Skyrim .pex file'
    r.pos = 16
    for _ in range(3): r.wstring()
    r.strings = [r.wstring() for _ in range(r.u16())]
    if r.u8():                                        # debug info
        r.pos += 8
        for _ in range(r.u16()):
            r.pos += 7
            line_count = r.u16()
            r.pos += 2 * line_count
    for _ in range(r.u16()): r.u16(); r.u8()          # user flags

    signatures = []
    for _ in range(r.u16()):                          # objects
        r.u16(); r.u32()
        r.u16(); r.u16(); r.u32(); r.u16()            # parent, doc, user flags, auto state
        for _ in range(r.u16()): r.u16(); r.u16(); r.u32(); r.value()   # variables
        for _ in range(r.u16()):                      # properties
            r.u16(); r.u16(); r.u16(); r.u32()
            flags = r.u8()
            if flags & 4: r.u16()
            else:
                if flags & 1: r.function()
                if flags & 2: r.function()
        for _ in range(r.u16()):                      # states
            state = r.name()
            for _ in range(r.u16()):
                name = r.name()
                return_type, params, flags = r.function()
                if state == '':
                    kind = 'function' if return_type != 'None' or not name.lower().startswith('on') else 'function/event'
                    signatures.append(f"{'' if return_type == 'None' else return_type + ' '}{kind} {name}({', '.join(f'{t} {n}' for n, t in params)}){' global' if flags & 1 else ''}{' native' if flags & 2 else ''}")
    return signatures


if __name__ == '__main__':
    name_filter = sys.argv[2].lower() if len(sys.argv) > 2 else ''
    for signature in get_signatures(sys.argv[1]):
        if name_filter in signature.lower():
            print(signature)
