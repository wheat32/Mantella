"""Minimal extractor for Skyrim SE (v105) and LE (v104) .bsa archives: extracts files whose path matches a substring."""
import struct, sys, os, zlib

def extract(bsa_path, match, out_dir):
    with open(bsa_path, 'rb') as f:
        magic, version, offset, flags, folder_count, file_count, total_folder_len, total_file_len, file_flags = struct.unpack('<4sIIIIIIII', f.read(36))
        assert magic == b'BSA\x00', magic
        compressed_default = bool(flags & 0x4)
        embed_names = bool(flags & 0x100) and version >= 104
        folders = []
        for _ in range(folder_count):
            if version == 105:
                _hash, count, _pad, off, _pad2 = struct.unpack('<QIIII', f.read(24))
            else:
                _hash, count, off = struct.unpack('<QII', f.read(16))
            folders.append(count)
        records = []
        for count in folders:
            name_len = f.read(1)[0]
            folder_name = f.read(name_len)[:-1].decode('cp1252')
            for _ in range(count):
                _hash, size, off = struct.unpack('<QII', f.read(16))
                records.append([folder_name, size, off])
        names = f.read(total_file_len).split(b'\x00')
        extracted = []
        for record, name in zip(records, names):
            folder_name, size, off = record
            path = f"{folder_name}\\{name.decode('cp1252')}"
            if match.lower() not in path.lower():
                continue
            compressed = compressed_default != bool(size & 0x40000000)
            size &= 0x3FFFFFFF
            f.seek(off)
            if embed_names:
                skip = f.read(1)[0]
                f.read(skip)
                size -= skip + 1
            if compressed:
                original_size = struct.unpack('<I', f.read(4))[0]
                raw = f.read(size - 4)
                if version == 105:
                    import lz4.frame
                    data = lz4.frame.decompress(raw)
                else:
                    data = zlib.decompress(raw)
            else:
                data = f.read(size)
            target = os.path.join(out_dir, os.path.basename(path.replace('\\', '/')))
            os.makedirs(out_dir, exist_ok=True)
            with open(target, 'wb') as out:
                out.write(data)
            extracted.append(path)
        return extracted, version, compressed_default

if __name__ == '__main__':
    files, version, compressed = extract(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f'v{version} compressed={compressed}: extracted {len(files)} files')
    for p in files[:8]: print('  ', p)
