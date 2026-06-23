---
type: Playbook
title: Add an External Module
description: Add a new statically-linked C library to CPython by creating a ModuleBuilder subclass and wiring it into the candidate list.
tags: [playbook, modules, contributing]
timestamp: 2026-06-23T00:00:00Z
---

# Add an External Module

To statically link a new C library into CPython, add a [`ModuleBuilder`](/architecture/module-builder.md) subclass. The existing [external modules](/modules/external-modules.md) are the best templates.

## Steps

1. **Create the class** in `src/portable_python/external/xcpython.py`:

   ```python
   class Mylib(ModuleBuilder):
       """See https://docs.python.org/3/library/mymodule.html"""

       m_telltale = "{include}/mylib.h"     # marker if system already has it
       m_debian = "+libmylib-dev"           # Linux build constraint (see telltale detection)

       @property
       def url(self):
           return self.cfg_url(self.version) or f"https://example.org/mylib-{self.version}.tar.gz"

       @property
       def version(self):
           return self.cfg_version("1.2.3")  # default, overridable via mylib-version config

       def c_configure_args(self):
           if args := self.cfg_configure(self.deps_lib_dir, self.deps_lib64_dir):
               yield args
           else:
               yield "--enable-shared=no"
               yield "--enable-static=yes"

       def _do_linux_compile(self):
           self.run_configure("./configure", self.c_configure_args())
           self.run_make()
           self.run_make("install")
   ```

2. **Set the declarative attributes**: `m_telltale` (see [telltale detection](/concepts/telltale-detection.md)), `m_debian` with the right sigil, and `m_include`/`m_build_cwd` if needed.

3. **Implement source resolution**: `url` and `version` (using `cfg_url`/`cfg_version` so config overrides work).

4. **Implement the compile**: `_do_linux_compile()`. macOS reuses it unless you add `_do_macos_compile()`.

5. **Register it** in `Cpython.candidate_modules()` (in `cpython.py`) so it becomes a candidate.

6. **Add tests** in `tests/test_setup.py` (the suite runs in `--dryrun`, so it asserts the planned commands without compiling).

## Tips

- Prefer config flags over source patches — see the [no-patches principle](/overview.md).
- Use `--dryrun` to confirm the configure/make commands look right before a real build.
- If the library is only needed when explicitly selected, leave `auto_select_reason()` unset; if a build cannot succeed without it, return a short reason there.

# Citations

[1] [DEVELOP.md — Add a New External Module](https://github.com/codrsquad/portable-python/blob/main/DEVELOP.md)
[2] [src/portable_python/external/xcpython.py — existing modules](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/external/xcpython.py)
