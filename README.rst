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


``Portable-Python`` is a CLI (and a python library) for compiling python binaries
from source than can be decompressed in any folder, and used from there without
further ado (ie: no need to run an "installer").


Motivation
----------

The idea here is to allow for automated systems to:

- Easily obtain a python binary, that can be used in sandboxes / workstations / laptops / instances...

- Inspect any python installation, and point out how portable it is, which
  shared or non-standard libraries it is using


Installation
------------

``portable-python`` is a regular python CLI, it can be installed with:

pickley_::

    pickley install portable-python
    portable-python --help
    portable-python inspect /usr/bin/python3

Or pipx_::

    pipx install portable-python
    portable-python inspect /usr/bin/python3

Using ``pip install`` (a CI builder would probably do this)::

    /usr/bin/python3 -mvenv /tmp/pp
    /tmp/pp/bin/python -mpip install portable-python
    /tmp/pp/bin/portable-python --help
    /tmp/pp/bin/portable-python inspect /usr/bin/python3


Supported operating systems
---------------------------

Portable python binaries can be built for Linux and MacOS (Intel/M1/M2).

Currently **Windows is NOT supported**, contributions are welcome.

Python binaries can be produced as "portable" (statically linked, can run from any folder
where the binary is unpacked in), or with a ``--prefix`` (build targeted to live in a
pre-determined folder, like ``/apps/pythonM.m``)

================  ========  ========
Operating system  Portable  --prefix
================  ========  ========
Linux                ✅        ✅
Macos                ✅        ✅
Windows              ❌        ❌
================  ========  ========


Building a portable cpython
===========================

Once ``portable-python`` is installed:

Build a binary::

    cd some-temp-folder
    portable-python build 3.9.7
    ls -l dist/cpython-3.9.7-macos-arm64.tar.gz

Unpack it somewhere::

    tar -C ~/tmp/versions/ -xf dist/cpython-3.9.7-macos-arm64.tar.gz
    ls -l ~/tmp/versions/

It's ready to be used::

    ~/tmp/versions/3.9.7/bin/python --version


Note that you can use ``--dryrun`` mode to inspect what would be done without doing it::

    $ portable-python --dryrun build 3.9.7

    INFO selected: xz openssl gdbm (3 modules) xz:5.2.5 openssl:1.1.1k gdbm:1.18.1
    INFO Platform: macos-x86_64
    ...
    --------------
    -- xz:5.2.5 --
    --------------
    Would download https://tukaani.org/xz/xz-5.2.5.tar.gz
    Would untar build/sources/xz-5.2.5.tar.gz -> build/components/xz
    INFO env PATH=build/deps/bin:/usr/bin:/bin
    INFO env MACOSX_DEPLOYMENT_TARGET=10.14
    Would run: ./configure --prefix=build/deps --enable-shared=no --enable-static=yes ...
    ...
    -------------------
    -- cpython:3.9.7 --
    -------------------
    Would download https://www.python.org/ftp/python/3.9.7/Python-3.9.7.tar.xz
    Would untar build/sources/Python-3.9.7.tar.xz -> build/components/cpython
    ...
    Would run: ./configure --prefix=/ppp-marker/3.9.7 --enable-optimizations ...
    Would run: /usr/bin/make
    Would run: /usr/bin/make install DESTDIR=build
    ...
    Would tar build/3.9.7 -> dist/cpython-3.9.7-macos-x86_64.tar.gz


Library
-------

Portable Python can be used as a python library to invoke builds, or inspect an installation.

Invoke a build from python code::

    from portable_python import BuildSetup

    setup = BuildSetup("cpython:3.9.7")
    setup.compile()


Invoke an inspection from python code::

    from portable_python.inspector import PythonInspector

    inspector = PythonInspector("/usr/bin/python3")
    print(inspector.represented())
    problem = inspector.full_so_report.get_problem(portable=True)
    if problem:
        print("oops, it is not portable!: %s" % problem)


From source, contributions welcome!::

    git clone https://github.com/codrsquad/portable-python.git
    cd portable-python
    python3 -mvenv .venv
    .venv/bin/pip install -r requirements.txt -r tests/requirements.txt
    .venv/bin/pip install -e .
    .venv/bin/portable-python --help
    .venv/bin/portable-python inspect /usr/bin/python3

    tox -e py311
    tox -e style


Build folder structure
----------------------

``portable-python`` uses this file structure (build/ and dist/ folders configurable)::

    build/
        ppp-marker/3.9.7/                   # Full installation (after build completes)
        components/                         # Builds of statically compiled extension modules are here
        deps/                               # --prefix=.../deps passed to all component ./configure scripts
        sources/
            openssl-1.1.1k.tar.gz           # Downloaded artifacts (downloaded only once)
    dist/
        cpython-3.9.7-macos-arm64.tar.gz    # Ready-to-go portable binary tarball


Guiding principles
------------------

- Focuses on just one thing: compile a portable python, and validate that it is indeed portable,
  produce outcome in (configurable) ``./dist/`` folder and that's it

- No patches: C compilation is done as simply as possible without modifying the upstream source code.
  Rely solely on the make/configure scripts, typically via stuff like ``--enable-shared=no``

- Builds are validated, an important part of the effort was to write up code that is able to
  ``inspect`` a python installation and detect whether it is portable or not (and why not if so).

- Only the last few non-EOL versions of python are supported (no historical stuff)

- As time goes on, the code of this tool will evolve so that the latest pythons keep building
  (but won't worry that older versions still keep building)


For this repo itself:

- Code is pure python, it is a CLI with one entry-point called ``portable-python``

  - Can be ran in a debugger

  - 100% test coverage, has a ``--dryrun`` mode to help with testing / debugging / seeing what would be done quickly

  - No shell scripts (those are hard to maintain/test/debug)

  - Can be ``pip install``-ed and reused


.. _pickley: https://pypi.org/project/pickley/

.. _pipx: https://pypi.org/project/pipx/
