#!/usr/bin/env python3
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Patch
from pathlib import Path

# 颜色配置 - 与条形图对应
SYSTEMS = [
    ('helmdb',        'GredoDB',          '#3A76AF'),
    ('arangodb',      'ArangoDB',         '#2D8E4E'),
    ('agensgraph-sp', 'AgensGraph (SP)',  '#F4A742'),
    ('agensgraph-mp', 'AgensGraph (MP)',  '#D2691E'),
    ('duckdb-st',     'DuckDB (ST)',      '#B388C9'),
    ('duckdb-mt',     'DuckDB (MT)',      '#7B2D8E'),
    ('polystore',     'Polyglot',         '#888888'),
]

# 线型配置 - 区分SP/MP和ST/MT
LINE_STYLES = {
    'helmdb':        '-',
    'arangodb':      '-',
    'agensgraph-sp': '--',
    'agensgraph-mp': '-',
    'duckdb-st':     '--',
    'duckdb-mt':     '-',
    'polystore':     '-',
}

MARKERS = {
    'helmdb':        'o',
    'arangodb':      's',
    'agensgraph-sp': '^',
    'agensgraph-mp': '^',
    'duckdb-st':     'D',
    'duckdb-mt':     'D',
    'polystore':     'v',
}

# 默认绘制的查询 - 每类两个代表性查询
DEFAULT_QUERIES = {
    'H': ['H1', 'H3'],
    'A': ['A1', 'A5'],
    'V': ['V3', 'V4'],
    'G': ['G3', 'G4'],
}

SCALE_ORDER = ['MAP-S', 'MAP-M', 'MAP-L']
SCALE_LABELS = ['MAP-S', 'MAP-M', 'MAP-L']


def parse_args():
    parser = argparse.ArgumentParser(description='MAP-Bench Scalability Plot')
    parser.add_argument('-i', '--input', type=Path, required=True,
                        help='Input CSV file')
    parser.add_argument('-o', '--output', type=Path, default=Path('scalability.pdf'),
                        help='Output figure path')
    parser.add_argument('--dpi', type=int, default=300)
    parser.add_argument('--queries', type=str, nargs='+',
                        help='Queries to plot (default: H1 H3 A1 A4 V3 V4 G1 G4)')
    args = parser.parse_args()
    return args


def load_data(csv_path):
    """Load and pivot the CSV data"""
    df = pd.read_csv(csv_path)
    
    # Convert to numeric, handling missing values
    for col in [s[0] for s in SYSTEMS]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df


def plot_scalability(df, queries, output_path, dpi):
    """
    Create 2x4 subplot layout for scalability curves
    
    Args:
        df: DataFrame with columns [scale, query, system1, system2, ...]
        queries: List of query names to plot
        output_path: Output file path
        dpi: Figure DPI
    """
    
    # Determine layout
    if queries is None:
        queries = []
        for pattern in ['H', 'A', 'V', 'G']:
            queries.extend(DEFAULT_QUERIES[pattern])
    
    n_queries = len(queries)
    assert n_queries == 8, "Must specify exactly 8 queries for 2x4 layout"
    
    # Setup figure
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 19,
        'axes.titlesize': 21,
        'axes.labelsize': 18,
        'xtick.labelsize': 17,
        'ytick.labelsize': 17,
        'legend.fontsize': 17,
        'axes.linewidth': 1.0,
    })
    
    fig = plt.figure(figsize=(10, 6), facecolor='white')
    
    # Create 2x4 grid
    gs = gridspec.GridSpec(2, 4, figure=fig,
                          left=0.06, right=0.99,
                          top=0.90, bottom=0.12,
                          wspace=0.25, hspace=0.3)
    
    # Plot each query
    for idx, qname in enumerate(queries):
        row = idx // 4
        col = idx % 4
        ax = fig.add_subplot(gs[row, col])
        
        # Filter data for this query
        qdata = df[df['query'] == qname].copy()
        
        if qdata.empty:
            ax.text(0.5, 0.5, f'{qname}\nNo Data', 
                   ha='center', va='center', fontsize=12, color='gray')
            ax.set_xticks([])
            ax.set_yticks([])
            continue
        
        # Ensure scale order
        qdata['scale_cat'] = pd.Categorical(qdata['scale'], 
                                            categories=SCALE_ORDER, 
                                            ordered=True)
        qdata = qdata.sort_values('scale_cat')
        
        x_positions = np.arange(len(SCALE_ORDER))
        
        # Plot each system
        for sys_col, sys_label, sys_color in SYSTEMS:
            if sys_col not in qdata.columns:
                continue
                
            y_values = []
            x_valid = []
            
            for i, scale in enumerate(SCALE_ORDER):
                scale_data = qdata[qdata['scale'] == scale]
                if not scale_data.empty:
                    val = scale_data[sys_col].values[0]
                    if not np.isnan(val):
                        y_values.append(val)
                        x_valid.append(i)
            
            if y_values:
                ax.plot(x_valid, y_values, 
                       color=sys_color,
                       linestyle=LINE_STYLES[sys_col],
                       marker=MARKERS[sys_col],
                       markersize=6,
                       linewidth=2.0,
                       label=sys_label,
                       alpha=0.9)
        
        # Configure axes
        ax.set_yscale('log')
        ax.set_xticks(x_positions)
        ax.set_xticklabels(SCALE_LABELS, fontsize=15)
        ax.set_xlim(-0.3, len(SCALE_ORDER) - 0.7)
        
        # Set title
        ax.set_title(qname, fontsize=19, pad=5)
        
        # Y-axis label only for leftmost column
        if col == 0:
            ax.set_ylabel('Latency (ms)', fontsize=17)
        
        # Grid
        ax.grid(axis='y', which='major', alpha=0.3, linestyle='-', linewidth=0.5)
        ax.grid(axis='y', which='minor', alpha=0.15, linestyle=':', linewidth=0.3)
        
        # Spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    
    # Create legend
    handles = []
    labels = []
    for sys_col, sys_label, sys_color in SYSTEMS:
        handles.append(plt.Line2D([0], [0], 
                                 color=sys_color, 
                                 linestyle=LINE_STYLES[sys_col],
                                 marker=MARKERS[sys_col],
                                 markersize=6,
                                 linewidth=2.0))
        labels.append(sys_label)
    
    fig.legend(handles, labels,
              loc='lower center',
              ncol=4,
              fontsize=16,
              frameon=True,
              edgecolor='#cccccc',
              fancybox=True,
              bbox_to_anchor=(0.5, -0.08),
              handlelength=2.0,
              handletextpad=0.5,
              columnspacing=1.5)
    
    # Save figure
    fig.savefig(str(output_path), 
               dpi=dpi, 
               bbox_inches='tight',
               facecolor='white',
               edgecolor='none')
    
    print(f'✓ Saved: {output_path}')
    plt.close(fig)


def main():
    args = parse_args()
    
    # Load data
    df = load_data(args.input)
    
    # Plot
    plot_scalability(df, args.queries, args.output, args.dpi)


if __name__ == '__main__':
    main()