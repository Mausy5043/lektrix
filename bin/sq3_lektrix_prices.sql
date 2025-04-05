#!/usr/bin/env sqlite3
-- SQLite3 script
-- create a table `prices` to store dynamic electricity prices

DROP TABLE IF EXISTS prices;

CREATE TABLE prices (
  sample_time   datetime NOT NULL PRIMARY KEY,
  sample_epoch  integer,
  price         float
  );

-- SQLite3 automatically creates a UNIQUE INDEX on the PRIMARY KEY in the background.
-- So, no index needed.
