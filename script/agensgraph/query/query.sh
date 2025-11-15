#!/bin/bash

set -euo pipefail


python bench_agensgraph.py *.sql -o "out/$(date +%F_%T).csv" -x G1.sql