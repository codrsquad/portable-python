"""
Tracking only a handful of most recent (and non-EOL) versions by design
Not trying to do historical stuff here, older (or EOL-ed) versions will be removed from the list without notice

Usage:
    from portable_python.versions import PythonVersions

    print(PythonVersions.cpython.latest)
    print(PythonVersions.cpython.versions)
"""

import logging
import re

import runez
from runez.http import RestClient
from runez.pyenv import PythonDepot, PythonSpec, Version


class VersionFamily:
    """Common ancestor for python family implementations"""

    _latest = None
    _versions = None
    _test_latest = "3.9.6"  # Pretend latest used in tests and dryruns

    def __init__(self):
        self.family_name = self.__class__.__name__[:7].lower()

    def __repr__(self):
        return self.family_name

    def _fetch_versions(self):
        if self._versions is None:
            if self._test_latest and (runez.DRYRUN or runez.DEV.current_test()):
                self._latest = Version(self._test_latest)
                mm = Version("%s.%s" % (self._latest.major, self._latest.minor))
                self._versions = {mm: self._latest}
                return

            self._versions = {}
            versions = self.get_available_versions()
            versions = versions and sorted((Version.from_text(x) for x in versions), reverse=True)
            if versions:
                self._latest = versions[0]
                for v in versions:
                    mm = Version("%s.%s" % (v.major, v.minor))
                    if mm not in self._versions:
                        self._versions[mm] = v

    @runez.cached_property
    def latest(self) -> Version:
        """Latest version for this family"""
        self._fetch_versions()
        return self._latest

    @runez.cached_property
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

    client = RestClient("https://www.python.org/")

    # client = RestClient("https://api.github.com")
    # def get_available_versions(self):
    #     """Available versions as per github release tags"""
    #     r = self.client.get("repos/python/cpython/git/matching-refs/tags/v3.", logger=logging.debug)
    #     for item in r:
    #         ref = item.get("ref")
    #         if ref and ref.startswith("refs/tags/v"):
    #             ref = ref[11:]
    #             v = Version(ref)
    #             if v.is_valid and v.is_final and v.given_components and len(v.given_components) == 3 and (v.major, v.minor) > (3, 5):
    #                 yield v

    def get_available_versions(self):
        """Available versions as per python.org/ftp"""
        r = self.client.get_response("ftp/python/", logger=logging.debug)
        regex = re.compile(r'"(\d+\.\d+\.\d+)/"')
        if r.text:
            for line in r.text.splitlines():
                line = line.strip()
                if line:
                    m = regex.search(line)
                    if m:
                        v = Version(m.group(1))
                        if v.is_valid and v.is_final and "3.6" < v < "3.10":
                            yield v

    def get_builder(self):
        from portable_python.cpython import Cpython

        return Cpython


class PythonVersions:
    """Available python families, and their versions, as well as link to associated PythonBuilder class"""

    cpython = CPythonFamily()
    families = dict(cpython=cpython)

    _depot = None

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

    @classmethod
    def validated_spec(cls, spec: str) -> PythonSpec:
        spec = PythonSpec.to_spec(spec)
        if not spec.version or not spec.version.is_valid:
            runez.abort("Invalid python spec: %s" % runez.red(spec))

        if spec.version.text not in spec.text or len(spec.version.given_components) < 3:
            runez.abort("Please provide full desired version: %s is not good enough" % runez.red(spec))

        return spec
