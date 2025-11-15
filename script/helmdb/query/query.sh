#!/bin/bash

set -euo pipefail


python bench_helmdb.py *.sql -o "out/$(date +%F_%T).csv"  -x  G4.sql G5.sql G6.sql 