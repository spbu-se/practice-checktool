#!/bin/sh

set -e

.venv/bin/mypy --strict *.py
