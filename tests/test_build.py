from unittest.mock import patch

import runez

from portable_python.versions import Version

from .conftest import dummy_tarball


TV = Version("3.9.7")  # Test Version (version we're using in the tests here)


def test_finalization(cli, monkeypatch):
    cli.run("-n", "build", TV, "--clean", "foo")
    assert cli.failed
    assert "'foo' is not a valid value for --clean" in cli.logged

    dummy_tarball(f"Python-{TV}.tar.xz")
    dummy_tarball("bzip2-1.0.8.tar.gz")
    base = runez.to_path(f"build/cpython-{TV}")
    bin = base / f"{TV}/bin"

    runez.touch(base / "build/cpython/README", logger=None)

    # Create some files to be groomed by CPython
    runez.touch(bin.parent / "lib/idle_test/foo", logger=None)
    runez.touch(bin.parent / "lib/__phello__.foo.py", logger=None)
    runez.touch(bin / "2to3", logger=None)
    runez.touch(bin / "foo-python", logger=None)
    runez.symlink(bin / "foo-python", bin / "python3", logger=None)  # Simulate a funky symlink, to test edge cases
    runez.write(bin / "some-exe", "#!.../bin/python3\nhello", logger=None)
    runez.write(bin / "some-exe3", "#!/bin/sh\nhello", logger=None)
    runez.write(bin / "pythond", b"\xe4", logger=None)  # Non-unicode char to trigger edge case
    monkeypatch.setenv("PP_X_DEBUG", "direct-finalize")
    with patch("runez.run", return_value=runez.program.RunResult(code=0)):
        cli.run("build", TV, "-mbzip2", "--clean", "bin,libpython")
        assert cli.failed
        assert "selected: bzip2 (1 module)" in cli.logged
        assert "INFO Cleaned 2 build artifacts: __phello__.foo.py idle_test" in cli.logged
        assert f"Deleted build/cpython-{TV}/{TV}/bin/2to3" in cli.logged
        assert "Symlink foo-python <- python" in cli.logged
        assert f"Auto-corrected shebang for build/cpython-{TV}/{TV}/bin/some-exe" in cli.logged
        assert "Build failed" in cli.logged

    assert list(runez.readlines(bin / "some-exe")) == ["#!/bin/sh", '"exec" "$(dirname $0)/foo-python" "$0" "$@"', "hello"]
    assert list(runez.readlines(bin / "some-exe3")) == ["#!/bin/sh", "hello"]
    assert runez.basename(bin / "python", follow=True) == "foo-python"
