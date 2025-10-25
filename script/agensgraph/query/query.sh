#!/bin/bash

set -euo pipefail


python bench_agensgraph.py *.sql -o q2.csv -x q1.sql