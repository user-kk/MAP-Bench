#!/bin/bash

set -euo pipefail


python bench_duckdb.py *.sql -x G1.sql G3.sql -o "out/$(date +%F_%T).csv"