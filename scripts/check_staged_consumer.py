#!/usr/bin/env python3
"""Compile the public consumer against extracted Cargo package archives."""
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("sdm-core", "sdm-data", "sdm-eval", "sdm-experiment",
            "sdm-nonlinear", "sdm-runtime", "sdm-training")


def run(args, cwd):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def main():
    archive_dir = ROOT / "target/package"
    with tempfile.TemporaryDirectory(prefix="sdm-staged-consumer-") as temporary:
        temp = Path(temporary)
        packages = temp / "packages"
        packages.mkdir()
        for name in PACKAGES:
            archive = archive_dir / f"{name}-0.1.0.crate"
            if not archive.is_file():
                raise SystemExit(f"missing {archive}; run cargo package --workspace --locked first")
            with tarfile.open(archive, "r:gz") as package:
                members = package.getmembers()
                root = f"{name}-0.1.0/"
                if any(not member.name.startswith(root) for member in members):
                    raise SystemExit(f"unexpected path in {archive}")
                package.extractall(packages)
            shutil.move(packages / f"{name}-0.1.0", packages / name)
            if not (packages / name / "Cargo.toml").is_file():
                raise SystemExit(f"extracted package has no manifest: {packages / name}")

        consumer = temp / "consumer"
        (consumer / "src").mkdir(parents=True)
        shutil.copy(ROOT / "examples/standalone-consumer/src/main.rs", consumer / "src/main.rs")
        (consumer / "Cargo.toml").write_text(
            '[package]\nname = "sdm-staged-consumer"\nversion = "0.1.0"\nedition = "2021"\n\n'
            '[dependencies]\nsdm-experiment = "=0.1.0"\nserde_json = "1"\n'
        )
        config = temp / ".cargo"
        config.mkdir()
        patch = "\n".join(
            f'{name} = {{ path = "{(packages / name).as_posix()}" }}' for name in PACKAGES
        )
        (config / "config.toml").write_text(f"[patch.crates-io]\n{patch}\n")
        run(["cargo", "generate-lockfile", "--offline"], consumer)
        run(["cargo", "check", "--locked", "--offline"], consumer)
    print("staged consumer compiled against extracted package archives")


if __name__ == "__main__":
    main()
