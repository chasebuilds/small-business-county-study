# Limitations

What this study can and cannot support.

## Coverage of the data

- **County Business Patterns (CBP) counts employer establishments only.** It leaves out the self-employed with no payroll, most crop and animal farms, railroads, private households and government employees. Small businesses in rural counties are often in those groups, so counts here understate them.
- **An establishment is a location, not a company.** A chain with several stores in a county counts once per store.
- **Employment is a March snapshot,** the payroll for the pay period containing March 12, not annual jobs.
- **Industry codes changed** between NAICS 2012, 2017 and 2022. Sector comparisons across those years may include reclassification.

## Suppression and noise

- 2012 to 2016 files withhold many county-sector employment values. They are treated as missing, not zero, and no regional sector total is computed when any county is missing.
- From 2017 on, values are published with noise and flagged (G under 2%, H 2% to under 5%, J 5% or more). About a third of county-sector cells in 2018 to 2023 are flagged J, so small-sector percentage changes are unreliable.
- Because of this, sector-level job changes are only compared from 2018.
- The one-step drop in the regional establishment count between 2016 and 2017 is not explained by this analysis.

## Survey estimates

- ACS figures are five-year survey estimates (2020 to 2024) with margins of error. 23 of 31 county median-income estimates have a margin over 10% of the estimate, so county rankings are rough.
- The regional income figure is the median of 31 county medians. That is not the same as the median household income across the whole region.
- Broadband of any type includes cellular data plans.
- Broadband and income move together across counties (correlation about 0.5). This is one cross-section of 31 points and does not show cause.

## Scope

- "Eastern Kentucky" is defined here as five development districts. Other definitions give other totals.
- Population per-resident rates use the 2023 population estimate against 2023 business counts. Visitors, commuters and customers from neighboring counties are not accounted for.
- The study is descriptive. It does not test why the region differs from Kentucky or the US, and it makes no claim about any policy.
- Only free, keyless public files are used. The Census API (which now needs a key) is not used.
