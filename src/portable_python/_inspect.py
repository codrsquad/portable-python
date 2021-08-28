import json
import os
import sys

INSIGHTS = {
    "_curses": "version __version__",
    "_ctypes": "__version__",
    "_dbm": "library",
    "_gdbm": "_GDBM_VERSION",
    "_tkinter": "TCL_VERSION TK_VERSION",
    "_sqlite3": "sqlite_version version",
    "_ssl": "OPENSSL_VERSION",
    "dbm.gnu": "_GDBM_VERSION",
    "pip": "__version__",
    "readline": "_READLINE_LIBRARY_VERSION",
    "setuptools": "__version__",
    "tkinter": "TclVersion TkVersion",
    "wheel": "__version__",
    "zlib": "ZLIB_VERSION ZLIB_RUNTIME_VERSION",
}


def represented(key, value, source):
    if value:
        if isinstance(value, bytes):
            value = value.decode("utf-8")

        if isinstance(value, tuple):
            value = ".".join(str(x) for x in value)

        value = "%s=%s" % (key, value)
        if hasattr(source, "__file__"):
            value += " %s" % source.__file__

        return value


def module_representation(module_name, mod):
    fields = INSIGHTS.get(module_name)
    if fields:
        fields = fields.split()
        for f in fields:
            v = represented(f, getattr(mod, f, None), mod)
            if v:
                return v

    if hasattr(mod, "__file__"):
        return mod.__file__

    if hasattr(mod, "__spec__"):
        v = getattr(mod.__spec__, "origin")
        if v:
            return str(v)

    return str(dir(mod))


def module_report(module_name):
    try:
        return module_representation(module_name, __import__(module_name))

    except ImportError:
        return "*absent*"


def get_report(modules):
    report = dict((k, module_report(k)) for k in modules if k)
    prefixes = set(getattr(sys, x) for x in dir(sys) if "prefix" in x and "pycache" not in x)
    if len(prefixes) > 1:
        report["prefixes"] = " ".join(sorted(prefixes))

    return report


def get_import_names(names):
    default = "_bz2,_ctypes,_curses,_dbm,_gdbm,_lzma,_tkinter,_sqlite3,_ssl,_uuid,pip,readline,setuptools,wheel,zlib"
    if not names:
        names = default

    elif names == "all":
        names = "%s,_asyncio,_functools,_tracemalloc,dbm.gnu,tkinter" % default

    elif names[0] == "+":
        names = "%s,%s" % (default, names[1:])

    return [x for x in names.split(",") if x]


def main(args=None):
    names = args and args[0]
    if names == "sysconfig":
        import sysconfig

        abs_builddir = sysconfig.get_config_var("abs_builddir")
        secondary = None
        marker = "$^"
        if abs_builddir:
            abs_builddir = os.path.dirname(abs_builddir)
            if abs_builddir.startswith("/private"):
                secondary = abs_builddir[8:]  # pragma: no cover, edge case: whoever compiled didn't use realpath(tmp)

            elif not abs_builddir.startswith("/tmp"):  # nosec, just simplifying paths
                abs_builddir = os.path.dirname(abs_builddir)

            print("%s: %s  # original abs_builddir" % (marker, abs_builddir))

        for k, v in sorted(sysconfig.get_config_vars().items()):
            if abs_builddir:
                v = str(v).replace(abs_builddir, marker)
                if secondary:
                    v = v.replace(secondary, marker)  # pragma: no cover

            print("%s: %s" % (k, v))

        return

    report = get_report(get_import_names(names))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1:])  # pragma: no cover
