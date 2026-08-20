from portable_python import ModuleBuilder


class GettextTiny(ModuleBuilder):
    """Prevents libintl getting picked up from /usr/local"""

    @property
    def url(self):
        return self.cfg_url(self.version) or f"https://github.com/sabotage-linux/gettext-tiny/archive/refs/tags/v{self.version}.tar.gz"

    @property
    def version(self):
        # Small, dormant project (0.3.3 released Jan 2026), bump freely within the 0.3 line
        # Check https://github.com/sabotage-linux/gettext-tiny/releases
        return self.cfg_version("0.3.3")

    def _do_linux_compile(self):
        self.run_make("LIBINTL=NOOP")
        self.run_make("LIBINTL=NOOP", f"DESTDIR={self.deps}", "prefix=/", "install")


class Toolchain(ModuleBuilder):
    """Additional libs we compile to ensure portable build is possible"""

    @classmethod
    def candidate_modules(cls):
        yield GettextTiny
