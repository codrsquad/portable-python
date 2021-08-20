import os

import runez

from portable_python import LOG
from portable_python.builder import BuildSetup, PythonBuilder


@BuildSetup.python_builders.declare
class Cpython(PythonBuilder):
    """Build CPython binaries"""

    base_url = "https://www.python.org/ftp/python"

    @property
    def url(self):
        """Url of source tarball"""
        return f"{self.base_url}/{self.version}/Python-{self.version}.tar.xz"

    def xenv_cflags(self):
        yield "-Wno-unused-command-line-argument"

    def c_configure_args(self):
        yield from super().c_configure_args()
        yield "--with-ensurepip=upgrade"
        yield "--enable-optimizations"
        yield "--with-lto"
        if self.setup.is_active_module("openssl"):
            yield f"--with-openssl={self.deps}"

        if self.setup.is_active_module("tcl"):
            yield "--with-tcltk-includes=-I%s/include" % self.deps
            yield "--with-tcltk-libs=-L%s/lib" % self.deps

    def _finalize(self):
        self.cleanup_distribution()
        if self.setup.static:
            self._symlink_static_libs()

        main_python = self.correct_symlinks()

        # For some reason, pip upgrade doesn't work unless ensurepip/_bundled was cleaned up, so run it after 1st cleanup
        self.run(self.bin_folder / main_python, "-mpip", "install", "-U", "pip", "setuptools", "wheel")

        # Clean up again to remove pip _bundled stuff
        self.cleanup_distribution()

        # Regenerate __pycache__
        self.run(self.bin_folder / main_python, "-mcompileall")

        # Create tarball
        runez.compress(self.bin_folder.parent, self.tarball_path)

    def _symlink_static_libs(self):
        """Symlink libpython*.a to save space"""
        libs = []
        for dirpath, dirnames, filenames in os.walk(self.bin_folder.parent / "lib"):
            for name in filenames:
                if name.startswith("libpython"):
                    libs.append(os.path.join(dirpath, name))

        if len(libs) == 2:
            shorter, longer = sorted(libs, key=lambda x: len(x))
            shorter_size = runez.to_path(shorter).stat().st_size
            longer_size = runez.to_path(longer).stat().st_size
            if shorter_size == longer_size:  # Double-check that they are the same size (they should be identical)
                runez.symlink(longer, shorter)

    @runez.cached_property
    def cleanable_basenames(self):
        """Folders that are not useful in deliverable (test suites etc)"""
        r = {
            "__phello__.foo.py",
            "__pycache__",  # Clear it because lots of unneeded stuff is in there initially, -mcompileall regenerates it
            "_bundled",
            "idle_test",
            "test",
            "tests",
        }
        if not self.setup.static:
            # Don't keep static compilation file unless --static
            r.add(f"libpython{self.version.major}.{self.version.minor}.a")

        return r

    @runez.cached_property
    def cleanable_prefixes(self):
        """Files/folders that are not useful in deliverable, but name varies, can be identified by their prefix"""
        r = set()
        if not self.setup.static:
            r.add("config-%s.%s-" % (self.version.major, self.version.minor))

        return r

    def should_clean(self, basename):
        return basename in self.cleanable_basenames or any(basename.startswith(x) for x in self.cleanable_prefixes)

    def cleanup_distribution(self):
        cleaned = []
        for dirpath, dirnames, filenames in os.walk(self.bin_folder.parent):
            removed = []
            for name in dirnames:
                if self.should_clean(name):
                    # Remove unnecessary file, to save on space
                    full_path = os.path.join(dirpath, name)
                    removed.append(name)
                    cleaned.append(name)
                    runez.delete(full_path, logger=None)

            for name in removed:
                dirnames.remove(name)

            for name in filenames:
                if self.should_clean(name):
                    full_path = os.path.join(dirpath, name)
                    cleaned.append(name)
                    runez.delete(full_path, logger=None)

        if cleaned:
            names = runez.joined(sorted(set(cleaned)))
            LOG.info("Cleaned %s: %s" % (runez.plural(cleaned, "build artifact"), runez.short(names)))

    @staticmethod
    def actual_basename(path):
        """Follow symlink, for bin/python* symlinked exes"""
        if os.path.islink(path):
            path = runez.to_path(os.path.realpath(path))

        return path.name

    def correct_symlinks(self):
        with runez.CurrentFolder(self.bin_folder):
            main_python = None  # Basename of main python executable
            main_python_candidates = ("python", "python%s" % self.version.major, "python%s.%s" % (self.version.major, self.version.minor))
            all_files = {}
            files = {}
            symlinks = {}
            cleanable = ("2to3", "easy_install", "idle3", "pip", "pydoc", "wheel")
            for f in BuildSetup.ls_dir(self.bin_folder):
                if f.name.startswith(cleanable):
                    runez.delete(f)  # Get rid of old junk, can be pip installed if needed
                    continue

                if not main_python and f.name in main_python_candidates:
                    main_python = self.actual_basename(f)

                all_files[f.name] = f
                if f.is_symlink():
                    symlinks[f.name] = f

                else:
                    files[f.name] = f

            if main_python:
                if "python" not in all_files:
                    runez.symlink(main_python, "python")

                for f in files.values():
                    if f.name != main_python:
                        self._auto_correct_shebang(main_python, f)

            return main_python or "python"

    def _auto_correct_shebang(self, main_python, path):
        lines = []
        with open(path) as fh:
            for line in fh:
                if lines:
                    lines.append(line)

                elif not line.startswith("#!") or "bin/python" not in line:
                    return

                else:
                    lines.append("#!/bin/sh\n")
                    lines.append('"exec" "$(dirname $0)/%s" "$0" "$@"\n' % main_python)

        LOG.info("Auto-corrected shebang for %s" % runez.short(path))
        with open(path, "wt") as fh:
            for line in lines:
                fh.write(line)
