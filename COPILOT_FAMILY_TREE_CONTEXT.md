# Family-tree project context for GitHub Copilot

Use this document when updating the family data, generator, or family-tree
image. It records both the CSV conventions and the family-relationship
instructions supplied by the user. Do not rely on column names alone when
interpreting the family relationships.

## What this project does

This project reads `feriancovci.csv` and uses `family_map.py` to generate
`family_map.png`. The intended result is **one connected family tree**, laid
out by generation. It is not a set of separate trees by location or by
parental side.

The family-side column describes how a relative connects to the fiancé's
parents:

- `Od matky` means the relative is on the mother's side.
- `Od otce` means the relative is on the father's side.

Use these as the maternal and paternal branches of the same tree. Translate
and interpret `Role v rodine` to determine each person's family role and
generation. The location column is a secondary visual cue, not the family
tree's organizing structure.

## Input columns

The CSV header is expected to contain these exact columns:

| Column | Meaning |
|---|---|
| `Jmeno` | Person's name. |
| `Role v rodine` | Their family role, written in Slovak/Czech without diacritics in the current data. Use it to understand their relationship and likely generation. |
| `Rodinna priduzenost` | Which of the fiancé's parents' sides the connection comes from: `Od matky` (mother's side) or `Od otce` (father's side). This is branch information in the one family tree. |
| `Rodinny Cluster` | Their location code: `0` Martin, `1` Kladno, `2` Ostrava, `3` Liptov, `4` Bratislava. Use location for color/legend or other secondary grouping, not as a separate family tree. |
| `Vztah` | An ID for a direct relationship group, such as a husband-and-wife pair. People in the same relationship group are connected together. |
| `Deti` | The `Vztah` ID of the relationship from which this person's child came. Connect the referenced parents/relationship group to this child. It is commonly blank for a person who is a partner in a group. |

Blank values are meaningful: for example, a person can have no `Vztah` of
their own but still have `Deti` filled in to show their parents' relationship.
Do not treat `Vztah` and `Deti` as names or as interchangeable IDs.

## Role translation reference

Use these translations for the values present in the current CSV:

| Source value | English meaning |
|---|---|
| `Matka` | Mother |
| `Otec` | Father |
| `Bratr` | Brother |
| `Babicka` | Grandmother |
| `Dedecek` | Grandfather |
| `Teta` | Aunt |
| `Stryc` | Uncle |
| `Sestrenice` | Female cousin |
| `Bratranec` | Male cousin |
| `Brantranec` | Male cousin (spelling variant in the data) |
| `Manzelka bratrance` | Cousin's wife |
| `Dite` | Child |
| `Prateta` | Great-aunt |

When new role values appear, translate them using their family meaning and
add them to the generator's role translation table. If the meaning is
unclear, ask the user instead of silently assigning a relationship.

## Data interpretation and edge cases

- The relationship structure and role labels are authoritative; location is
  not a substitute for parentage.
- People who share a `Vztah` ID in the same location are grouped as one direct
  relationship. `Deti` points to that relationship ID, not to an individual
  by name.
- Keep each relationship ID unique across the full CSV. Reusing an ID in
  another location makes a `Deti` reference ambiguous. The generator should
  report such ambiguity rather than guess.
- The current generator uses explicit `Deti` links when provided. Some cousin
  rows do not have `Deti`; for those it infers a parent link from their role,
  side, and row order, selecting the closest preceding aunt/uncle family
  group on the same side (and, on the father's side, in the same location).
  This is a fallback inference, not a fact explicitly encoded in those rows.
  Review it if new data makes the intended parents unclear.
- The current data does not name every ancestor. The generator shows labeled
  placeholders for the paternal grandparents and maternal great-grandparents
  where the tree implies those generations. Placeholders are not real people:
  do not invent names or details for them.
- The CSV identifies Martina as `Matka` and Miroslav as `Otec`, and lists
  Adrian and Matej as their `Bratr` children. It does **not** identify which
  child is the fiancé; do not infer or label that person's identity.
- The renderer should preserve names as written in the CSV. Do not correct,
  translate, or normalize family names without asking.

## Current renderer and operation

The generator is `family_map.py`. It requires Python 3 and macOS's built-in
`sips` utility, uses no third-party Python packages, and writes PNG output.
From the project directory, regenerate the default image with:

```sh
python3 family_map.py
```

Equivalent explicit command:

```sh
python3 family_map.py feriancovci.csv --output family_map.png
```

See `README.md` for the short user-facing run instructions. When changing the
CSV schema or generator behavior, update that README and this context document
so future runs remain understandable and repeatable.

## Guidance for future Copilot work

When new family rows are added:

1. Read the updated CSV and this document before changing the layout.
2. Keep the output as one connected, generation-based tree, with maternal
   and paternal sides as branches and locations as secondary visual cues.
3. Use explicit `Vztah`/`Deti` links first; only use role-based inference
   where parent links are absent, and make any such inference visible in the
   implementation/documentation.
4. Validate that every person is present, relationship IDs resolve
   unambiguously, the PNG can be regenerated, and the image remains legible.
5. Do not fabricate missing people, names, marriages, or parentage. Ask the
   user when the data supports multiple reasonable family relationships.
