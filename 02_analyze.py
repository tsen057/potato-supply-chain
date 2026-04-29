"""
02_analyze.py
-------------
Reads processed data and produces analysis outputs:
  - Country cost comparison summary
  - Input cost trend (2015-2023)
  - Price volatility ranking
  - Regenerative agriculture potential estimates
  - Data source inventory scoring

Outputs saved to data/processed/analysis_*.csv
"""

import os
import pandas as pd
import numpy as np

try:
    BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
except NameError:
    BASE = '.'

PROCESSED = os.path.join(BASE, 'data', 'processed')
os.makedirs(PROCESSED, exist_ok=True)


def load_processed():
    prod   = pd.read_csv(os.path.join(PROCESSED, 'production_clean.csv'))
    costs  = pd.read_csv(os.path.join(PROCESSED, 'costs_merged.csv'))
    prices = pd.read_csv(os.path.join(PROCESSED, 'price_analysis.csv'))
    return prod, costs, prices


def country_summary(costs: pd.DataFrame) -> pd.DataFrame:
    """Average metrics per country across all available years."""
    print("\nCountry summary...")

    summary = costs.groupby('country').agg(
        avg_yield_t_ha          =('yield_t_ha',                    'mean'),
        avg_area_kha            =('area_kha',                      'mean'),
        avg_production_kt       =('production_kt',                 'mean'),
        avg_fert_cost_eur_ha    =('est_fert_cost_eur_ha',          'mean'),
        avg_energy_cost_eur_ha  =('est_energy_cost_eur_ha',        'mean'),
        avg_total_input_eur_ha  =('est_total_input_cost_eur_ha',   'mean'),
    ).round(1).reset_index()

    # Cost per tonne = total input cost / yield
    summary['est_input_cost_eur_t'] = (
        summary['avg_total_input_eur_ha'] / summary['avg_yield_t_ha']
    ).round(1)

    summary = summary.sort_values('est_input_cost_eur_t')
    print(summary[['country','avg_yield_t_ha','avg_total_input_eur_ha',
                    'est_input_cost_eur_t']].to_string(index=False))
    return summary


def cost_spike_analysis(costs: pd.DataFrame) -> pd.DataFrame:
    """Highlight the 2022 energy crisis cost spike vs 2019 baseline."""
    print("\nCost spike analysis (2022 vs 2019)...")

    base = costs[costs['year'] == 2019][
        ['country', 'est_total_input_cost_eur_ha']
    ].rename(columns={'est_total_input_cost_eur_ha': 'cost_2019'})

    spike = costs[costs['year'] == 2022][
        ['country', 'est_total_input_cost_eur_ha']
    ].rename(columns={'est_total_input_cost_eur_ha': 'cost_2022'})

    df = base.merge(spike, on='country')
    df['increase_eur_ha'] = (df['cost_2022'] - df['cost_2019']).round(1)
    df['increase_pct']    = ((df['increase_eur_ha'] / df['cost_2019']) * 100).round(1)
    df = df.sort_values('increase_pct', ascending=False)
    print(df.to_string(index=False))
    return df


def price_volatility(prices: pd.DataFrame) -> pd.DataFrame:
    """Rank countries by price index volatility (std dev)."""
    print("\nPrice volatility by country...")

    vol = prices.groupby('country').agg(
        mean_index  =('price_index_2015_100', 'mean'),
        std_index   =('price_index_2015_100', 'std'),
        min_index   =('price_index_2015_100', 'min'),
        max_index   =('price_index_2015_100', 'max'),
    ).round(1).reset_index()

    vol['cv_pct'] = (vol['std_index'] / vol['mean_index'] * 100).round(1)
    vol = vol.sort_values('cv_pct', ascending=False)
    print(vol.to_string(index=False))
    return vol


