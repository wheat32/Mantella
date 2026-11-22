"""Removes the user name and computer name that the Papyrus compiler embeds in compiled scripts (.pex).

Usage: python packaging/anonymize_pex.py <file or folder> [...]
"""
import struct
import sys
from pathlib import Path

SKYRIM_PEX_MAGIC = 0xFA57C0DE


def anonymize(path: Path) -> bool:
    """Blanks the user and machine name in the header of a Skyrim .pex file. Returns whether the file was changed"""
    data = path.read_bytes()
    if len(data) < 16 or struct.unpack('>I', data[:4])[0] != SKYRIM_PEX_MAGIC:
        raise ValueError(f'{path} is not a Skyrim .pex file')

    # Header: magic (4), major version (1), minor version (1), game id (2), compilation time (8),
    # followed by three length-prefixed strings: source file name, user name, machine name
    offset = 16
    positions: list[tuple[int, int]] = []
    for _ in range(3):
        length = struct.unpack('>H', data[offset:offset + 2])[0]
        positions.append((offset, length))
        offset += 2 + length

    (user_offset, user_length), (machine_offset, machine_length) = positions[1], positions[2]
    if user_length == 0 and machine_length == 0:
        return False
    end_of_header = machine_offset + 2 + machine_length
    path.write_bytes(data[:user_offset] + struct.pack('>H', 0) + struct.pack('>H', 0) + data[end_of_header:])
    return True


def main():
    targets = [Path(argument) for argument in sys.argv[1:]]
    if not targets:
        sys.exit(__doc__)
    files = [f for target in targets for f in (sorted(target.rglob('*.pex')) if target.is_dir() else [target])]
    changed = sum(anonymize(f) for f in files)
    print(f'Anonymized {changed} of {len(files)} compiled scripts')


if __name__ == '__main__':
    main()
