import argparse
import re
import struct
import zlib
from pathlib import Path


END = 0xFFFFFFFE
FREE = 0xFFFFFFFF


def u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


class CompoundFile:
    def __init__(self, data):
        self.data = data
        if data[:8] != bytes.fromhex("D0CF11E0A1B11AE1"):
            raise ValueError("not an OLE compound file")

        self.sector_size = 1 << u16(data, 0x1E)
        self.mini_sector_size = 1 << u16(data, 0x20)
        self.num_fat = u32(data, 0x2C)
        self.dir_start = u32(data, 0x30)
        self.mini_cutoff = u32(data, 0x38)
        self.minifat_start = u32(data, 0x3C)
        self.num_minifat = u32(data, 0x40)
        self.difat_start = u32(data, 0x44)
        self.num_difat = u32(data, 0x48)

        self.difat = []
        for i in range(109):
            sid = u32(data, 0x4C + i * 4)
            if sid not in (FREE, END):
                self.difat.append(sid)

        next_difat = self.difat_start
        for _ in range(self.num_difat):
            sec = self.sector(next_difat)
            for i in range((self.sector_size // 4) - 1):
                sid = u32(sec, i * 4)
                if sid not in (FREE, END):
                    self.difat.append(sid)
            next_difat = u32(sec, self.sector_size - 4)
            if next_difat == END:
                break

        self.fat = []
        for sid in self.difat[: self.num_fat]:
            sec = self.sector(sid)
            self.fat.extend(u32(sec, i * 4) for i in range(self.sector_size // 4))

        self.dir_stream = self.stream_by_start(self.dir_start, None)
        self.entries = self.parse_directory()
        self.root = next((entry for entry in self.entries if entry["type"] == 5), None)

        self.mini_stream = b""
        if self.root and self.root["start"] not in (FREE, END):
            self.mini_stream = self.stream_by_start(self.root["start"], self.root["size"])

        self.minifat = []
        if self.minifat_start not in (FREE, END):
            data = self.stream_by_start(
                self.minifat_start, self.num_minifat * self.sector_size
            )
            self.minifat = [u32(data, i * 4) for i in range(len(data) // 4)]

    def sector(self, sid):
        offset = (sid + 1) * self.sector_size
        return self.data[offset : offset + self.sector_size]

    def chain(self, start, fat=None):
        fat = self.fat if fat is None else fat
        sid = start
        seen = set()
        while sid not in (FREE, END) and sid < len(fat) and sid not in seen:
            seen.add(sid)
            yield sid
            sid = fat[sid]

    def stream_by_start(self, start, size):
        chunks = [self.sector(sid) for sid in self.chain(start)]
        data = b"".join(chunks)
        return data if size is None else data[:size]

    def ministream_by_start(self, start, size):
        chunks = []
        sid = start
        seen = set()
        while sid not in (FREE, END) and sid < len(self.minifat) and sid not in seen:
            seen.add(sid)
            offset = sid * self.mini_sector_size
            chunks.append(self.mini_stream[offset : offset + self.mini_sector_size])
            sid = self.minifat[sid]
        return b"".join(chunks)[:size]

    def parse_directory(self):
        entries = []
        for offset in range(0, len(self.dir_stream), 128):
            entry = self.dir_stream[offset : offset + 128]
            if len(entry) < 128:
                continue
            name_len = u16(entry, 64)
            name = ""
            if name_len >= 2:
                name = entry[: name_len - 2].decode("utf-16le", errors="ignore")
            entries.append(
                {
                    "idx": len(entries),
                    "name": name,
                    "type": entry[66],
                    "start": u32(entry, 116),
                    "size": struct.unpack_from("<Q", entry, 120)[0],
                }
            )
        return entries

    def read_entry(self, entry):
        if entry["type"] == 2 and entry["size"] < self.mini_cutoff:
            return self.ministream_by_start(entry["start"], entry["size"])
        return self.stream_by_start(entry["start"], entry["size"])


def inflate_candidates(data):
    yield data
    for wbits in (-15, 15):
        try:
            yield zlib.decompress(data, wbits)
        except zlib.error:
            pass


def hwp_text_from_records(data):
    parts = []
    offset = 0
    while offset + 4 <= len(data):
        header = u32(data, offset)
        offset += 4
        tag = header & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            if offset + 4 > len(data):
                break
            size = u32(data, offset)
            offset += 4
        record = data[offset : offset + size]
        offset += size
        if tag == 67:
            text = record.decode("utf-16le", errors="ignore")
            if text.strip():
                parts.append(text)
    return parts


def clean_text(text):
    text = text.replace("\x00", " ")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_hwp(path):
    cfb = CompoundFile(Path(path).read_bytes())
    sections = []
    for entry in cfb.entries:
        if entry["type"] != 2:
            continue
        name = entry["name"]
        if not (name.startswith("Section") or name == "PrvText"):
            continue
        raw = cfb.read_entry(entry)
        best_parts = []
        for candidate in inflate_candidates(raw):
            parts = hwp_text_from_records(candidate)
            if len(" ".join(parts)) > len(" ".join(best_parts)):
                best_parts = parts
        if not best_parts:
            try:
                best_parts = [raw.decode("utf-16le", errors="ignore")]
            except UnicodeError:
                best_parts = []
        if best_parts:
            sections.append((name, clean_text("\n".join(best_parts))))
    return sections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("hwp")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    sections = extract_hwp(args.hwp)
    if args.list:
        for name, text in sections:
            print(f"== {name} ==")
            print(text[:1000])
            print()
        return
    for name, text in sections:
        print(f"\n===== {name} =====\n")
        print(text)


if __name__ == "__main__":
    main()
