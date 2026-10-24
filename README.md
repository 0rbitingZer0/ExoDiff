# ExoDiff

**Site:** https://0rbitingzer0.github.io/ExoDiff/

ExoDiff checks public exoplanet data for inconsistencies. It compares measurements within research archive records, across NASA's archive and public catalogue pages, against exoplanet.eu, and with updated stellar distances from Gaia.

It identifies discrepancies worth investigating, shows the evidence behind them, and tests possible explanations. A finding is not proof of an error, and ExoDiff does not decide which published value is correct.

ExoDiff focuses on automated consistency checks across catalogue records and public pages, linking discrepancies back to their sources rather than selecting a single value as correct.

## Data sources

- [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/)
- [NASA Exoplanet Catalog](https://science.nasa.gov/exoplanets/exoplanet-catalog/)
- [exoplanet.eu](https://exoplanet.eu/)
- [Gaia DR3](https://www.cosmos.esa.int/web/gaia/dr3)
- [SIMBAD](https://simbad.cds.unistra.fr/simbad/), used to match star names between catalogues

## Implementation

Built with Claude Opus 5.5. The data processing and comparisons are performed by ordinary code, not by an AI model interpreting the measurements.

ExoDiff is an independent project and is not affiliated with NASA, Caltech, ESA, exoplanet.eu or CDS.

For the checks, statistical rules, validation results and limitations, see the [methodology](https://0rbitingzer0.github.io/ExoDiff/#/methodology) page.

## Credits

This research has made use of the [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/), which is operated by the California Institute of Technology, under contract with the National Aeronautics and Space Administration under the Exoplanet Exploration Program.

This research has made use of data obtained from or tools provided by the portal [exoplanet.eu](https://exoplanet.eu/) of The Extrasolar Planets Encyclopaedia ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)).

Gaia data: ESA/Gaia/DPAC, [CC BY-NC 3.0 IGO](https://www.cosmos.esa.int/web/gaia-users/license).

This research has made use of the SIMBAD database, CDS, Strasbourg Astronomical Observatory, France.