def regen_potential(costs: pd.DataFrame) -> pd.DataFrame:
    """
    Estimate potential savings from regenerative practices.
    Based on published literature benchmarks:
      - Cover cropping:        reduces N fertiliser need ~15%
      - Precision fertilisation: reduces total fertiliser use ~12%
      - Reduced tillage:       reduces energy/fuel costs ~20%
    """
    print("\nRegenerative agriculture potential...")

    latest = costs[costs['year'] >= 2021].groupby('country').agg(
        avg_fert_cost   =('est_fert_cost_eur_ha',   'mean'),
        avg_energy_cost =('est_energy_cost_eur_ha',  'mean'),
        avg_area_ha     =('area_ha',                 'mean'),
    ).reset_index()

    latest['cover_crop_saving_eur_ha']    = (latest['avg_fert_cost']   * 0.15).round(1)
    latest['precision_fert_saving_eur_ha']= (latest['avg_fert_cost']   * 0.12).round(1)
    latest['reduced_tillage_saving_eur_ha']=(latest['avg_energy_cost'] * 0.20).round(1)
    latest['total_potential_saving_eur_ha']= (
        latest['cover_crop_saving_eur_ha'] +
        latest['precision_fert_saving_eur_ha'] +
        latest['reduced_tillage_saving_eur_ha']
    ).round(1)

    latest['total_potential_saving_meur'] = (
        latest['total_potential_saving_eur_ha'] * latest['avg_area_ha'] / 1e6
    ).round(1)

    out = latest[['country', 'avg_fert_cost', 'avg_energy_cost',
                  'total_potential_saving_eur_ha', 'total_potential_saving_meur']]
    print(out.to_string(index=False))
    return latest


