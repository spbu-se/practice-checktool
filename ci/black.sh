#!/bin/sh

set -e

.venv/bin/black -t py313 --diff --check *.py
