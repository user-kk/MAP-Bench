#!/bin/bash

set -euo pipefail


python bench_arangodb.py *.aql -o "out/$(date +%F_%T).csv"