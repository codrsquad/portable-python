"""
Tracking only a handful of most recent (and non-EOL) versions by design
Not trying to do historical stuff here, older (or EOL-ed) versions will be removed from the list without notice
"""

import logging
import re

import runez
from runez.http import RestClient
from runez.pyenv import PythonDepot, Version

from portable_python.config import Config


class VersionFamily:
    """Common ancestor for python family implementations"""

    _latest = None
    _versions = None

    def __init__(self):
        self.family_name = self.__class__.__name__[:7].lower()

    def __repr__(self):
        return self.family_name

    def _fetch_versions(self):
        if self._versions is None:
            self._versions = {}
            versions = self.get_available_versions()
            versions = versions and sorted((Version.from_text(x) for x in versions), reverse=True)
            if versions:
                self._latest = versions[0]
                for v in versions:
                    mm = Version("%s.%s" % (v.major, v.minor))
                    if mm not in self._versions:
                        self._versions[mm] = v

    @property
    def latest(self) -> Version:
        """Latest version for this family"""
        self._fetch_versions()
        return self._latest

    @property
    def available_versions(self):
        """Supplied by descendant: list of available versions"""
        self._fetch_versions()
        return self._versions

    def get_available_versions(self) -> list:
        """Implementation supplied by descendant: iterable of available versions, can be strings"""

    def get_builder(self):
        """
        Returns:
            (portable_python.PythonBuilder)
        """


class CPythonFamily(VersionFamily):
    """Implementation for cpython"""

    client = RestClient()
    MIN_VERSION = Version("3.7")

    def get_available_versions(self):
        """Available versions as per python.org/ftp"""
        if PPG.config.get_value("cpython-use-github"):
            r = self.client.get("https://api.github.com/repos/python/cpython/git/matching-refs/tags/v3.", logger=logging.debug)
            for item in r:
                ref = item.get("ref")
                if ref and ref.startswith("refs/tags/v"):
                    ref = ref[11:]
                    v = Version(ref)
                    if v.is_valid and v.is_final and v.given_components and len(v.given_components) == 3 and self.MIN_VERSION < v:
                        yield v

            return

        r = self.client.get_response("https://www.python.org/ftp/python/", logger=logging.debug)
        regex = re.compile(r'"(\d+\.\d+\.\d+)/"')
        if r.text:
            for line in r.text.splitlines():
                line = line.strip()
                if line:
                    m = regex.search(line)
                    if m:
                        v = Version(m.group(1))
                        if v.is_valid and v.is_final and self.MIN_VERSION < v:
                            yield v

    def get_builder(self):
        from portable_python.cpython import Cpython

        return Cpython


class PPG:
    """Globals"""

    cpython = CPythonFamily()
    families = dict(cpython=cpython)
    config = Config()
    target = config.target

    _depot = None

    @classmethod
    def grab_config(cls, path=None, base_folder=None, target=None):
        cls.config = Config(path=path, base_folder=base_folder, target=target, replaces=cls.config)
        cls.target = cls.config.target

    @classmethod
    def family(cls, family_name, fatal=True) -> VersionFamily:
        fam = cls.families.get(family_name)
        if fatal and not fam:
            runez.abort(f"Python family '{family_name}' is not yet supported")

        return fam

    @classmethod
    def find_python(cls, spec):
        if cls._depot is None:
            cls._depot = PythonDepot(use_path=False)

        return cls._depot.find_python(spec)
