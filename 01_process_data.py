"""
01_process_data.py
------------------
Reads raw CSVs from data/raw/, cleans and merges them into
analysis-ready datasets saved to data/processed/.

Inputs  (data/raw/)
  eurostat_production.csv         — area_ha, production_t, yield_t_ha
  eurostat_price_index.csv        — price_index_2015_100
  worldbank_commodity_prices.csv  — urea_usd_mt, dap_usd_mt, natgas_europe_usd_mmbtu

Outputs (data/processed/)
  production_clean.csv    — production data with derived metrics
  costs_merged.csv        — production + commodity prices merged by year
  price_analysis.csv      — price index with year-on-year change
"""

import os
import pandas as pd
import numpy as np

try:
    BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
except NameError:
    BASE = '.'

RAW       = os.path.join(BASE, 'data', 'raw')
PROCESSED = os.path.join(BASE, 'data', 'processed')
os.makedirs(PROCESSED, exist_ok=True)

COUNTRIES = ['France', 'Netherlands', 'Poland', 'Germany']


def load_raw():
    print("Loading raw data...")

    prod = pd.read_csv(os.path.join(RAW, 'eurostat_production.csv'))
    price = pd.read_csv(os.path.join(RAW, 'eurostat_price_index.csv'))
    wb = pd.read_csv(os.path.join(RAW, 'worldbank_commodity_prices.csv'))

    print(f"  Production:  {prod.shape}  {list(prod.columns)}")
    print(f"  Price index: {price.shape}  {list(price.columns)}")
    print(f"  World Bank:  {wb.shape}  {list(wb.columns)}")
    return prod, price, wb


def process_production(prod: pd.DataFrame) -> pd.DataFrame:
    print("\nProcessing production data...")

    df = prod.copy()
    df = df[df['country'].isin(COUNTRIES)]
    df = df.dropna(subset=['area_ha', 'production_t'])

    # Derived metrics
    df['production_kt']        = (df['production_t'] / 1000).round(1)
    df['area_kha']             = (df['area_ha'] / 1000).round(1)

    # Estimated farmgate value (proxy: €180/t average EU ware potato price)
    df['est_farmgate_value_meur'] = (df['production_t'] * 180 / 1e6).round(1)

    # Fill missing yield with derived value
    mask = df['yield_t_ha'].isna()
    df.loc[mask, 'yield_t_ha'] = (
        df.loc[mask, 'production_t'] / df.loc[mask, 'area_ha']
    ).round(2)

    df = df.sort_values(['country', 'year']).reset_index(drop=True)
    print(f"  Rows: {len(df)}, Countries: {df['country'].nunique()}, "
          f"Years: {df['year'].min()}–{df['year'].max()}")
    return df


def process_costs(prod: pd.DataFrame, wb: pd.DataFrame) -> pd.DataFrame:
    print("\nMerging production with commodity prices...")

    # Restrict to overlapping years
    years = prod['year'].unique()
    wb_filtered = wb[wb['year'].isin(years)].copy()

    merged = prod.merge(wb_filtered, on='year', how='left')

    # Estimated fertilizer cost per hectare
    # Potato crop ~200 kg N/ha urea equivalent, ~100 kg P/ha DAP equivalent
    # Urea is 46% N so 200 kg N = ~435 kg urea; DAP is 18% N / 46% P
    KG_UREA_PER_HA = 435
    KG_DAP_PER_HA  = 220
    MT_PER_KG      = 0.001

    merged['est_fert_cost_eur_ha'] = (
        (merged['urea_usd_mt'] * KG_UREA_PER_HA * MT_PER_KG +
         merged['dap_usd_mt']  * KG_DAP_PER_HA  * MT_PER_KG) * 0.92  # USD -> EUR approx
    ).round(1)

    # Energy cost proxy: 15 GJ/ha * natgas price converted (1 mmbtu = 1.055 GJ)
    GJ_PER_HA     = 15
    GJ_PER_MMBTU  = 1.055
    merged['est_energy_cost_eur_ha'] = (
        merged['natgas_europe_usd_mmbtu'] * (GJ_PER_HA / GJ_PER_MMBTU) * 0.92
    ).round(1)

    merged['est_total_input_cost_eur_ha'] = (
        merged['est_fert_cost_eur_ha'] + merged['est_energy_cost_eur_ha']
    ).round(1)

    merged = merged.sort_values(['country', 'year']).reset_index(drop=True)
    print(f"  Merged rows: {len(merged)}")
    return merged


def process_prices(price: pd.DataFrame) -> pd.DataFrame:
    print("\nProcessing price index data...")

    df = price.copy()
    df = df[df['country'].isin(COUNTRIES)]
    df = df.sort_values(['country', 'year'])

    # Year-on-year % change
    df['price_yoy_pct'] = (
        df.groupby('country')['price_index_2015_100']
        .pct_change() * 100
    ).round(1)

    # 3-year rolling average to smooth volatility
    df['price_3yr_avg'] = (
        df.groupby('country')['price_index_2015_100']
        .transform(lambda x: x.rolling(3, min_periods=1).mean())
    ).round(1)

    print(f"  Rows: {len(df)}")
    return df.reset_index(drop=True)


def main():
    print("=" * 55)
    print("Processing raw data")
    print("=" * 55)

    prod, price, wb = load_raw()

    prod_clean   = process_production(prod)
    costs_merged = process_costs(prod_clean, wb)
    price_clean  = process_prices(price)

    # Save
    prod_clean.to_csv(os.path.join(PROCESSED, 'production_clean.csv'),   index=False)
    costs_merged.to_csv(os.path.join(PROCESSED, 'costs_merged.csv'),     index=False)
    price_clean.to_csv(os.path.join(PROCESSED, 'price_analysis.csv'),    index=False)

    print("\nSaved to data/processed/:")
    print(f"  production_clean.csv  ({len(prod_clean)} rows)")
    print(f"  costs_merged.csv      ({len(costs_merged)} rows)")
    print(f"  price_analysis.csv    ({len(price_clean)} rows)")

    print("\nSample — costs_merged (2022 energy crisis year):")
    spike = costs_merged[costs_merged['year'] == 2022][
        ['country', 'year', 'yield_t_ha', 'est_fert_cost_eur_ha',
         'est_energy_cost_eur_ha', 'est_total_input_cost_eur_ha']
    ]
    print(spike.to_string(index=False))


if __name__ == '__main__':
    main()
