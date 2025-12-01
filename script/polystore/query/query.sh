#!/bin/bash

set -euo pipefail

python bench_poly.py *.py -x A1.py A4.py bench_poly.py -o "out/$(date +%F_%T).csv"