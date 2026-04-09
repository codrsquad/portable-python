# Local development

Create a dev venv:

```shell
uv sync
```

You can then run `portable-python` from that venv:

```shell
.venv/bin/portable-python list
.venv/bin/portable-python build-report 3.10.5
```


# Run the tests

If you have tox, just run: `tox` to run all the tests. You can also run:
- `tox -e py313` to run with just one python version
- `tox -e style` to check PEP8 formatting
- etc

If you don't have tox, you can run the tests with: `.venv/bin/pytest tests/`

You can also run any of the `tests/` in IDEs such as PyCharm or VSCode.

For example in PyCharm, just make sure that `pytest` is selected as "Default test runner"
in Preferences -> Tools -> Python Integrated Tools.
Then right-click on any file in `tests/`
(or in any function `test_...` function within a `test_*` file)
and select "Debug pytest in ..."

You can set breakpoints as well during such test runs.


# Running in the debugger

You can easily run `portable-python` in a debugger.
In PyCharm for example, you would simply browse to `.venv/bin/portable-python`
then right-click and select "Debug portable-python".
You can then edit the build/run configuration in PyCharm, add some "Parameters" to it,
like for example `build-report 3.13.2`, and then set breakpoints wherever you like.

There is a `--dryrun` mode that can come in very handy for rapid iterations.


# Building a linux binary via docker

Build a docker image, for example using the provided sample `Dockerfile`:

```shell
docker build -t portable-python-jammy .
```

Run the docker image, with a folder `/src/` mounted to point to:

```shell
docker run -it -v./:/src/ portable-python-jammy /bin/bash
```

Now inside docker, you run a build:

```shell
portable-python build 3.13.2
```


# Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| click | <9 | CLI framework |
| pyyaml | <7 | Configuration parsing |
| requests | <3 | HTTP downloads |
| runez | <6 | Utilities (file ops, system, logging) |
| urllib3 | <3 | HTTP transport |
| pytest-cov | - | Coverage reporting (dev only) |

**runez** is central: provides file ops (`ls_dir`, `touch`, `compress`/`decompress`), system info (platform detection), CLI decorators (`@click.group`), logging, and version handling (`Version`, `PythonSpec`).


# Common Tasks

## Add a New External Module

1. Create class in `src/portable_python/external/xcpython.py` extending `ModuleBuilder`
2. Set `m_name`, `m_telltale`, `m_debian`, `version` property
3. Implement `url` property (or override `_do_linux_compile()` / `_do_macos_compile()`)
4. Add to `Cpython.candidate_modules()` if it's a CPython sub-module
5. Add tests in `tests/test_setup.py`

## Add a New Config Option

1. Update `DEFAULT_CONFIG` in `src/portable_python/config.py`
2. Use `PPG.config.get_value("key")` to retrieve it in code
3. Add tests to `tests/test_setup.py`

## Fix a Portability Issue

1. Run `portable-python inspect <PATH>` to diagnose
2. If lib is being dynamically linked, add to module list or update isolation
3. Use `LibAutoCorrect.run()` logic (or extend it) to fix paths
4. Add test case to `tests/test_inspector.py`

## Bump Python Support

1. Update `pyproject.toml` classifiers and `requires-python`
2. Update `.github/workflows/tests.yml` matrix
3. Update `CPythonFamily.min_version` if needed
4. Run full test matrix with `tox`
