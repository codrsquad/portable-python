import pathlib
from io import StringIO

import runez
import yaml


DEFAULT_CONFIG = """
ext: gz

windows:
  ext: zip


macos:
  allowed-system-libs: .*
  env:
    MACOSX_DEPLOYMENT_TARGET: 10.14
  cpython-modules: xz openssl gdbm

cpython-configure:
  - --enable-optimizations
  - --with-lto
  - --with-pydebug
  - --with-ensurepip=upgrade
"""


class ConfigSource:
    """Settings from one config file"""

    def __init__(self, source, data):
        self.source = source
        self.data = data

    def __repr__(self):
        return "%s config" % runez.short(self.source)

    def represented(self):
        """Textual (yaml) representation of this config"""
        buffer = StringIO()
        yaml.dump(self.data, stream=buffer)
        return buffer.getvalue()

    def get_value(self, key):
        """
        Args:
            key (str | tuple): Key to look up, tuple represents hierarchy, ie: a/b -> (a, b)

        Returns:
            Associated value, if any
        """
        return self._deep_get(self.data, key)

    def _deep_get(self, data, key):
        if not key or not isinstance(data, dict):
            return None

        if isinstance(key, tuple):
            if len(key) > 1:
                value = self._deep_get(data, key[0])
                return self._deep_get(value, key[1:])

            key = key[0]

        value = data.get(key)
        if value is not None:
            return value


class Config:
    """Overall config, the 1st found (most specific) setting wins"""

    base_folder: pathlib.Path = None
    dist_folder: pathlib.Path = None
    main_build_folder: pathlib.Path = None
    path: pathlib.Path = None

    def __init__(self, path=None, base_folder=None, target=None, replaces=None):
        """
        Args:
            path (str): Path to config file
            base_folder (str | None): Base folder to use (for build/ and dist/ folders)
            target (str | runez.system.PlatformId | None): Target platform (for testing, defaults to current platform)
            replaces (Config): Internal: other config this config is replacing
        """
        if isinstance(replaces, Config):
            path = path or replaces.path
            base_folder = base_folder or replaces.base_folder

        elif base_folder:
            base_folder = runez.to_path(base_folder, no_spaces=True).absolute()

        if path:
            path = runez.to_path(path).absolute()

        if not isinstance(target, runez.system.PlatformId):
            target = runez.system.PlatformId(target)

        self.path = path
        self.target = target
        self.sources = []  # type: list[ConfigSource]
        self.by_path = {}
        if path:
            self.load(path)
            default = yaml.safe_load(DEFAULT_CONFIG)
            default = ConfigSource("default", default)
            self.sources.append(default)

        if base_folder:
            base_folder = runez.to_path(base_folder, no_spaces=True).absolute()

        if base_folder != self.base_folder:
            self.base_folder = base_folder
            self.main_build_folder = base_folder / "build"
            self.dist_folder = base_folder / "dist"

    def __repr__(self):
        return "%s, %s [%s]" % (runez.short(self.path), runez.plural(self.sources, "config source"), self.target)

    def load(self, path):
        if path.exists():
            with open(path) as fh:
                data = yaml.safe_load(fh)
                source = ConfigSource(path, data)
                self.sources.append(source)
                self.by_path[str(path)] = source
                include = source.get_value("include")
                if include:
                    include = runez.resolved_path(include, base=path.parent)
                    self.load(runez.to_path(include))

    def represented(self):
        """Textual (yaml) representation of all configs"""
        result = []
        for source in self.sources:
            result.append("%s:" % runez.bold(source))
            result.append(source.represented())

        return runez.joined(result, delimiter="\n")

    def get_value(self, key):
        """
        Args:
            key (str | tuple): Key to look up, tuple represents hierarchy, ie: a/b -> (a, b)

        Returns:
            Associated value, if any
        """
        paths = self._key_paths(key)
        for k in paths:
            for source in self.sources:
                v = source.get_value(k)
                if v is not None:
                    return v

    def _key_paths(self, key):
        return (self.target.platform, self.target.arch, key), (self.target.platform, key), key
