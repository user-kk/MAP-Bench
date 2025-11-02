#!/bin/bash

set -euo pipefail


python bench_helmdb.py q*.sql s*.sql -o "out/$(date +%F_%T).csv"  -x q2.sql q9.sql q10.sql q11.sql 