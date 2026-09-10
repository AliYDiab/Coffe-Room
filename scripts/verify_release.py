import argparse
import hashlib
from pathlib import Path


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifacts(release_dir, version):
    release_dir = Path(release_dir)
    expected = {
        f"CafeRoom-Mobile-v{version}.apk": b"PK",
        f"CafeRoom-PC-v{version}.exe": b"MZ",
    }
    hashes = {}
    for name, signature in expected.items():
        path = release_dir / name
        platform = "Mobile" if name.endswith(".apk") else "PC"
        if not path.is_file():
            raise RuntimeError(f"Missing {platform} release asset: {name}")
        if path.stat().st_size <= len(signature):
            raise RuntimeError(f"Empty {platform} release asset: {name}")
        with path.open("rb") as handle:
            if handle.read(len(signature)) != signature:
                raise RuntimeError(f"Invalid {platform} file signature: {name}")
        hashes[name] = _sha256(path)
    return hashes


def write_checksums(release_dir, version, hashes):
    path = Path(release_dir) / f"SHA256SUMS-v{version}.txt"
    lines = [f"{digest}  {name}" for name, digest in sorted(hashes.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description="Validate CafeRoom release assets")
    parser.add_argument("release_dir", type=Path)
    parser.add_argument("version")
    args = parser.parse_args()
    hashes = verify_artifacts(args.release_dir, args.version)
    checksum = write_checksums(args.release_dir, args.version, hashes)
    for name, digest in sorted(hashes.items()):
        print(f"{name}: {digest}")
    print(f"Checksums: {checksum}")


if __name__ == "__main__":
    main()
