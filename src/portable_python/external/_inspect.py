import json
import os
import re
import sys
import sysconfig


RX_VERSION = re.compile(r"\d\.\d")
INSIGHTS = {
    "_gdbm": "_GDBM_VERSION",
    "_tkinter": "TCL_VERSION TK_VERSION",
    "_sqlite3": "sqlite_version version",
    "_ssl": "OPENSSL_VERSION",
    "dbm.gnu": "_GDBM_VERSION",
    "ensurepip": "_PIP_VERSION",
    "pyexpat": "version_info",
    "readline": "_READLINE_LIBRARY_VERSION",
    "tkinter": "TclVersion TkVersion",
    "zlib": "ZLIB_VERSION ZLIB_RUNTIME_VERSION",
}


def get_version(text):
    if text:
        if isinstance(text, bytes):
            text = text.decode("utf-8")

        elif isinstance(text, tuple):
            text = ".".join(str(x) for x in text)

        else:
            text = str(text)

        if text and RX_VERSION.search(text):
            return text.splitlines()[0]


def pymodule_version_info(key, value, pymodule):
    version = get_version(value)
    if version:
        result = dict(version_field=key, version=version)
        if hasattr(pymodule, "__file__"):
            result["path"] = pymodule.__file__

        return result


def pymodule_info(module_name, pymodule):
    fields = INSIGHTS.get(module_name)
    fields = fields.split() if fields else ["__version__", "version", "VERSION"]
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

    except Exception as e:
        note = str(e)
        if "No module named" in note:
            return dict(version="*absent*")

        return dict(version="*absent*", note=note)


def get_srcdir():
    srcdir = sysconfig.get_config_var("srcdir")
    if not srcdir or len(srcdir) < 3:
        srcdir = sysconfig.get_config_var("DESTSHARED")  # edge case: py2 reports an odd '.' as srcdir

    return srcdir


def get_simplified_dirs(path):
    result = []
    if path:
        path = os.path.dirname(path)
        result.append(path)
        if path.startswith("/private"):
            result.append(path[8:])  # whoever compiled didn't use realpath(tmp)

        elif not path.startswith("/tmp"):  # nosec, just simplifying paths
            result.append(os.path.dirname(result[0]))

    return result


def main(arg):
    if arg == "sysconfig":
        marker = "$^"
        simplified_dirs = get_simplified_dirs(sysconfig.get_config_var("abs_builddir"))
        if simplified_dirs:
            print("# '%s' is original abs_builddir:" % marker)
            print("%s: %s\n" % (marker, simplified_dirs[0]))

        for k, v in sorted(sysconfig.get_config_vars().items()):
            for sp in simplified_dirs:
                v = str(v).replace(sp, marker)

            print("%s: %s" % (k, v))

        return

    if arg and not arg.startswith("-"):
        report = dict((k, module_report(k)) for k in arg.split(","))
        report = dict(report=report, srcdir=get_srcdir(), prefix=sysconfig.get_config_var("prefix"))
        print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
