import collections
import fnmatch
import logging
import os
import pathlib
import re
from io import StringIO

import runez
import yaml


LOG = logging.getLogger(__name__)


DEFAULT_CONFIG = """
folders:
  build: build
  destdir: "{build}"
  dist: dist
  logs: ""
  prefix: /{version}
  sources: build/sources

ext: gz
cpython-always-clean-default:
  - __phello__.foo.py
  - __pycache__
  - _test*capi.*
  - idle_test/
  - test/
  - tests/

# By default, clean old cruft (this can be overridden in user config)
cpython-always-clean:
  - bin/2to3* bin/easy_install* bin/idle3* bin/pydoc* bin/pyvenv* bin/wheel*
cpython-always-clean-linux: wininst-*
cpython-always-clean-macos: wininst-*

cpython-pip-install: wheel
cpython-symlink: bin/python

cpython-configure:
  - --enable-optimizations      # 3.6+
  - --with-lto                  # 3.6+
  - --with-ensurepip=upgrade    # 3.6+

windows:
  ext: zip

macos:
  allowed-system-libs: .*
  env:
    MACOSX_DEPLOYMENT_TARGET: 10.14
  cpython-modules: xz openssl
  arm64:
    env:
      MACOSX_DEPLOYMENT_TARGET: 11
"""


class Config:
    """Overall config, the 1st found (most specific) setting wins"""

    def __init__(self, paths=None, target=None):
        """
        Args:
            paths (str | list | None): Path(s) to config file(s)
            target (str | runez.system.PlatformId | None): Target platform (for testing, defaults to current platform)
        """
        self.paths = runez.flattened(paths, split=",")
        if not isinstance(target, runez.system.PlatformId):
            target = runez.system.PlatformId(target)

        self.target = target
        self.sources = []  # type: list[ConfigSource]
        self.by_path = {}
        for path in self.paths:
            self.load(path)

        default = self.parsed_yaml(DEFAULT_CONFIG, "default config")
        default = ConfigSource("default config", default)
        self.sources.append(default)

    def __repr__(self):
        return "%s [%s]" % (runez.plural(self.sources, "config source"), self.target)

    def get_value(self, *key, by_platform=True):
        """
        Args:
            key (str | tuple): Key to look up, tuple represents hierarchy, ie: a/b -> (a, b)
            by_platform (bool): If True, value can be configured by platform

        Returns:
            Associated value, if any
        """
        if by_platform:
            keys = (self.target.platform, self.target.arch, *key), (self.target.platform, *key), key

        else:
            keys = (key, )

        for k in keys:
            for source in self.sources:
                v = source.get_value(k)
                if v is not None:
                    return v

    def config_files_report(self):
        """One liner describing which config files are used, if any"""
        sources = self.sources
        if sources and len(sources) > 1:
            return "Config files: %s" % runez.joined(sources[:-1], delimiter=", ")

        return "no config"

    def represented(self):
        """Textual (yaml) representation of all configs"""
        result = []
        for source in self.sources:
            result.append("%s:" % runez.bold(source))
            result.append(source.represented())

        return runez.joined(result, delimiter="\n")

    @staticmethod
    def represented_filesize(*paths, base=1024):
        size = runez.filesize(*paths, logger=LOG.debug)
        return runez.bold(runez.represented_bytesize(size, base=base) if size else "-")

    @staticmethod
    def delete(path):
        size = runez.filesize(path)
        runez.delete(path, logger=None)
        LOG.info("Deleted %s (%s)" % (runez.short(path), runez.represented_bytesize(size)))
        return size

    @staticmethod
    def parsed_yaml(text, source):
        try:
            return yaml.safe_load(text)

        except Exception as e:
            runez.abort("Invalid yaml in %s: %s" % (runez.bold(runez.short(source)), e))

    def _cleanup_folder_with_spec(self, module, spec):
        spec = runez.flattened(spec, split=True, unique=True)
        if spec:
            spec = [module.setup.folders.formatted(x) for x in spec]
            deleted_size = 0
            matcher = FileMatcher(spec)
            LOG.info("Applying clean-up spec: %s" % matcher)
            cleaned = []
            for dirpath, dirnames, filenames in os.walk(module.install_folder):
                removed = []
                dirpath = runez.to_path(dirpath)
                for name in dirnames:
                    full_path = dirpath / name
                    if matcher.is_match(full_path):
                        removed.append(name)
                        cleaned.append(name)
                        deleted_size += self.delete(full_path)

                for name in removed:
                    dirnames.remove(name)

                for name in filenames:
                    full_path = dirpath / name
                    if matcher.is_match(full_path):
                        cleaned.append(name)
                        deleted_size += self.delete(full_path)

            if cleaned:
                names = runez.joined(sorted(set(cleaned)))
                deleted_size = runez.represented_bytesize(deleted_size)
                LOG.info("Cleaned %s (%s): %s" % (runez.plural(cleaned, "build artifact"), deleted_size, runez.short(names)))

    def cleanup_folder(self, module):
        """

        Args:
            module (portable_python.PythonBuilder): Associated python builder module
        """
        key = "%s-always-clean" % module.m_name
        general_clean = (
            self.get_value("%s-default" % key),
            self.get_value(key),
            self.get_value("%s-%s" % (key, self.target.platform)),
        )
        self._cleanup_folder_with_spec(module, general_clean)
        original_size = runez.filesize(module.install_folder)
        self._cleanup_folder_with_spec(module, self.get_value("%s-clean" % module.m_name))
        self.symlink_duplicates(module.install_folder)
        # Log size before and after cleanup
        cleaned_size = runez.filesize(module.install_folder)
        original_size = runez.represented_bytesize(original_size)
        cleaned_size = runez.represented_bytesize(cleaned_size)
        LOG.info("Original size: %s, cleaned size: %s" % (original_size, cleaned_size))

    def symlink_duplicates(self, folder):
        if self.target.is_linux or self.target.is_macos:
            seen = collections.defaultdict(list)
            _find_file_duplicates(seen, folder)
            duplicates = {k: v for k, v in seen.items() if len(v) > 1}
            for dupes in duplicates.values():
                dupes = sorted(dupes, key=lambda x: len(str(x)))
                if len(dupes) == 2:
                    shorter, longer = dupes
                    if str(longer).startswith(str(shorter.parent)):
                        runez.symlink(longer, shorter, logger=LOG.info)

    @staticmethod
    def real_path(path: pathlib.Path):
        if path and path.exists():
            if path.is_symlink():
                path = runez.to_path(os.path.realpath(path))

            return path

    @staticmethod
    def candidate_exes(basename: str, version):
        return basename, "%s%s" % (basename, version.major), "%s%s" % (basename, version.mm)

    @staticmethod
    def find_main_file(desired: pathlib.Path, version, fatal=None):
        p = Config.real_path(desired)
        if p:
            return p

        for c in Config.candidate_exes(desired.name, version):
            fc = Config.real_path(desired.parent / c)
            if fc:
                return fc

        if fatal is not None:
            return runez.abort("Could not determine real path for %s" % runez.short(desired), return_value=desired, fatal=fatal)

    def ensure_main_file_symlinks(self, module):
        folder = module.install_folder
        version = module.version
        relative_paths = self.get_value("%s-symlink" % module.m_name)
        relative_paths = runez.flattened(relative_paths, split=True)
        if relative_paths:
            for rp in relative_paths:
                desired = folder / rp
                main_file = self.find_main_file(desired, version)
                if main_file and main_file != desired:
                    runez.symlink(main_file, desired, overwrite=False)

    @staticmethod
    def auto_correct_shebang(path: pathlib.Path, main_python: pathlib.Path):
        if path == main_python or not path.is_file() or path.is_symlink():
            return

        lines = []
        with open(path) as fh:
            try:
                for line in fh:
                    if lines:
                        lines.append(line)
                        continue

                    if not line.startswith("#!") or "bin/python" not in line:
                        return

                    lines.append("#!/bin/sh\n")
                    lines.append('"exec" "$(dirname $0)/%s" "$0" "$@"\n' % main_python.name)

            except UnicodeError:
                return

        if lines:
            LOG.info("Auto-corrected shebang for %s" % runez.short(path))
            with open(path, "wt") as fh:
                for line in lines:
                    fh.write(line)

    def load(self, path, base=None):
        if path:
            front = False
            if path.startswith("+"):
                front = True
                path = path[1:]

            path = runez.resolved_path(path, base=base)
            path = runez.to_path(path)
            if path.exists():
                with open(path) as fh:
                    data = self.parsed_yaml(fh, path)
                    source = ConfigSource(path, data)
                    if front:
                        self.sources.insert(0, source)

                    else:
                        self.sources.append(source)

                    self.by_path[str(path)] = source
                    for include in runez.flattened(source.get_value("include"), split=True):
                        self.load(include, base=path.parent)


