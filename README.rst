Portable python binaries
========================

.. image:: https://img.shields.io/pypi/v/portable-python.svg
    :target: https://pypi.org/project/portable-python/
    :alt: Version on pypi

.. image:: https://github.com/codrsquad/portable-python/workflows/Tests/badge.svg
    :target: https://github.com/codrsquad/portable-python/actions
    :alt: Tested with Github Actions

.. image:: https://codecov.io/gh/codrsquad/portable-python/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/codrsquad/portable-python
    :alt: Test coverage

.. image:: https://img.shields.io/pypi/pyversions/portable-python.svg
    :target: https://github.com/codrsquad/portable-python
    :alt: Python versions tested (link to github project)


This project is a python CLI that aims to make compiling portable python binaries automatable.


What is a "portable python"?
----------------------------

It's a binary python distribution (``.tar.gz`` or ``.zip``) that can be decompressed
in any folder, and used from there without further ado (ie: no need to run an "installer"
and things like that).

The idea here is to allow for automated systems to:

- Easily obtain a python binary, and use it in their sandbox.

- Install versions of python from binary distributions on laptops/workstations,
  similarly to how pyenv_ does it, but without having to compile on target system.


Guiding principles
------------------

- Only the last few non-EOL versions of python are supported (no historical stuff)

- Code is 100% properly packaged python

  - Can be ran in a debugger, 100% test coverage

  - ``--dryrun`` mode to help with testing / debugging / seeing what would be done quickly

  - No shell scripts (those are hard to maintain/test/debug)

- ``portable-python`` is designed to be used as a tool to produce binary pythons
  that can easily be deployed, and then published somewhere (internally at a company),
  not designed to be used directly on laptops/workstations

- C compilation is done as simply as possible: no "patching" of any sort,
  (rely completely on the upstream make/configure scripts as-is)

- Cpython is initially supported, but aiming to compile any flavor in the future
  (pypi, conda, ...)

- Cross-compilation would be cool, but only if upstream supports it


How it works
------------

``portable-python`` is a regular python CLI, it can be installed with:

- pickley_::

    pickley install portable-python
    portable-python --help

- Using ``pip install``::

    /usr/bin/python3 -mvenv pp
    ./pp/bin/python -mpip install portable-python
    ./pp/bin/portable-python --help

- From python::

    # pip install portable-python

    from portable_python import BuildSetup

    setup = BuildSetup("cpython:3.9.6")
    setup.compile()


- From source::

    git clone https://github.com/codrsquad/portable-python.git
    cd portable-python
    tox -e venv
    .venv/bin/portable-python --help


Once you've installed ``portable-python``, you can get going like so::

    # Build a binary (for current platform)
    cd some-temp-folder
    portable-python build 3.9.6
    ls -l dist/cpython-*.tar.gz

    # Unpack it somewhere
    tar -C ~/.pyenv/versions/ -xf dist/cpython-3.9.6-darwin-x86_64.tar.gz
    ls -l ~/.pyenv/versions/

    # It's ready to be used
    ~/.pyenv/versions/3.9.6/bin/python --version


Note that you can use ``--dryrun`` mode to inspect what would be done without doing it::

    $ portable-python --dryrun build 3.9.6

    Would create build/cpython-3.9.2
    ...
    Would untar build/downloads/readline-8.1.tar.gz -> build/cpython-3.9.2/build/readline
    ...
    Would run: ./configure --prefix=/deps
    Would run: /usr/bin/make
    Would run: /usr/bin/make install DESTDIR=build/cpython-3.9.2
    ...


Build folder structure
----------------------

``portable-python`` uses this file structure (build/ and dist/ folders configurable)::

    build/
        cpython-3.9.6/      # Build artifacts for corresponding version are here
            3.9.6/          # Full installation (after build completes)
            build/          # Source code of various needed/selected modules are here
            deps/           # --prefix=.../deps passed to all ./configure scripts
            logs/           # Logs for each module build are here, in order of build
        downloads/
            openssl-1.1.1k.tar.gz           # Downloaded artifacts (downloaded only once)
    dist/
        cpython-3.9.6-darwin-x86_64.tar.gz  # Ready-to-go binary tarball



.. _pyenv: https://github.com/pyenv/pyenv

.. _pickley: https://pypi.org/project/pickley/
