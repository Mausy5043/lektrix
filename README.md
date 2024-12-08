
[![License](https://img.shields.io/github/license/mausy5043/lektrix)](LICENSE)
![Static Badge](https://img.shields.io/badge/release-rolling-lightgreen)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Mausy5043/lektrix/master.svg)](https://results.pre-commit.ci/latest/github/Mausy5043/lektrix/master)

# lektrix

Interface
with [KAMSTRUP smart electricity meter](https://www.kamstrup.com/), [SolarEdge API](https://www.solaredge.com/), [ZAPPI v2](https://myenergi.com/) and [HomeWizard](https://www.homewizard.com/) APIs using Raspberry Pi

## What is does

- Read data from a KAMSTRUP smart meter. (deprecated)
- Read data from solarpanels via SolarEdge API.
- Read data from zappi v2 EV charger via ZAPPI API.
- Read data from Home Wizard P1 meter via the Home Wizard API.
- Store all that data in an SQLite3 database.
- Regularly create trendgraphs.
- Show trendgraphs on a local website.

## Installing

Clone the repository somewhere handy. Adding the `lektrix` directory to your `$PATH` may help.
To install run `lektrix --install`.
Use `lektrix --uninstall` to uninstall.

## Usage

`lektrix <options>`

`--hours HOURS`, `--days DAYS`, `--months MONTHS`, `--years YEARS`
Create a bar graph of the given number of HOURS/DAYS/MONTHS/YEARS

`--balance`, `--balances`

See [docs/trends.md](./docs/trends.md) for more info.

## Disclaimer & License
As of September 2024 `lektrix` is distributed under [AGPL-3.0-or-later](LICENSE).
