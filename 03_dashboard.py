"""
03_dashboard.py
---------------
Generates all charts and saves a multi-panel dashboard PNG to outputs/.

Charts produced:
  1. Potato production by country (2015-2023)
  2. Yield comparison across countries
  3. Input cost trend — fertiliser & energy (2015-2023)
  4. 2022 energy crisis cost spike
  5. Producer price index volatility
  6. Regenerative agriculture savings potential
"""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd
import numpy as np

try:
    BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
except NameError:
    BASE = '.'

PROCESSED = os.path.join(BASE, 'data', 'processed')
OUTPUTS   = os.path.join(BASE, 'outputs')
os.makedirs(OUTPUTS, exist_ok=True)

# ── Colour palette ──────────────────────────────────────────────
PALETTE = {
    'France':      '#2196F3',
    'Germany':     '#FF9800',
    'Netherlands': '#4CAF50',
    'Poland':      '#E91E63',
}
BG       = '#0F1117'
PANEL_BG = '#1A1D27'
TEXT     = '#E8EAF0'
GRID     = '#2A2D3A'
ACCENT   = '#FFD700'

plt.rcParams.update({
    'figure.facecolor':  BG,
    'axes.facecolor':    PANEL_BG,
    'axes.edgecolor':    GRID,
    'axes.labelcolor':   TEXT,
    'axes.titlecolor':   TEXT,
    'xtick.color':       TEXT,
    'ytick.color':       TEXT,
    'text.color':        TEXT,
    'grid.color':        GRID,
    'grid.linewidth':    0.5,
    'legend.facecolor':  PANEL_BG,
    'legend.edgecolor':  GRID,
    'font.family':       'DejaVu Sans',
    'font.size':         9,
})


def load_data():
    costs    = pd.read_csv(os.path.join(PROCESSED, 'costs_merged.csv'))
    prices   = pd.read_csv(os.path.join(PROCESSED, 'price_analysis.csv'))
    summary  = pd.read_csv(os.path.join(PROCESSED, 'analysis_country_summary.csv'))
    spike    = pd.read_csv(os.path.join(PROCESSED, 'analysis_cost_spike.csv'))
    regen    = pd.read_csv(os.path.join(PROCESSED, 'analysis_regen_potential.csv'))
    return costs, prices, summary, spike, regen


def plot_production(ax, costs):
    ax.set_title('Potato Production 2015–2023  (1 000 t)', fontsize=10, fontweight='bold', pad=8)
    for country, grp in costs.groupby('country'):
        ax.plot(grp['year'], grp['production_kt'],
                color=PALETTE[country], linewidth=2, marker='o', markersize=4, label=country)
    ax.set_ylabel('Production (1 000 t)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.4)
    ax.set_xlim(2015, 2023)


def plot_yield(ax, costs):
    ax.set_title('Average Yield by Country  (t/ha)', fontsize=10, fontweight='bold', pad=8)
    countries = costs['country'].unique()
    avg_yield = costs.groupby('country')['yield_t_ha'].mean().reindex(countries)
    bars = ax.bar(countries, avg_yield,
                  color=[PALETTE[c] for c in countries], alpha=0.85, zorder=3)
    for bar, val in zip(bars, avg_yield):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f'{val:.1f}', ha='center', va='bottom', fontsize=8, color=TEXT)
    ax.set_ylabel('Yield (t/ha)')
    ax.grid(True, axis='y', alpha=0.4)
    ax.set_ylim(0, max(avg_yield) * 1.2)


def plot_input_costs(ax, costs):
    ax.set_title('Estimated Input Cost Trend  (€/ha)', fontsize=10, fontweight='bold', pad=8)
    annual = costs.groupby('year').agg(
        fert  =('est_fert_cost_eur_ha',   'mean'),
        energy=('est_energy_cost_eur_ha',  'mean'),
    ).reset_index()
    ax.stackplot(annual['year'],
                 annual['fert'], annual['energy'],
                 labels=['Fertiliser', 'Energy'],
                 colors=['#2196F3', '#FF9800'], alpha=0.8)
    ax.axvline(2022, color=ACCENT, linestyle='--', linewidth=1.5, alpha=0.8, label='2022 crisis')
    ax.set_ylabel('Cost (€/ha)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.4)
    ax.set_xlim(2015, 2023)


def plot_cost_spike(ax, spike):
    ax.set_title('Input Cost Increase: 2019 → 2022  (%)', fontsize=10, fontweight='bold', pad=8)
    spike = spike.sort_values('increase_pct', ascending=True)
    bars  = ax.barh(spike['country'], spike['increase_pct'],
                    color=[PALETTE[c] for c in spike['country']], alpha=0.85)
    for bar, val in zip(bars, spike['increase_pct']):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f'+{val:.0f}%', va='center', fontsize=9, color=ACCENT, fontweight='bold')
    ax.set_xlabel('Increase (%)')
    ax.grid(True, axis='x', alpha=0.4)
    ax.set_xlim(0, spike['increase_pct'].max() * 1.25)


def plot_price_index(ax, prices):
    ax.set_title('Producer Price Index  (2015 = 100)', fontsize=10, fontweight='bold', pad=8)
    for country, grp in prices.groupby('country'):
        ax.plot(grp['year'], grp['price_index_2015_100'],
                color=PALETTE[country], linewidth=2, label=country)
    ax.axhline(100, color=GRID, linestyle='--', linewidth=1)
    ax.set_ylabel('Index (2015=100)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.4)
    ax.set_xlim(2015, 2023)


def plot_regen(ax, regen):
    ax.set_title('Regen Practice Savings Potential  (€/ha)', fontsize=10, fontweight='bold', pad=8)
    regen = regen.sort_values('total_potential_saving_eur_ha', ascending=True)
    bars  = ax.barh(regen['country'], regen['total_potential_saving_eur_ha'],
                    color=[PALETTE[c] for c in regen['country']], alpha=0.85)
    for bar, val in zip(bars, regen['total_potential_saving_eur_ha']):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f'€{val:.0f}', va='center', fontsize=9, color='#4CAF50', fontweight='bold')
    ax.set_xlabel('Saving (€/ha)')
    ax.grid(True, axis='x', alpha=0.4)


def main():
    print("=" * 55)
    print("Generating dashboard")
    print("=" * 55)

    costs, prices, summary, spike, regen = load_data()

    fig = plt.figure(figsize=(18, 11), facecolor=BG)
    fig.suptitle(
        'EU Potato Supply Chain Analytics  ·  FR · NL · PL · DE  ·  2015–2023',
        fontsize=14, fontweight='bold', color=ACCENT, y=0.98
    )

    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35,
                           left=0.06, right=0.97, top=0.93, bottom=0.07)

    plot_production( fig.add_subplot(gs[0, 0]), costs)
    plot_yield(      fig.add_subplot(gs[0, 1]), costs)
    plot_input_costs(fig.add_subplot(gs[0, 2]), costs)
    plot_cost_spike( fig.add_subplot(gs[1, 0]), spike)
    plot_price_index(fig.add_subplot(gs[1, 1]), prices)
    plot_regen(      fig.add_subplot(gs[1, 2]), regen)

    out_path = os.path.join(OUTPUTS, 'dashboard.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close()
    print(f"  -> Saved {out_path}")


if __name__ == '__main__':
    main()
