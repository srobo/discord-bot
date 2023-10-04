#!/bin/bash

set -euo pipefail

cd $(dirname $0)/..

echo "Compiling main requirements"
pip-compile --quiet "$@"

echo "Compiling development requirements"
pip-compile --quiet script/requirements.in "$@"
