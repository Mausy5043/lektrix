![Static Badge](https://img.shields.io/badge/release-rolling-lightgreen)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# lektrix

Interface
with [KAMSTRUP smart electricity meter](https://www.kamstrup.com/), [SolarEdge API](https://www.solaredge.com/)
and [ZAPPI v2](https://myenergi.com/) API using Raspberry Pi

### What is does

- Read data from a KAMSTRUP smart meter.
- Read data from solarpanels via SolarEdge API.
- Read data from zappi v2 EV charger via ZAPPI API.
- Store all that data in an SQLite3 database.
- Regularly create trendgraphs.
- Show trendgraphs on a local website.

### Installing

Clone the repository somewhere handy. Adding the `lektrix` directory to your `$PATH` may help.  
To install run `lektrix --install`.  
Use `lektrix --uninstall` to uninstall.

### Usage

`lektrix <options>`

`--hours HOURS`, `--days DAYS`, `--months MONTHS`, `--years YEARS`  
Create a bar graph of the given number of HOURS/DAYS/MONTHS/YEARS

`--balance`, `--balances`

See [docs/trends.md](./docs/trends.md) for more info.
