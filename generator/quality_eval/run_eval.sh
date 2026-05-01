#!/bin/bash

set -e

echo "================================================================="
echo "Starting OpenAlex Data Generation Quality Evaluation Pipeline"
echo "================================================================="

SCRIPTS=(
    "relation_dist.py"
    "relation_ccdf.py"
    "doc_metrics.py"
    "doc_authorship.py"
    "graph_degree_ccdf.py"
    "vector_lid_kde.py"
    "cross_topic.py"
    "cross_citation.py"
    "publication_panels.py"
)

START_TIME=$(date +%s)

for script in "${SCRIPTS[@]}"; do
    echo ""
    echo "-----------------------------------------------------------------"
    echo "[$(date +'%H:%M:%S')] Running: $script"
    echo "-----------------------------------------------------------------"
    python "$script"
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "================================================================="
echo "All evaluations completed successfully in ${DURATION} seconds."
echo "Please check quality_eval_optimized/output for the single plots, panel figures, and summary tables."
echo "================================================================="
