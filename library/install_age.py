#!/usr/bin/python
from __future__ import annotations
from dataclasses import dataclass
import json
import os.path
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import traceback
from typing import Any
from urllib.request import Request, urlopen
from ansible.module_utils.basic import AnsibleModule

USER_AGENT = "install_age.py/0.0.0"


@dataclass(order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s: str) -> Version:
        if (m := re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", s)) is not None:
            major = int(m[1])
            minor = int(m[2])
            patch = int(m[3])
            return Version(major, minor, patch)
        else:
            raise ValueError(f"invalid version string: {s!r}")


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "minversion": {"type": "str", "default": None},
            "latest": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    if (mv := module.params["minversion"]) is not None:
        try:
            minversion = Version.parse(mv)
        except ValueError as e:
            module.fail_json(msg=f"failed to parse 'minversion' argument: {e}")
    else:
        minversion = None
    latest = module.params["latest"]
    try:
        r = subprocess.run(
            ["age", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        installed_version = None
    except subprocess.CalledProcessError as e:
        module.fail_json(msg=str(e))
    except Exception:
        module.fail_json(msg=traceback.format_exc())
    else:
        try:
            installed_version = Version.parse(r.stdout.strip())
        except ValueError as e:
            module.fail_json(msg=f"failed to parse 'age --version' output: {e}")
    if (
        not latest
        and installed_version is not None
        and (minversion is None or installed_version >= minversion)
    ):
        module.exit_json(changed=False)
    else:
        try:
            data = get_json(
                "https://api.github.com/repos/FiloSottile/age/releases/latest"
            )
            latest_tag = data["tag_name"]
            try:
                latest_version = Version.parse(latest_tag)
            except ValueError as e:
                module.fail_json(msg=f"failed to parse latest tag: {e}")
            if latest_version == installed_version:
                module.exit_json(changed=False)
            if not module.check_mode:
                r = subprocess.run(
                    ["dpkg", "--print-architecture"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                )
                arch = r.stdout.strip()
                tarpath = download_to_tempfile(
                    f"https://github.com/FiloSottile/age/releases/download/{latest_tag}/age-{latest_tag}-linux-{arch}.tar.gz",
                )
                try:
                    with tarfile.open(tarpath) as tar:
                        tar.extractall(path="/usr/local/bin", filter=tarfilter)
                finally:
                    tarpath.unlink()
            module.exit_json(changed=True)
        except Exception:
            module.fail_json(msg=traceback.format_exc())


def get_json(url: str) -> Any:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as r:
        return json.load(r)


def download_file(url: str, path: Path) -> None:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as r:
        with open(path, "wb") as fp:
            shutil.copyfileobj(r, fp)
        if "content-length" in r.headers:
            size = int(r.headers["Content-Length"])
            fsize = os.path.getsize(path)
            if fsize < size:
                raise RuntimeError(f"{url}: only {fsize} out of {size} bytes received")


def download_to_tempfile(url: str) -> Path:
    fd, tmpfile = tempfile.mkstemp()
    os.close(fd)
    p = Path(tmpfile)
    download_file(url, p)
    return p


def tarfilter(member: tarfile.TarInfo, path: str) -> tarfile.TarInfo | None:
    p = PurePosixPath(member.name)
    if len(p.parts) == 2:
        # Change the name before calling data_filter(), as otherwise, once
        # /usr/local/bin/age is extracted, trying to filter anything else under
        # the tarball's age/ directory will lead to an error due to tarfile
        # thinking we're trying to extract to a path under a non-directory.
        member = member.replace(name=p.name)
        member = tarfile.data_filter(member, path)
        if member is not None and member.isfile() and member.mode & 0o100:
            return member
    return None


if __name__ == "__main__":
    main()