class ConfigSource:
    """Settings from one config file"""

    def __init__(self, source, data):
        self.source = source
        self.data = data

    def __repr__(self):
        return runez.short(self.source)

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


class FileMatcher:

    def __init__(self, clean_spec):
        self.matches = []
        for spec in clean_spec:
            self.matches.append(SingleFileMatch(spec))

    def __repr__(self):
        return runez.joined(self.matches)

    def is_match(self, path: pathlib.Path):
        for m in self.matches:
            if m.is_match(path):
                return path


class SingleFileMatch:

    _on_folder = False
    _rx_basename = None
    _rx_path = None

    def __init__(self, spec: str):
        self.spec = spec
        if spec.endswith("/"):
            spec = spec[:-1]
            self._on_folder = True

        if "/" in spec:
            # lib/*/config-{python_mm}-\w+/
            path = ".*/%s$" % os.path.dirname(spec).replace("*", ".*").strip("/")
            spec = os.path.basename(spec)
            self._rx_path = re.compile(path)

        self._rx_basename = spec

    def __repr__(self):
        return self.spec

    def is_match(self, path: pathlib.Path):
        if self._on_folder == path.is_dir():
            if self._rx_path:
                m = self._rx_path.match(str(path.parent))
                if not m:
                    return False

            return fnmatch.fnmatch(path.name, self._rx_basename)


def _find_file_duplicates(seen, folder):
    for p in runez.ls_dir(folder):
        if p.name not in ("__pycache__", "site-packages"):
            if p.is_dir():
                _find_file_duplicates(seen, p)

            elif p.is_file() and runez.filesize(p) > 10000:
                c = runez.checksum(p)
                seen[c].append(p)
