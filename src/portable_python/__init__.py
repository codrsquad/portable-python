import json
import logging
import os
import re

import runez
from runez.pyenv import PythonDepot
from runez.render import PrettyTable


LOG = logging.getLogger(__name__)


class PythonInspector:

    def __init__(self, specs, modules=None):
        self.inspector_path = os.path.join(os.path.dirname(__file__), "_inspect.py")
        self.specs = runez.flattened(specs, keep_empty=None, split=",")
        self.modules = modules
        self.depot = PythonDepot(use_path=False)
        self.reports = [self._spec_report(p) for p in self.specs]

    def report(self):
        return runez.joined(self.report_rows(), delimiter="\n")

    def report_rows(self):
        for r in self.reports:
            if r.report:
                if r.python.problem:
                    yield runez.short("%s: %s" % (runez.blue(r.spec), runez.red(r.python.problem)))

                else:
                    yield "%s:" % runez.blue(r.python)
                    yield r.represented() or ""

    def _spec_report(self, spec):
        python = self.depot.find_python(spec)
        report = dict(problem=python.problem) if python.problem else self._python_report(python.executable)
        return InspectionReport(spec, python, report)

    def _python_report(self, exe):
        r = runez.run(exe, self.inspector_path, self.modules, fatal=False, logger=print if runez.DRYRUN else LOG.debug)
        if not runez.DRYRUN:
            if r.succeeded and r.output and r.output.startswith("{"):
                return json.loads(r.output)

            return dict(exit_code=r.exit_code, error=r.error, output=r.output)


class InspectionReport:

    def __init__(self, spec, python, report):
        self.spec = spec
        self.python = python
        self.report = report

    def __repr__(self):
        return str(self.python)

    @staticmethod
    def lib_version_via_otool(path):
        aliases = {"tkinter": "tcl"}
        if path and os.path.exists(path):
            r = runez.run("otool", "-L", path, fatal=False, logger=None)
            if r.succeeded:
                m = re.match(r"^_?([^.]+).*$", os.path.basename(path))
                if m:
                    name = m.group(1).lower()
                    name = aliases.get(name, name)
                    for line in r.output.splitlines():
                        m = re.match(r"^\s*(\S+).+current version ([0-9.]+).*$", line)
                        if m:
                            lb = m.group(1).lower()
                            if name in lb:
                                return m.group(2)

    @staticmethod
    def lib_version(path):
        v = InspectionReport.lib_version_via_otool(path)
        return v

    @staticmethod
    def color(text):
        if text.startswith("*"):
            return runez.orange(text)

        if text == "built-in":
            return runez.blue(text)

        m = re.match(r"^(.*?)\s*(\S+/(lib(64)?/.*))$", text)
        if m:
            before = m.group(1)
            version = InspectionReport.lib_version(m.group(2))
            text = runez.green(m.group(3))
            if version:
                text = "%s %s" % (text, runez.blue(version))

            if before:
                text = "%s %s" % (before, text)

        else:
            text = runez.short(text)

        return text

    def represented(self):
        if self.report:
            t = PrettyTable(2)
            t.header[0].align = "right"
            for k, v in sorted(self.report.items()):
                t.add_row(k, self.color(v or "*empty*"))

            return "%s\n" % t
