# Family relationship map

`family_map.py` reads `feriancovci.csv` and creates one connected, generation-
based family tree as a PNG. It uses Python's standard library and macOS's
built-in `sips` image converter; no Python packages or other tools need to be
installed.

## Requirements

- macOS
- Python 3

## Run it

From this folder, run:

```sh
python3 family_map.py feriancovci.csv --output family_map.png
```

The generated `family_map.png` is written to this folder. To use another CSV
or output path, replace the paths in the command. The defaults are
`feriancovci.csv` and `family_map.png`, so the short form also works:

```sh
python3 family_map.py
```

## How it works

- The family roles establish generations and the central parents. For example,
  the mother and father are paired in the main household; the mother's parents
  and sister sit above/beside her branch; the father's aunts and uncles share
  the father's generation.
- `Rodinna priduzenost` assigns a relative to the mother's or father's side of
  that one tree. It is not used as a separate tree or a location grouping.
- People with the same `Vztah` value **in the same location** share a
  relationship connector. That connector links partners and anchors their
  children.
- A person's `Deti` value points to the `Vztah` of their parent relationship.
  Those links are used whenever present. When a cousin has no `Deti` value,
  the script uses the role and nearby family rows to associate that cousin
  with the closest preceding aunt/uncle family group on the same side (and,
  on the father's side, in the same location).
- Family roles are translated into English on the cards. `Rodinny Cluster`
  remains a color key: `0` Martin, `1` Kladno, `2` Ostrava, `3` Liptov, and
  `4` Bratislava.
- Since the CSV has no paternal grandparents or maternal great-grandparents,
  the map shows labeled placeholders for those inferred ancestor couples
  instead of inventing names.
- The script lays out the tree in SVG, then uses `sips` to convert it to PNG.

Relationship IDs should identify one group across the CSV; IDs reused in
different locations are kept separate for drawing, but make a `Deti` reference
ambiguous and are reported as an error. Every location code must be one of
`0` through `4`.
# feriancovci
