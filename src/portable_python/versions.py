"""
Tracking only a handful of most recent (and non-EOL) versions by design.

Not trying to do historical stuff here, older (or EOL-ed) versions will be removed from the list without notice.
"""

import abc
import logging
import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar, TYPE_CHECKING

import runez
from runez.http import RestClient
from runez.pyenv import PythonDepot, Version

from portable_python.config import Config

if TYPE_CHECKING:
    from portable_python import PythonBuilder


class VersionFamily(abc.ABC):
    """Common ancestor for python family implementations"""

    _latest: Version | None = None
    _versions: dict[str, Version] | None = None

    def __init__(self):
        self.family_name = self.__class__.__name__[:7].lower()

    def __repr__(self):
        return self.family_name

    def _fetch_versions(self) -> dict[str, Version]:
        if self._versions is None:
            self._versions = {}
            versions = sorted(self.get_available_versions(), reverse=True)
            self._latest = versions[0] if versions else None
            for v in versions:
                if v.mm not in self._versions:
                    self._versions[v.mm] = v

        return self._versions

    @property
    def latest(self) -> Version:
        """Latest version for this family"""
        self._fetch_versions()
        if self._latest is None:
            runez.abort(f"Could not determine latest {self} version")

        return self._latest

    @property
    def available_versions(self) -> dict[str, Version]:
        """Latest version per major.minor (as supplied by descendant)"""
        return self._fetch_versions()

    @abc.abstractmethod
    def get_available_versions(self) -> Iterable[Version]:
        """Available versions"""

    @abc.abstractmethod
    def get_builder(self) -> type["PythonBuilder"]:
        """Builder implementation for this family"""


class CPythonFamily(VersionFamily):
    """Implementation for cpython"""

    min_version = "3.9"  # Earliest non-EOL known to compile well

    @runez.cached_property
    def client(self):
        return RestClient()

    def get_available_versions(self) -> Iterable[Version]:
        """Available versions as per python.org/ftp"""
        if PPG.config.get_value("cpython-use-github"):
            r = self.client.get("https://api.github.com/repos/python/cpython/git/matching-refs/tags/v3.", logger=logging.debug)
            for item in r or ():
                ref = item.get("ref")
                if ref and ref.startswith("refs/tags/v"):
                    ref = ref[11:]
                    v = Version(ref)
                    if v.is_valid and v.is_final and v.given_components and len(v.given_components) == 3 and self.min_version < v:
                        yield v

            return

        upcoming = Version("3.11")  # No need to double-check .0 releases prior to this version
        base_url = "https://www.python.org/ftp/python"
        r = self.client.get_response(f"{base_url}/", logger=logging.debug)
        regex = re.compile(r'"(\d+\.\d+\.\d+)/"')
        if r.text:
            for line in r.text.splitlines():
                line = line.strip()
                if line:
                    m = regex.search(line)
                    if m:
                        v = Version(m.group(1))
                        if v.is_valid and v.is_final and self.min_version < v:
                            # For .0 releases, double-check that it's not a release candidate
                            if v < upcoming or v.patch or self.client.url_exists(f"{base_url}/{v}/Python-{v}.tar.xz"):
                                yield v

    def get_builder(self) -> type["PythonBuilder"]:
        from portable_python.cpython import Cpython

        return Cpython


class Folders:
    def __init__(self, config: Config, base=None, family=None, version=None, abi_suffix=None):
        self.config = config
        self.base_folder = runez.resolved_path(base)  # TODO: revise this so that attributes that are paths, are of type Path
        self.family = family
        self.version = Version.from_object(version)
        self.mm = self.version and self.version.mm
        self.completions = config.completions(family=family, version=version, mm=self.mm, abi_suffix=abi_suffix or "")
        self.build_folder = self._required_path("build")
        self.completions["build"] = str(self.build_folder)
        self.components = self.build_folder / "components"
        self.deps = self.build_folder / "deps"
        self.destdir = self._required_path("destdir")
        self.dist = self._get_path("dist")
        self.logs = self._get_path("logs")
        self.ppp_marker = self._required_value("ppp-marker")
        self.sources = self._required_path("sources")

    def __repr__(self):
        return runez.short(self.build_folder)

    def formatted(self, text):
        if text:
            text = text.format(**self.completions)

        return text

    def resolved_destdir(self, relative_path=None):
        folder = self.destdir / self.ppp_marker.strip("/")
        if relative_path:
            folder = folder / relative_path

        return folder

    def _get_value(self, key) -> str | None:
        value = self.config.get_value("folders", key, by_platform=False)
        if value:
            value = os.path.expandvars(value)
            value = self.formatted(value)

        return value

    def _required_value(self, key) -> str:
        value = self._get_value(key)
        if not value:
            runez.abort("Folder '%s' must be configured" % key)

        return value

    def _get_path(self, key) -> Path | None:
        value = self._get_value(key)
        return self._as_path(value) if value else None

    def _required_path(self, key) -> Path:
        return self._as_path(self._required_value(key))

    def _as_path(self, value: str) -> Path:
        if self.base_folder:
            value = runez.resolved_path(value, base=self.base_folder)

        if " " in value:
            runez.abort("Refusing path with space (escapes too complex with makefiles, shell scripts etc): '%s'" % runez.short(value))

        return Path(value)


class PPG:
    """
    Global settings for portable-python

    Attributes
    ----------
    families : dict[str, VersionFamily]
        Mapping of family names to implementations
    config : portable_python.config.Config
        Global configuration
    target : runez.system.PlatformId
        Target platform
    """

    cpython = CPythonFamily()
    families: ClassVar[dict[str, VersionFamily]] = {"cpython": cpython}
    config = Config()
    target = config.target

    _depot = None

    @classmethod
    def grab_config(cls, paths=None, target=None):
        cls.config = Config(paths, target=target)
        cls.target = cls.config.target

    @classmethod
    def get_folders(cls, base=None, family="cpython", version=None, abi_suffix=None):
        config = cls.config or Config()
        return Folders(config, base=base, family=family, version=version, abi_suffix=abi_suffix)

    @classmethod
    def family(cls, family_name) -> VersionFamily:
        fam = cls.families.get(family_name)
        if not fam:
            runez.abort(f"Python family '{runez.red(family_name)}' is not yet supported")

        return fam

    @classmethod
    def find_python(cls, spec):
        if cls._depot is None:
            cls._depot = PythonDepot("PATH")

        return cls._depot.find_python(spec)

    @classmethod
    def find_telltale(cls, telltale: str):
        for tt in runez.flattened(telltale, split=" "):
            for sys_include in runez.flattened(cls.target.sys_include):
                path = tt.format(include=sys_include)
                if os.path.exists(path):
                    return path
