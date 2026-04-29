# Data Sources — EU Potato Supply Chain Analytics

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
