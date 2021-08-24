import runez
from runez.pyenv import PythonSpec, Version

from portable_python import LOG


CPYTHON_VERSIONS = """
3.9.6
3.9.5
3.8.11
3.7.11
3.6.14
"""


class VersionList:

    def __init__(self, family, versions):
        self.family = family
        self.versions = [Version(v) for v in versions.split()]

    def __repr__(self):
        return "%s [%s]" % (self.family, runez.plural(self.versions, "version"))

    @property
    def latest(self) -> Version:
        """Latest version for this family"""
        return self.versions[0]


class PythonVersions:

    cpython = VersionList("cpython", CPYTHON_VERSIONS)

    families = dict(cpython=cpython)

    @classmethod
    def family(cls, family_name, fatal=True) -> VersionList:
        fam = cls.families.get(family_name)
        if fatal and not fam:
            runez.abort(f"Python family '{family_name}' is not yet supported")

        return fam

    @classmethod
    def validated_spec(cls, spec) -> PythonSpec:
        spec = PythonSpec.to_spec(spec)
        if not spec.version or not spec.version.is_valid:
            runez.abort("Invalid python spec: %s" % runez.red(spec))

        fam = cls.family(spec.family)
        if spec.version not in fam.versions:
            LOG.warning("%s is not in the supported list, your mileage may vary" % spec)

        return spec
