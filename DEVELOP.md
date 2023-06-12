# How to create a dev venv

If you have tox, you can run: `tox -re venv`, that will get you a `.venv/`
ready to go.

If you don't have tox, you can run this (any python 3.6+ will do):

```shell
rm -rf .venv
/usr/bin/python3 -mvenv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt -r tests/requirements.txt
.venv/bin/pip install -e .
```

You can then run `portable-python` from that venv:

```shell
.venv/bin/portable-python list
.venv/bin/portable-python build-report 3.10.5
```


# Run the tests

If you have tox, just run: `tox` to run all the tests. You can also run:
- `tox -e py39` to run with just one python version
- `tox -e style` to check PEP8 formatting
- `tox -r` if you changed any `requirements.txt` (`-r` is short for `--recreate`)
- `tox -re py39` to recreate and run `py39` only
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
like for example `build-report 3.10.5`, and then set breakpoints wherever you like.

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
portable-python build 3.11.4
```
