#!/bin/bash

set -euo pipefail


python bench_duckdb.py *.sql -x q1.sql q12.sql -o q.csv