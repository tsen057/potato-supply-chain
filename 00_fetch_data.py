"""
00_fetch_data.py
----------------
Fetches real potato production data from:
  - Eurostat Statistics API (apro_cpsh1)     — area harvested & production volume
  - Eurostat Statistics API (apri_pi15_outa) — producer price indices
  - World Bank Pink Sheet (Excel download)   — urea, DAP, European natural gas prices

Saves raw CSVs to data/raw/ for use by the rest of the pipeline.

Part of: EU Potato Supply Chain Analytics
Author: Tejaswini Sengaonkar
Sources:
  - Eurostat © European Union, 1995-2024. Licence: CC BY 4.0
    https://ec.europa.eu/eurostat/web/main/data/database
  - World Bank Commodity Markets (Pink Sheet). Licence: CC BY 4.0
    https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/
    related/CMO-Historical-Data-Monthly.xlsx

Correct API codes (verified 2026-04-29):
  apro_cpsh1   crops=R1000  strucpro: AR, PR_HU_EU, YI_HU_EU
  apri_pi15_outa  product=050000  p_adj=NI (nominal index only)
  World Bank   Pink Sheet Excel — NOT the v2/indicator API
"""

import io
import os

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Paths — works whether run as a script OR from a Jupyter notebook
# ---------------------------------------------------------------------------
try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    RAW = os.path.normpath(os.path.join(_SCRIPT_DIR, '..', 'data', 'raw'))
except NameError:
    RAW = os.path.normpath(os.path.join('data', 'raw'))

os.makedirs(RAW, exist_ok=True)

COUNTRIES     = {'FR': 'France', 'NL': 'Netherlands', 'PL': 'Poland', 'DE': 'Germany'}
EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


# ---------------------------------------------------------------------------
# Eurostat helpers
# ---------------------------------------------------------------------------

def parse_eurostat_jsonstat(data: dict, value_label: str) -> pd.DataFrame:
    """
    Parse a Eurostat JSON-stat response into a tidy DataFrame.
    Always uses raw category CODES (not display labels) so that
    merges on 'geo', 'time', 'crops' etc. work reliably.
    """
    if not data or 'value' not in data:
        return pd.DataFrame()

    dim_keys  = data['id']
    dim_sizes = data['size']
    dims      = data['dimension']

    dim_pos_to_code = []
    for d in dim_keys:
        pos_to_code = {v: k for k, v in dims[d]['category']['index'].items()}
        dim_pos_to_code.append(pos_to_code)

    values = data['value']
    if isinstance(values, dict):
        values = {int(k): v for k, v in values.items()}

    total = 1
    for s in dim_sizes:
        total *= s

    rows = []
    for flat_idx in range(total):
        val = (values.get(flat_idx) if isinstance(values, dict)
               else (values[flat_idx] if flat_idx < len(values) else None))
        if val is None:
            continue

        remainder = flat_idx
        coords    = []
        for size in reversed(dim_sizes):
            coords.append(remainder % size)
            remainder //= size
        coords.reverse()

        row = {dim_keys[i]: dim_pos_to_code[i][coords[i]] for i in range(len(dim_keys))}
        row[value_label] = val
        rows.append(row)

    return pd.DataFrame(rows)


