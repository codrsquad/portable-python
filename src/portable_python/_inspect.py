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


def pymodule_version_info(key, value, pymodule):
    if value:
        result = dict(version_field=key)
        if isinstance(value, bytes):
            value = value.decode("utf-8")

        if isinstance(value, tuple):
            value = ".".join(str(x) for x in value)

        result["version"] = value
        if hasattr(pymodule, "__file__"):
            result["path"] = pymodule.__file__

        return result


def pymodule_info(module_name, pymodule):
    fields = INSIGHTS.get(module_name)
    if fields:
        fields = fields.split()
        for f in fields:
            v = pymodule_version_info(f, getattr(pymodule, f, None), pymodule)
            if v:
                return v

    if hasattr(pymodule, "__file__"):
        return dict(path=pymodule.__file__)

    if hasattr(pymodule, "__spec__"):
        v = getattr(pymodule.__spec__, "origin")
        if v == "built-in":
            return dict(version=v)

    return dict(note=str(dir(pymodule)))


def module_report(module_name):
    try:
        return pymodule_info(module_name, __import__(module_name))

    except ImportError as e:
        return dict(version="*absent*", note=str(e))


def main(arg):
    if arg == "sysconfig":
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

    report = dict((k, module_report(k)) for k in arg.split(","))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1])  # pragma: no cover