def data_source_inventory() -> pd.DataFrame:
    """
    Scored inventory of key EU agricultural data sources.
    Criteria: Coverage, Granularity, Access, Update Frequency, Relevance to McCain.
    Score 1-5 each, total /25.
    """
    sources = [
        {
            'source': 'Eurostat apro_cpsh1',
            'description': 'Crop production: area, yield, output',
            'coverage': 'EU27 countries, annual 1975+',
            'granularity': 'National',
            'access': 'Free API',
            'update_freq': 'Annual',
            'score_coverage': 5, 'score_granularity': 3, 'score_access': 5,
            'score_freshness': 3, 'score_relevance': 5,
        },
        {
            'source': 'Eurostat apri_pi15_outa',
            'description': 'Agricultural output price indices (2015=100)',
            'coverage': 'EU27 countries, annual 2000+',
            'granularity': 'National, product level',
            'access': 'Free API',
            'update_freq': 'Annual',
            'score_coverage': 5, 'score_granularity': 4, 'score_access': 5,
            'score_freshness': 3, 'score_relevance': 5,
        },
        {
            'source': 'World Bank Pink Sheet',
            'description': 'Global commodity prices: urea, DAP, natural gas',
            'coverage': 'Global, monthly 1960+',
            'granularity': 'Global benchmark prices',
            'access': 'Free Excel download',
            'update_freq': 'Monthly',
            'score_coverage': 4, 'score_granularity': 2, 'score_access': 5,
            'score_freshness': 5, 'score_relevance': 4,
        },
        {
            'source': 'Eurostat FADN',
            'description': 'Farm Accountancy Data Network — farm-level economics',
            'coverage': 'EU farm sample, annual',
            'granularity': 'Farm type, region (NUTS2)',
            'access': 'Aggregate free; microdata NDA',
            'update_freq': 'Annual (2yr lag)',
            'score_coverage': 4, 'score_granularity': 5, 'score_access': 2,
            'score_freshness': 2, 'score_relevance': 5,
        },
        {
            'source': 'Eurostat ef_m_farmleg',
            'description': 'Farm structure survey — farm size, tenure, labour',
            'coverage': 'EU27, every 3-4 years',
            'granularity': 'NUTS2 regional',
            'access': 'Free API',
            'update_freq': 'Every 3-4 years',
            'score_coverage': 4, 'score_granularity': 4, 'score_access': 5,
            'score_freshness': 2, 'score_relevance': 3,
        },
        {
            'source': 'Eurostat apri_ap_ina',
            'description': 'Input price indices: fertilisers, energy, pesticides',
            'coverage': 'EU27, annual 2000+',
            'granularity': 'National, input category',
            'access': 'Free API',
            'update_freq': 'Annual',
            'score_coverage': 5, 'score_granularity': 4, 'score_access': 5,
            'score_freshness': 3, 'score_relevance': 5,
        },
        {
            'source': 'Copernicus LUCAS',
            'description': 'Land use / land cover survey across EU',
            'coverage': 'EU27, every 3 years',
            'granularity': 'Point survey, NUTS2',
            'access': 'Free download',
            'update_freq': 'Every 3 years',
            'score_coverage': 4, 'score_granularity': 4, 'score_access': 4,
            'score_freshness': 2, 'score_relevance': 3,
        },
        {
            'source': 'IFA Fertilizer Statistics',
            'description': 'Country-level fertiliser consumption and trade',
            'coverage': 'Global, annual',
            'granularity': 'National, nutrient type',
            'access': 'Partial free; full membership',
            'update_freq': 'Annual',
            'score_coverage': 4, 'score_granularity': 3, 'score_access': 3,
            'score_freshness': 3, 'score_relevance': 4,
        },
        {
            'source': 'Wageningen Economic Research',
            'description': 'Published farm cost benchmarks NL/EU potatoes',
            'coverage': 'Netherlands focus, some EU',
            'granularity': 'Crop type, farm size',
            'access': 'Free reports (PDF)',
            'update_freq': 'Annual',
            'score_coverage': 3, 'score_granularity': 5, 'score_access': 4,
            'score_freshness': 3, 'score_relevance': 5,
        },
        {
            'source': 'FAOSTAT',
            'description': 'Global crop production, trade, food balance',
            'coverage': 'Global, annual 1961+',
            'granularity': 'National',
            'access': 'Free API + download',
            'update_freq': 'Annual',
            'score_coverage': 5, 'score_granularity': 3, 'score_access': 5,
            'score_freshness': 3, 'score_relevance': 3,
        },
    ]

    df = pd.DataFrame(sources)
    df['total_score'] = (
        df['score_coverage'] + df['score_granularity'] +
        df['score_access'] + df['score_freshness'] + df['score_relevance']
    )
    df['priority_tier'] = pd.cut(
        df['total_score'],
        bins=[0, 15, 19, 25],
        labels=['Tier 3 — Monitor', 'Tier 2 — Useful', 'Tier 1 — Priority']
    )
    df = df.sort_values('total_score', ascending=False).reset_index(drop=True)
    print("\nData source inventory (top 5):")
    print(df[['source','total_score','priority_tier']].head(5).to_string(index=False))
    return df


def main():
    print("=" * 55)
    print("Running analysis")
    print("=" * 55)

    prod, costs, prices = load_processed()

    summary    = country_summary(costs)
    spike      = cost_spike_analysis(costs)
    volatility = price_volatility(prices)
    regen      = regen_potential(costs)
    inventory  = data_source_inventory()

    # Save all
    summary.to_csv(   os.path.join(PROCESSED, 'analysis_country_summary.csv'),   index=False)
    spike.to_csv(     os.path.join(PROCESSED, 'analysis_cost_spike.csv'),         index=False)
    volatility.to_csv(os.path.join(PROCESSED, 'analysis_price_volatility.csv'),  index=False)
    regen.to_csv(     os.path.join(PROCESSED, 'analysis_regen_potential.csv'),   index=False)
    inventory.to_csv( os.path.join(PROCESSED, 'analysis_data_inventory.csv'),    index=False)

    print("\nSaved 5 analysis files to data/processed/")


if __name__ == '__main__':
    main()
