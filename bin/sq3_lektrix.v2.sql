#!/usr/bin/env sqlite3
-- SQLite3 script
-- create a table `mains` for HomeWizard electricity meter readings
-- create a table `production` for SOLAREDGE solar panel monitoring
-- create a table `prices` for keeping track of dynamic electricity prices


-- --------------------------------------------------------
-- Track production and consumption of the home, EV and PV/Battery
-- --------------------------------------------------------

DROP TABLE IF EXISTS charger;
DROP TABLE IF EXISTS mains;

CREATE TABLE mains (
    sample_time     datetime NOT NULL PRIMARY KEY,
    sample_epoch    integer,
    site_id         text,
    exp             integer,
    imp             integer,
    gen             integer,
    gep             integer,
    evn             integer,
    evp             integer,
    v1              integer,
    frq             integer
    );

CREATE INDEX idx_mains_site ON mains(site_id);
CREATE INDEX idx_mains_epoch ON mains(sample_epoch);
-- SQLite3 automatically creates a UNIQUE INDEX on the PRIMARY KEY in the background.
INSERT INTO mains (sample_time, sample_epoch, site_id, exp, imp, gen, gep, evn, evp, v1, frq)
       VALUES ('2025-04-09 09:00:00', 1744182000, '4.2', 0, 0, 0, 0, 0, 0, 0, 0)

-- --------------------------------------------------------
-- Track PV production
-- --------------------------------------------------------

DROP TABLE IF EXISTS production;

-- energy is cumulative power generated in Wh

CREATE TABLE production (
  sample_time   datetime NOT NULL PRIMARY KEY,
  sample_epoch  integer,
  site_id       integer,
  solar         integer
  );

CREATE INDEX idx_prod_site ON production(site_id);
CREATE INDEX idx_prod_epoch ON production(sample_epoch);
--
---- Set a starting value and add first two datapoints (not available in SolarEdge DB)
--INSERT INTO production (sample_time, sample_epoch, site_id, energy)
--       VALUES ('2020-02-20 09:08:22', 1582186102, 1508443, 0);
--INSERT INTO production (sample_time, sample_epoch, site_id, energy)
--       VALUES ('2020-02-21 23:30:00', 1582324200, 1508443, 510);
--INSERT INTO production (sample_time, sample_epoch, site_id, energy)
--       VALUES ('2020-02-22 09:30:00', 1582360200, 1508443, 641);

-- --------------------------------------------------------
-- Track dynamic electricity prices
-- --------------------------------------------------------
DROP TABLE IF EXISTS prices;

CREATE TABLE prices (
  sample_time   datetime NOT NULL PRIMARY KEY,
  sample_epoch  integer,
  site_id       text,
  price         float
  );

CREATE INDEX idx_prices_epoch ON prices(sample_epoch);
-- SQLite3 automatically creates a UNIQUE INDEX on the PRIMARY KEY in the background.
