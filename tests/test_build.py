from unittest.mock import patch

import runez

from .conftest import dummy_tarball


def test_finalization(cli, monkeypatch):
    v = "3.9.7"
    dummy_tarball(f"Python-{v}.tar.xz")
    dummy_tarball("bzip2-1.0.8.tar.gz")
    base = runez.to_path(f"build/cpython-{v}")
    bin = base / f"{v}/bin"

    runez.touch(base / "build/cpython/README", logger=None)

    # Create some files to be groomed by CPython
    runez.touch(bin.parent / "lib/idle_test/foo", logger=None)
    runez.touch(bin.parent / "lib/__phello__.foo.py", logger=None)
    runez.touch(bin / "foo-python", logger=None)
    runez.symlink(bin / "foo-python", bin / "python3", logger=None)  # Simulate a funky symlink, to test edge cases
    runez.write(bin / "some-exe", "#!.../bin/python3\nhello", logger=None)
    runez.write(bin / "some-exe3", "#!/bin/sh\nhello", logger=None)
    runez.write(bin / "pythond", b"\xe4", logger=None)  # Non-unicode char to trigger edge case
    monkeypatch.setenv("PP_X_DEBUG", "direct-finalize")
    with patch("runez.run", return_value=runez.program.RunResult(code=0)):
        cli.run("build", v, "-mbzip2")
        assert cli.failed
        assert "selected: bzip2 (1 module)" in cli.logged
        assert "INFO Cleaned 2 build artifacts: __phello__.foo.py idle_test" in cli.logged
        assert f"Symlink build/cpython-{v}/{v}/bin/foo-python <- build/cpython-{v}/{v}/bin/python" in cli.logged
        assert f"Auto-corrected shebang for build/cpython-{v}/{v}/bin/some-exe" in cli.logged
        assert "Build failed" in cli.logged

    assert list(runez.readlines(bin / "some-exe")) == ["#!/bin/sh", '"exec" "$(dirname $0)/foo-python" "$0" "$@"', "hello"]
    assert list(runez.readlines(bin / "some-exe3")) == ["#!/bin/sh", "hello"]
    assert runez.basename(bin / "python", follow=True) == "foo-python"
