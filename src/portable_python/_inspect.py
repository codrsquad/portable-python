import json
import sys

BASE_PREFIX = getattr(sys, "base_prefix", getattr(sys, "real_prefix", sys.prefix))
INSIGHTS = dict(
    _dbm="library",
    _tkinter="TCL_VERSION TK_VERSION",
    _sqlite3="sqlite_version version",
    _ssl="OPENSSL_VERSION",
    readline="_READLINE_LIBRARY_VERSION",
)


def module_representation(module_name, mod):
    fields = INSIGHTS.get(module_name)
    if fields:
        fields = fields.split()
        for f in fields:
            v = getattr(mod, f, None)
            if v:
                v = "%s=%s" % (f, v)
                if hasattr(mod, "__file__"):
                    v += " %s" % mod.__file__

                return v

    for f in ("__file__", "__spec__"):
        v = getattr(mod, f, None)
        if v:
            if isinstance(v, str) and v.startswith(BASE_PREFIX):
                v = v[len(BASE_PREFIX) + 1:]

            else:
                v = getattr(v, "origin", None)

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


def get_modules(args):
    mods = "_asyncio,_bz2,_curses,_dbm,_gdbm,_tkinter,_sqlite3,_ssl,_uuid,readline,zlib"
    if len(args) > 1 and args[1]:
        if args[1] == "all":
            mods += ",_functools,_tracemalloc"

        elif args[1][0] == "+":
            mods += ",%s" % args[1][1:]

        else:
            mods = args[1]

    return [x for x in mods.split(",") if x]


report = get_report(get_modules(sys.argv))
print(json.dumps(report, indent=2, sort_keys=True))