def estat_get(dataset: str, params: dict, label: str) -> pd.DataFrame:
    """GET one Eurostat slice; return empty DataFrame on any failure."""
    url = f"{EUROSTAT_BASE}/{dataset}"
    try:
        r = requests.get(url, params={**params, 'format': 'JSON', 'lang': 'EN'},
                         timeout=30)
        if r.status_code != 200:
            reason = r.headers.get('x-deny-reason', r.text[:120])
            print(f"  WARNING: HTTP {r.status_code} — {reason}")
            return pd.DataFrame()
        df = parse_eurostat_jsonstat(r.json(), label)
        print(f"  ✓ {params.get('strucpro', params.get('product', ''))}: {len(df)} rows")
        return df
    except requests.exceptions.RequestException as e:
        print(f"  WARNING: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# 1. Eurostat: potato production (apro_cpsh1)
# ---------------------------------------------------------------------------

def fetch_production_data() -> pd.DataFrame:
    """
    Eurostat apro_cpsh1: area (AR), production (PR_HU_EU), yield (YI_HU_EU)
    for potatoes (R1000) across FR, NL, PL, DE, 2015-2023.

    Verified codes (2026-04-29):
      crops    = R1000      Potatoes (including seed potatoes)
      strucpro = AR         Area (1000 ha)
      strucpro = PR_HU_EU   Harvested production in EU standard humidity (1000 t)
      strucpro = YI_HU_EU   Yield in EU standard humidity (t/ha)
    """
    common = dict(crops='R1000', geo=list(COUNTRIES.keys()),
                  sinceTimePeriod='2015', untilTimePeriod='2023')

    print("  Fetching area harvested (AR)...")
    ar = estat_get('apro_cpsh1', {**common, 'strucpro': 'AR'},         'area_ha')
    print("  Fetching production quantity (PR_HU_EU)...")
    pr = estat_get('apro_cpsh1', {**common, 'strucpro': 'PR_HU_EU'},   'production_t')
    print("  Fetching yield (YI_HU_EU)...")
    yi = estat_get('apro_cpsh1', {**common, 'strucpro': 'YI_HU_EU'},   'yield_t_ha')

    if ar.empty or pr.empty:
        print("  WARNING: Missing AR or PR data — using fallback CSV")
        return pd.DataFrame()

    # Eurostat reports in 1 000 ha / 1 000 t; yield is already in t/ha
    ar['area_ha']      = ar['area_ha']      * 1_000
    pr['production_t'] = pr['production_t'] * 1_000

    merged = (
        ar[['geo', 'time', 'crops', 'area_ha']]
        .merge(pr[['geo', 'time', 'crops', 'production_t']],
               on=['geo', 'time', 'crops'], how='inner')
    )
    if not yi.empty:
        merged = merged.merge(yi[['geo', 'time', 'crops', 'yield_t_ha']],
                              on=['geo', 'time', 'crops'], how='left')
    else:
        # Derive yield as fallback if YI endpoint is missing
        merged['yield_t_ha'] = (merged['production_t'] / merged['area_ha']).round(2)

    merged['country'] = merged['geo'].map(COUNTRIES)
    merged['year']    = merged['time'].astype(int)

    out = merged[merged['country'].notna()][
        ['country', 'year', 'area_ha', 'production_t', 'yield_t_ha']
    ].sort_values(['country', 'year'])

    print(f"  ✓ Final: {len(out)} rows, "
          f"{out['year'].min()}–{out['year'].max()}, "
          f"{out['country'].nunique()} countries")
    return out


# ---------------------------------------------------------------------------
# 2. Eurostat: producer price index (apri_pi15_outa)
# ---------------------------------------------------------------------------

def fetch_price_index() -> pd.DataFrame:
    """
    Eurostat apri_pi15_outa: potato producer price index (2015=100).

    Verified codes (2026-04-29):
      product = 050000   Potatoes (including seeds)
      unit    = I15      Index, base year 2015=100
      p_adj   = NI       Nominal index (RI = real index, excluded)
    """
    print("  Fetching producer price index (050000, NI)...")
    df = estat_get('apri_pi15_outa', {
        'product':         '050000',
        'geo':             list(COUNTRIES.keys()),
        'sinceTimePeriod': '2015',
        'untilTimePeriod': '2023',
        'unit':            'I15',
    }, 'price_index_2015_100')

    if df.empty:
        print("  WARNING: No data — using fallback CSV")
        return df

    # Keep nominal index only — drop real index (RI)
    if 'p_adj' in df.columns:
        df = df[df['p_adj'] == 'NI']

    df['country'] = df['geo'].map(COUNTRIES)
    df['year']    = df['time'].astype(int)

    out = df[df['country'].notna()][
        ['country', 'year', 'price_index_2015_100']
    ].sort_values(['country', 'year'])

    print(f"  ✓ Final: {len(out)} rows, "
          f"{out['year'].min()}–{out['year'].max()}, "
          f"{out['country'].nunique()} countries")
    return out


# ---------------------------------------------------------------------------
# 3. World Bank Pink Sheet: fertilizer + energy prices
# ---------------------------------------------------------------------------

def fetch_worldbank_fertilizer() -> pd.DataFrame:
    """
    Fetches annual average urea, DAP, and European natural gas prices from
    the World Bank Commodity Markets Pink Sheet (monthly Excel file).

    NOTE: The World Bank v2/indicator API does NOT carry fertilizer prices.
    The correct source is the Pink Sheet Excel download.

    Verified working 2026-04-29. Column 'Urea' has a trailing space in the
    sheet — stripped automatically with .str.strip().

    Columns returned:
      year                      int
      urea_usd_mt               float  — Urea E. Europe, USD/mt
      dap_usd_mt                float  — DAP, USD/mt
      natgas_europe_usd_mmbtu   float  — Natural gas Europe, USD/mmbtu
    """
    URL = (
        "https://thedocs.worldbank.org/en/doc/"
        "18675f1d1639c7a34d463f59263ba0a2-0050012025/related/"
        "CMO-Historical-Data-Monthly.xlsx"
    )

    print("  Fetching World Bank Pink Sheet...")
    try:
        resp = requests.get(URL, timeout=30)
        if resp.status_code != 200:
            reason = resp.headers.get('x-deny-reason', resp.text[:80])
            print(f"  WARNING: HTTP {resp.status_code} — {reason}")
            print("           Fallback: data/raw/worldbank_commodity_prices_verified.csv")
            return pd.DataFrame()

        xl = pd.ExcelFile(io.BytesIO(resp.content))
        df = xl.parse('Monthly Prices', header=4)

        # Strip trailing spaces (Pink Sheet has 'Urea ' with trailing space)
        df.columns = df.columns.str.strip()

        df = df.rename(columns={
            'Unnamed: 0':          'date',
            'Urea':                'urea_usd_mt',
            'DAP':                 'dap_usd_mt',
            'Natural gas, Europe': 'natgas_europe_usd_mmbtu',
        })

        keep = ['date', 'urea_usd_mt', 'dap_usd_mt', 'natgas_europe_usd_mmbtu']
        df   = df[keep].dropna(subset=['urea_usd_mt'])

        # Keep 2010 onwards — date strings formatted as '2010M01'
        df = df[df['date'].astype(str).str.match(r'20[1-9]\d')]

        # Aggregate to annual averages for consistency with Eurostat annual data
        df['year'] = df['date'].astype(str).str[:4].astype(int)
        annual = (
            df.groupby('year')[['urea_usd_mt', 'dap_usd_mt', 'natgas_europe_usd_mmbtu']]
            .mean()
            .round(2)
            .reset_index()
        )

        print(f"  ✓ {len(annual)} years fetched "
              f"({annual['year'].min()}–{annual['year'].max()})")
        return annual

    except Exception as e:
        print(f"  ✗ Error: {e}")
        print("  Fallback: data/raw/worldbank_commodity_prices_verified.csv")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# 4. Data source documentation
# ---------------------------------------------------------------------------

def save_readme():
    content = """# Data Sources — EU Potato Supply Chain Analytics

## Raw Data Files

### eurostat_production.csv
**Source**  : Eurostat, dataset `apro_cpsh1` — Crop production in EU standard humidity
**URL**     : https://ec.europa.eu/eurostat/databrowser/view/apro_cpsh1/
**Licence** : CC BY 4.0 — © European Union, 1995-2024
**Variables**: area_ha, production_t, yield_t_ha
**Countries**: France (FR), Netherlands (NL), Poland (PL), Germany (DE)
**Years**   : 2015–2023
**Codes**   : crops=R1000 (Potatoes incl. seed), strucpro=AR/PR_HU_EU/YI_HU_EU

### eurostat_price_index.csv
**Source**  : Eurostat, dataset `apri_pi15_outa` — Agricultural output price indices
**URL**     : https://ec.europa.eu/eurostat/databrowser/view/apri_pi15_outa/
**Licence** : CC BY 4.0 — © European Union, 1995-2024
**Variables**: price_index_2015_100 (nominal, base year 2015=100)
**Codes**   : product=050000, unit=I15, p_adj=NI (nominal only)

### worldbank_commodity_prices.csv
**Source**  : World Bank Commodity Markets Pink Sheet
**File**    : CMO-Historical-Data-Monthly.xlsx (Monthly Prices sheet)
**URL**     : https://thedocs.worldbank.org/en/doc/
              18675f1d1639c7a34d463f59263ba0a2-0050012025/related/
              CMO-Historical-Data-Monthly.xlsx
**Licence** : CC BY 4.0
**Variables**: urea_usd_mt, dap_usd_mt, natgas_europe_usd_mmbtu (annual averages)
**Note**    : Fetched from Excel — NOT the v2/indicator API (fertilizer series
              are not available through that endpoint)

### fadn_input_costs_verified.csv
**Source**  : FADN (Farm Accountancy Data Network), European Commission +
              Copa-Cogeca / Wageningen Economic Research published benchmarks
**Note**    : Microdata requires NDA; values are from published aggregate reports

### data_source_inventory.csv
**Source**  : Manually compiled from official source descriptions
**Purpose** : Evaluates 15+ agricultural data sources for quality, access, relevance
"""
    path = os.path.join(RAW, 'DATA_SOURCES.md')
    with open(path, 'w') as f:
        f.write(content)
    print(f"  -> Saved DATA_SOURCES.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 55)
    print("Fetching real data from government sources")
    print("=" * 55)

    print("\n[1/4] Eurostat: Potato production (apro_cpsh1)")
    prod_df = fetch_production_data()
    if not prod_df.empty:
        out = os.path.join(RAW, 'eurostat_production.csv')
        prod_df.to_csv(out, index=False)
        print(f"  -> Saved eurostat_production.csv ({len(prod_df)} rows)")
        print(prod_df.to_string(index=False))
    else:
        print("  -> No data — pipeline will use verified fallback CSV")

    print("\n[2/4] Eurostat: Producer price index (apri_pi15_outa)")
    price_df = fetch_price_index()
    if not price_df.empty:
        out = os.path.join(RAW, 'eurostat_price_index.csv')
        price_df.to_csv(out, index=False)
        print(f"  -> Saved eurostat_price_index.csv ({len(price_df)} rows)")
        print(price_df.to_string(index=False))
    else:
        print("  -> No data — pipeline will use verified fallback CSV")

    print("\n[3/4] World Bank: Fertilizer & energy prices (Pink Sheet)")
    fert_df = fetch_worldbank_fertilizer()
    if not fert_df.empty:
        out = os.path.join(RAW, 'worldbank_commodity_prices.csv')
        fert_df.to_csv(out, index=False)
        print(f"  -> Saved worldbank_commodity_prices.csv ({len(fert_df)} rows)")
        print(fert_df.to_string(index=False))
    else:
        print("  -> No data — pipeline will use verified fallback CSV")

    print("\n[4/4] Saving data source documentation")
    save_readme()

    print("\nDone.")
    print("All three live APIs confirmed working as of 2026-04-29.")
    print("If any call fails, the pipeline uses data/raw/*_verified.csv")


if __name__ == '__main__':
    main()
