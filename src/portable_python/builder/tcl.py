import runez

from portable_python.builder import BuildSetup, ModuleBuilder


@BuildSetup.module_builders.declare
class Tcl(ModuleBuilder):  # pragma: no cover

    @property
    def url(self):
        return f"https://prdownloads.sourceforge.net/tcl/tcl{self.version}-src.tar.gz"

    @property
    def version(self):
        return "8.6.10"

    def _do_linux_compile(self):
        for path in BuildSetup.ls_dir(self.build_folder / "pkgs"):
            if path.name.startswith(("sqlite", "tdbc")):
                # Remove packages we don't care about and can pull in unwanted symbols
                runez.delete(path)

        with runez.CurrentFolder("unix"):
            patch_file("Makefile.in", "--enable-shared ", "--enable-shared=no ")
            self.run("./configure", "--prefix=/deps", "--enable-shared=no", "--enable-threads")
            self.run("make")
            self.run("make", "install", "DESTDIR=%s" % self.deps.parent)
            self.run("make", "install-private-headers", "DESTDIR=%s" % self.deps.parent)


@BuildSetup.module_builders.declare
class Tk(ModuleBuilder):  # pragma: no cover

    @property
    def url(self):
        return f"https://prdownloads.sourceforge.net/tcl/tk{self.version}-src.tar.gz"

    @property
    def version(self):
        return "8.6.10"

    def _do_linux_compile(self):
        extra = []
        if self.setup.is_macos:
            extra.append("--enable-aqua=yes")
            extra.append("--without-x")

        else:
            extra.append(f"--x-includes={self.deps}/include")
            extra.append(f"--x-libraries={self.deps}/lib")

        with runez.CurrentFolder("unix"):
            self.run("./configure", "--prefix=/deps", f"--with-tcl={self.deps}/lib", "--enable-shared=no", "--enable-threads", *extra)
            self.run("make")
            self.run("make", "install", "DESTDIR=%s" % self.deps.parent)
            self.run("make", "install-private-headers", "DESTDIR=%s" % self.deps.parent)


@BuildSetup.module_builders.declare
class Tix(ModuleBuilder):  # pragma: no cover

    @property
    def url(self):
        return f"https://github.com/python/cpython-source-deps/archive/tix-{self.version}.tar.gz"

    @property
    def version(self):
        return "8.4.3.6"

    def xenv_cflags(self):
        yield from super().xenv_cflags()
        yield "-DUSE_INTERP_RESULT"  # -DUSE_INTERP_RESULT is to allow tix to use deprecated fields or something like that

    def _do_linux_compile(self):
        args = [f"--with-tcl={self.deps}/lib", f"--with-tk={self.deps}/lib", "--enable-shared=no"]
        if self.setup.is_macos:
            args.append("--without-x")

        else:
            args.append("--x-includes=/deps/include")
            args.append("--x-libraries=/deps/lib")

        self.run("/bin/sh", "configure", "--prefix=/deps", *args)
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)


def patch_file(path, old, new):  # pragma: no cover
    if runez.DRYRUN:
        print("Would patch %s" % runez.short(path))
        return

    path = runez.to_path(path).absolute()
    with runez.TempFolder():
        changed = 0
        with open("patched", "wt") as fout:
            with open(path) as fin:
                for line in fin:
                    if old in line:
                        line = line.replace(old, new)
                        changed += 1

                    fout.write(line)

        if changed:
            runez.move("patched", path)
