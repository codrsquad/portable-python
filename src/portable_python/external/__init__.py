from portable_python import ModuleBuilder


class GettextTiny(ModuleBuilder):
    """Prevents libintl getting picked up from /usr/local"""

    @property
    def url(self):
        return f"https://github.com/sabotage-linux/gettext-tiny/archive/refs/tags/v{self.version}.tar.gz"

    @property
    def version(self):
        return self.cfg_version("0.3.2")

    def _do_linux_compile(self):
        self.run_make("LIBINTL=NOOP", cpu_count=0)
        self.run_make("LIBINTL=NOOP", f"DESTDIR={self.deps}", "prefix=/", "install", cpu_count=0)


class Toolchain(ModuleBuilder):
    """Additional libs we compile to ensure portable build is possible"""

    @classmethod
    def candidate_modules(cls):
        yield GettextTiny
