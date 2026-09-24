#!/bin/sh

set -e

.venv/bin/black -t py312 --diff --check *.py
