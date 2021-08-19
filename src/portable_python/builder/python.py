import os

import runez

from portable_python import LOG
from portable_python.builder import BuildSetup, PythonBuilder


@BuildSetup.python_builders.declare
class Cpython(PythonBuilder):
    """Build CPython binaries"""

    def default_modules(self):
        return "openssl"

    @property
    def url(self):
        """Url of source tarball"""
        return f"https://www.python.org/ftp/python/{self.version}/Python-{self.version}.tar.xz"

    def xenv_cflags(self):
        yield from super().xenv_cflags()
        yield "-Wno-unused-command-line-argument"
        if self.target.is_linux:
            yield "-m64"

    @property
    def c_configure_prefix(self):
        """--prefix to use for the ./configure program"""
        return self.prefix

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

    def _do_linux_compile(self):
        self.run_configure()
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.install_folder)
        self.cleanup_build_artifacts()
        self.finalize()

    def finalize(self):
        # For some reason, pip upgrade doesn't work unless ensurepip/_bundled was cleaned up, so run it after cleanup
        self.cleanup_build_artifacts()
        self.run(self.bin_folder / "python3", "-mpip", "install", "-U", "pip", "setuptools", "wheel")
        # Then clean up again (to remove the artifacts done by the pip run)
        self.cleanup_build_artifacts()
        self.correct_symlinks()
        if not self.setup.prefix:
            path = self.bin_folder.parent
            dest = "%s-%s-%s.tar.gz" % (self.setup.python_spec.family, self.version, self.target)
            dest = self.setup.dist_folder / dest
            runez.compress(path, dest)

    def cleanup_build_artifacts(self):
        cleanable_folders = {"_bundled", "idle_test", "test", "tests"}  # Get rid of test suites
        config_dupe = "config-%s.%s-" % (self.version.major, self.version.minor)  # Config folder with build artifacts
        if not self.setup.prefix:
            cleanable_folders.add("__pycache__")

        cleaned = []
        for dirpath, dirnames, filenames in os.walk(self.bin_folder.parent):
            removed = []
            for name in dirnames:
                if name in cleanable_folders or name.startswith(config_dupe):
                    # Remove unnecessary file, to save on space
                    full_path = os.path.join(dirpath, name)
                    removed.append(name)
                    cleaned.append(name)
                    runez.delete(full_path, logger=None)

            for name in removed:
                dirnames.remove(name)

            for name in filenames:
                if name in ("__phello__.foo.py",):
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
        expected_main_python = ("python", "python%s" % self.version.major, "python%s.%s" % (self.version.major, self.version.minor))
        with runez.CurrentFolder(self.bin_folder):
            main_python = None  # Basename of main python executable
            all_files = {}
            files = {}
            symlinks = {}
            cleanable = ("2to3", "easy_install", "idle3", "pip", "pydoc", "wheel")
            for f in BuildSetup.ls_dir(self.bin_folder):
                if f.name.startswith(cleanable):
                    runez.delete(f)  # Get rid of old junk, can be pip installed if needed
                    continue

                if not main_python and f.name in expected_main_python:
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
