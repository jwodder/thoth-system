#!/usr/bin/python
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import PurePosixPath
import re
import subprocess
import tarfile
import tempfile
import traceback
from ansible.module_utils.basic import AnsibleModule
import requests


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
            with requests.Session() as s:
                r = s.get(
                    "https://api.github.com/repos/FiloSottile/age/releases/latest"
                )
                r.raise_for_status()
                latest_tag = r.json()["tag_name"]
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
                    with tempfile.NamedTemporaryFile() as tmpfile:
                        with s.get(
                            f"https://github.com/FiloSottile/age/releases/download/{latest_tag}/age-{latest_tag}-linux-{arch}.tar.gz",
                            stream=True,
                        ) as r:
                            r.raise_for_status()
                            for chunk in r.iter_content(65535):
                                tmpfile.write(chunk)
                        tmpfile.flush()
                        tmpfile.seek(0)
                        with tarfile.open(fileobj=tmpfile) as tar:
                            tar.extractall(path="/usr/local/bin", filter=tarfilter)
                module.exit_json(changed=True)
        except requests.HTTPError as e:
            if 400 <= e.response.status_code < 500:
                msg = "{0.status_code} Client Error: {0.reason} for URL: {0.url}\n"
            elif 500 <= e.response.status_code < 600:
                msg = "{0.status_code} Server Error: {0.reason} for URL: {0.url}\n"
            else:
                msg = "{0.status_code} Unknown Error: {0.reason} for URL: {0.url}\n"
            msg = msg.format(e.response)
            try:
                resp = e.response.json()
            except ValueError:
                msg += e.response.text
            else:
                msg += json.dumps(resp, sort_keys=True, indent=4)
            module.fail_json(msg=msg)
        except Exception:
            module.fail_json(msg=traceback.format_exc())


def tarfilter(member: tarfile.TarInfo, path: str) -> tarfile.TarInfo | None:
    member = tarfile.data_filter(member, path)
    if member is not None:
        p = PurePosixPath(member.name)
        if member.isfile() and len(p.parts) == 2 and member.mode & 0o100:
            return member.replace(name=p.name)
        else:
            return None
    return None


if __name__ == "__main__":
    main()
