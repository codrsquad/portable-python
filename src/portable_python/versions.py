"""
Tracking only a handful of most recent (and non-EOL) versions by design
Not trying to do historical stuff here, older (or EOL-ed) versions will be removed from the list without notice

Usage:
    from portable_python.versions import PythonVersions

    print(PythonVersions.cpython.latest)
    print(PythonVersions.cpython.versions)
"""

import runez
from runez.pyenv import PythonDepot, PythonSpec, Version


CPYTHON_VERSIONS = """
3.9.7
3.8.11
3.7.11
3.6.14
"""


class VersionFamily:
    """Latest versions for a python family"""

    def __init__(self, family, versions):
        self.family = family
        self.versions = sorted((Version(v) for v in versions.split()), reverse=True)

    def __repr__(self):
        return runez.plural(self.versions, "%s version" % self.family)

    @property
    def latest(self) -> Version:
        """Latest version for this family"""
        return self.versions[0]

    @property
    def builder(self):
        if self.family == "cpython":
            from portable_python.cpython import Cpython

            return Cpython


class PythonVersions:

    cpython = VersionFamily("cpython", CPYTHON_VERSIONS)
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

        return cls._depot.find_python(spec, fatal=False)

    @classmethod
    def validated_spec(cls, spec: str) -> PythonSpec:
        spec = PythonSpec.to_spec(spec)
        if not spec.version or not spec.version.is_valid:
            runez.abort("Invalid python spec: %s" % runez.red(spec))

        if spec.version.text not in spec.text or len(spec.version.given_components) < 3:
            runez.abort("Please provide full desired version: %s is not good enough" % runez.red(spec))

        return spec
