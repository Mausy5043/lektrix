#!/usr/bin/env sqlite3
-- SQLite3 script
-- create a table `mains` for KAMSTRUP smart electricity meter readings
-- create a table `production` for SOLAREDGE solar panel monitoring
-- create a table `charger` for ZAPPI EV charger monitoring
-- create a table `storage` for *future* home battery monitoring

DROP TABLE IF EXISTS mains;

-- T1* and T2* are power imported/exported in Wh
-- power* is momentary flux in W
-- tarif and swits are either a `1` or a `2`

CREATE TABLE mains (
  sample_time   datetime NOT NULL PRIMARY KEY,
  sample_epoch  integer,
  T1in          integer,
  T2in          integer,
  powerin       integer,
  T1out         integer,
  T2out         integer,
  powerout      integer,
  tarif         integer,
  swits         integer
  );

-- SQLite3 automatically creates a UNIQUE INDEX on the PRIMARY KEY in the background.
-- So, no index needed.


DROP TABLE IF EXISTS production;

-- energy is cumulative power generated in Wh

CREATE TABLE production (
  sample_time   datetime NOT NULL PRIMARY KEY,
  sample_epoch  integer,
  site_id       integer,
  energy        integer
  );

CREATE INDEX idx_prod_site ON production(site_id);

-- Set a starting value and add first two datapoints (not available in SolarEdge DB)
INSERT INTO production (sample_time, sample_epoch, site_id, energy) VALUES ('2020-02-20 09:08:22', 1582186102, 1508443, 0);
INSERT INTO production (sample_time, sample_epoch, site_id, energy) VALUES ('2020-02-21 23:30:00', 1582324200 , 1508443, 510);
INSERT INTO production (sample_time, sample_epoch, site_id, energy) VALUES ('2020-02-22 09:30:00', 1582360200 , 1508443, 641);


DROP TABLE IF EXISTS charger;

CREATE TABLE charger (
    sample_time     datetime NOT NULL PRIMARY KEY,
    sample_epoch    integer,
    site_id         float,
    exp             float,
    gen             float,
    gep             float,
    imp             float,
    h1b             float,
    h1d             float,
    v1              integer,
    frq             integer
    );

CREATE INDEX idx_chrg_site ON charger(site_id);
-- SQLite3 automatically creates a UNIQUE INDEX on the PRIMARY KEY in the background.
-- So, no index needed.
