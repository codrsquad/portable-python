#!/bin/bash

set -x
uv lock --upgrade
uv pip compile pyproject.toml --upgrade --universal -o requirements.txt --python-version 3.10 --group dev
