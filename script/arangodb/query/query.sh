#!/bin/bash

set -euo pipefail


python bench_arangodb.py *.aql -o q.csv