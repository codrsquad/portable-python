import os

import runez
from runez.pyenv import Version

from portable_python import Cleanable, LOG, PPG, PythonBuilder
from portable_python.external.xcpython import Bdb, Bzip2, Gdbm, LibFFI, Openssl, Readline, Sqlite, TkInter, Uuid, Xz, Zlib


class Cpython(PythonBuilder):
    """Build CPython binaries"""

    _main_python = None

    @classmethod
    def candidate_modules(cls):
        return [LibFFI, Zlib, Xz, Bzip2, Readline, Openssl, Sqlite, Bdb, Gdbm, TkInter, Uuid]

    @property
    def url(self):
        """Url of source tarball"""
        return f"https://www.python.org/ftp/python/{self.version}/Python-{self.version}.tar.xz"

    # noinspection PyMethodMayBeStatic
    # noinspection PyPep8Naming
    def xenv_CFLAGS(self):
        yield "-Wno-unused-command-line-argument"

    def c_configure_args(self):
        configured = PPG.config.get_value("cpython-configure")
        if configured:
            yield from configured

        yield "--enable-shared=%s" % ("yes" if self.setup.prefix else "no")
        if self.active_module(LibFFI):
            yield f"LIBFFI_INCLUDEDIR={self.deps_lib}"
            yield "--with-system-ffi=no"

        db_order = [
            self.active_module(Gdbm) and "gdbm",
            self.active_module(Bdb) and "bdb",
        ]
        db_order = runez.joined(db_order, delimiter=":")
        if db_order:
            yield f"--with-dbmliborder={db_order}"

        if self.active_module(Openssl):
            yield f"--with-openssl={self.deps}"

        tkinter = self.active_module(TkInter)
        if tkinter:
            mm = Version.from_text(tkinter.version)
            mm = "%s.%s" % (mm.major, mm.minor)
            yield f"--with-tcltk-includes=-I{self.deps}/include"
            yield f"--with-tcltk-libs=-L{self.deps_lib} -ltcl{mm} -ltk{mm}"

    def _do_linux_compile(self):
        self.run_configure("./configure", self.c_configure_args(), prefix=self.c_configure_prefix)
        self.run_make()
        self.run_make("install", f"DESTDIR={self.build_root}")

    @property
    def python_mm(self):
        return "python%s.%s" % (self.version.major, self.version.minor)

    @property
    def main_python(self):
        if self._main_python is None:
            self._main_python = self._find_main_basename("python")

        return self._main_python or "python"

    def _finalize(self):
        bin_python = self.bin_folder / self.main_python
        extras = PPG.config.get_value("pip-install")
        if extras:
            extras = runez.flattened(extras, split=" ")
            for extra in extras:
                self.run(bin_python, "-mpip", "install", "-U", extra, fatal=False)

        self.correct_symlinks()
        self.cleanup_distribution()
        self.run(bin_python, "-mcompileall")

    def cleanup_distribution(self):
        cleanable_prefixes = set()
        cleanable_basenames = {
            "__phello__.foo.py",
            "__pycache__",  # Clear it because lots of unneeded stuff is in there initially, -mcompileall regenerates it
            "idle_test",
            "test",
            "tests",
        }
        if Cleanable.libpython in self.setup.requested_clean:
            cleanable_prefixes.add(f"lib{self.python_mm}")
            cleanable_prefixes.add("config-%s.%s-" % (self.version.major, self.version.minor))

        cleaned = []
        for dirpath, dirnames, filenames in os.walk(self.install_folder):
            removed = []
            for name in dirnames:
                if name in cleanable_basenames or any(name.startswith(x) for x in cleanable_prefixes):
                    # Remove unnecessary file, to save on space
                    full_path = os.path.join(dirpath, name)
                    removed.append(name)
                    cleaned.append(name)
                    runez.delete(full_path, logger=None)

            for name in removed:
                dirnames.remove(name)

            for name in filenames:
                if name in cleanable_basenames or any(name.startswith(x) for x in cleanable_prefixes):
                    full_path = os.path.join(dirpath, name)
                    cleaned.append(name)
                    runez.delete(full_path, logger=None)

        if cleaned:
            names = runez.joined(sorted(set(cleaned)))
            LOG.info("Cleaned %s: %s" % (runez.plural(cleaned, "build artifact"), runez.short(names)))

    def correct_symlinks(self):
        with runez.CurrentFolder(self.bin_folder):
            all_files = {}
            files = {}
            symlinks = {}
            cleanable = set()
            if Cleanable.bin in self.setup.requested_clean:
                cleanable.update(["2to3", "easy_install", "idle3", "pydoc"])

            if Cleanable.pip in self.setup.requested_clean:
                cleanable.add("pip")

            for f in runez.ls_dir(self.bin_folder):
                if any(f.name.startswith(x) for x in cleanable):
                    runez.delete(f)  # Get rid of old junk from bin/ folder, can be pip installed if needed
                    continue

                all_files[f.name] = f
                if f.is_symlink():
                    symlinks[f.name] = f

                else:
                    files[f.name] = f

            self.ensure_main_symlink(all_files, "python", "pip")
            for f in files.values():
                if f.name != self.main_python:
                    self._auto_correct_shebang(f)

    def ensure_main_symlink(self, all_files, *basenames):
        for basename in basenames:
            if basename not in all_files:
                main_basename = self._find_main_basename(basename)
                if main_basename:
                    runez.symlink(main_basename, basename)

    def _find_main_basename(self, basename):
        candidates = [basename, "%s%s" % (basename, self.version.major)]
        if basename == "python":
            candidates.append(self.python_mm)

        for f in runez.ls_dir(self.bin_folder):
            if f.name in candidates:
                return runez.basename(f, extension_marker=None, follow=True)

    def _auto_correct_shebang(self, path):
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
                    lines.append('"exec" "$(dirname $0)/%s" "$0" "$@"\n' % self.main_python)

            except UnicodeError:
                return

        LOG.info("Auto-corrected shebang for %s" % runez.short(path))
        with open(path, "wt") as fh:
            for line in lines:
                fh.write(line)
