from portable_python.builder import BuildSetup, ModuleBuilder


@BuildSetup.module_builders.declare
class LibFFI(ModuleBuilder):

    @property
    def url(self):
        return f"https://github.com/libffi/libffi/releases/download/v{self.version}/libffi-{self.version}.tar.gz"

    @property
    def version(self):
        return "3.4.2"

    def _do_linux_compile(self):
        self.run("./configure", "--prefix=/deps", "--disable-shared")
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)


@BuildSetup.module_builders.declare
class Readline(ModuleBuilder):

    @property
    def url(self):
        return f"https://ftp.gnu.org/gnu/readline/readline-{self.version}.tar.gz"

    @property
    def version(self):
        return "8.1"

    def _do_linux_compile(self):
        self.run("./configure", "--prefix=/deps", "--disable-shared", "--with-curses")
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)


@BuildSetup.module_builders.declare
class Openssl(ModuleBuilder):

    @property
    def url(self):
        return f"https://www.openssl.org/source/openssl-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.1.1k"

    @staticmethod
    def compiler(setup):
        if setup.platform == "darwin":
            return "darwin64-%s-cc" % setup.architecture

        return "%s-%s" % (setup.platform, setup.architecture)

    def _do_linux_compile(self):
        self.run("./Configure", "--prefix=/deps", "--openssldir=/etc/ssl", self.compiler(self.setup), "no-shared")
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)


@BuildSetup.module_builders.declare
class Uuid(ModuleBuilder):

    @property
    def url(self):
        return f"https://sourceforge.net/projects/libuuid/files/libuuid-{self.version}.tar.gz"

    @property
    def version(self):
        return "1.0.3"

    def _do_linux_compile(self):
        self.run("./configure", "--prefix=/deps", "--disable-shared")
        self.run("make")
        self.run("make", "install", "DESTDIR=%s" % self.deps.parent)
