import os
import pathlib

import runez

from portable_python import LOG
from portable_python.builder import BuildSetup, ModuleBuilder


@BuildSetup.python_builders.declare
class Cpython(ModuleBuilder):
    """Build CPython binaries"""

    bin_folder: pathlib.Path = None
    prefix: str = None
    target: pathlib.Path = None

    def attach(self, setup):
        super().attach(setup)
        self.target = self.setup.build_folder
        self.prefix = self.version.text
        if self.setup.prefix:
            # Debian-style
            self.target = self.target / "root"
            self.prefix = self.setup.prefix.strip("/").format(python_version=self.version)

        self.bin_folder = self.target / self.prefix / "bin"

    @property
    def url(self):
        """Url of source tarball"""
        return f"https://www.python.org/ftp/python/{self.version}/Python-{self.version}.tar.xz"

    @property
    def version(self):
        return self.setup.python_spec.version

    def default_modules(self):
        """Default modules to compile"""
        return "readline,openssl"

    def xenv_cflags(self):
        yield from super().xenv_cflags()
        yield self.checked_folder(self.deps / "include/uuid", prefix="-I")
        yield self.checked_folder(self.deps / "include/readline", prefix="-I")
        yield "-Werror=unguarded-availability-new"

    def _do_linux_compile(self):
        extra = []
        if self.setup.is_active_module("openssl"):
            extra.append(f"--with-openssl={self.deps}")

        if self.setup.is_active_module("tcl"):
            extra.append("--with-tcltk-includes=-I%s/include" % self.deps)
            extra.append("--with-tcltk-libs=-L%s/lib" % self.deps)

        if not self.setup.prefix:
            extra.append("--disable-shared")

        # if self.setup.is_macos:
        #     extra.append("ac_cv_lib_intl_textdomain=no")
        #     extra.append("ac_cv_func_preadv=no")
        #     extra.append("ac_cv_func_pwritev=no")

        self.run(
            "./configure",
            "--prefix=/%s" % self.prefix,
            "--with-ensurepip=upgrade",
            "--enable-optimizations",
            "--with-lto",
            *extra,
        )
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.target)
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
            dest = "%s.tar.gz" % self.version
            dest = self.setup.dist_folder / dest
            runez.compress(path, dest)

    def cleanup_build_artifacts(self):
        libs = []
        cleanable = {"_bundled", "idle_test", "test", "tests"}  # Get rid of test suites
        if not self.setup.prefix:
            cleanable.add("__pycache__")

        cleanedup = 0
        for dirpath, dirnames, filenames in os.walk(self.bin_folder.parent):
            removed = []
            for name in dirnames:
                if name in cleanable:
                    # Remove unnecessary file, to save on space
                    full_path = os.path.join(dirpath, name)
                    removed.append(name)
                    cleanedup += 1
                    runez.delete(full_path, logger=None)

            for name in removed:
                dirnames.remove(name)

            for name in filenames:
                full_path = os.path.join(dirpath, name)
                if name.startswith("libpython"):
                    libs.append(full_path)

        if cleanedup:
            LOG.info("Cleaned up %s build artifacts" % cleanedup)

        if runez.DRYRUN:
            mm = "%s.%s" % (self.version.major, self.version.minor)
            pmm = "python%s" % mm
            lp = "lib%s.a" % pmm
            libs = ["lib/%s/config-%s-%s/%s" % (pmm, mm, self.setup.platform, lp), "lib/%s" % lp]

        if len(libs) == 2:
            shorter, longer = libs
            if len(shorter) > len(longer):
                shorter, longer = longer, shorter

            shorter = runez.to_path(shorter)
            longer = runez.to_path(longer)
            if not shorter.is_symlink() and not longer.is_symlink():
                runez.symlink(longer, shorter)

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
            for f in BuildSetup.ls_dir(self.bin_folder):
                if f.name.startswith(("2to3", "easy_install", "idle3")):
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
