#!/bin/sh

set -e

./ci/mypy.sh
./ci/black.sh
./ci/pylint.sh
