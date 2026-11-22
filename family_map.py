#!/usr/bin/env python3
"""Render the family CSV as a role-aware family tree PNG on macOS."""

import argparse
import csv
import html
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


LOCATIONS = {
    "0": ("Martin", "#e7f0fa", "#4c78a8"),
    "1": ("Kladno", "#e8f3e5", "#5b8c5a"),
    "2": ("Ostrava", "#f9e9df", "#c56b36"),
    "3": ("Liptov", "#eee9f5", "#8064a2"),
    "4": ("Bratislava", "#fbf2d9", "#b58b23"),
}
REQUIRED_COLUMNS = (
    "Jmeno",
    "Role v rodine",
    "Rodinna priduzenost",
    "Rodinny Cluster",
    "Vztah",
    "Deti",
)
RelationshipKey = Tuple[str, str]
CARD_WIDTH = 156
CARD_HEIGHT = 80
CARD_GAP = 14
ROW_STEP = 150


@dataclass(frozen=True)
class Person:
    row_number: int
    name: str
    role: str
    side: str
    location: str
    relationship: str
    parents_relationship: str

    @property
    def node_id(self) -> str:
        return "person_{}".format(self.row_number)


@dataclass
class FamilyUnit:
    unit_id: str
    location: str
    members: List[Person]
    relationship_key: Optional[RelationshipKey]
    first_row: int
    generation: Optional[int] = None


def load_people(csv_path: Path) -> List[Person]:
    with csv_path.open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError("{} has no CSV header".format(csv_path))

        missing_columns = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing_columns:
            raise ValueError(
                "{} is missing required columns: {}".format(
                    csv_path, ", ".join(missing_columns)
                )
            )

        people = []
        for row_number, row in enumerate(reader, start=2):
            name = (row.get("Jmeno") or "").strip()
            location = (row.get("Rodinny Cluster") or "").strip()
            if not name:
                raise ValueError("CSV row {} has no name in Jmeno".format(row_number))
            if location not in LOCATIONS:
                raise ValueError(
                    "CSV row {} has unknown Rodinny Cluster {!r}; expected one of {}".format(
                        row_number, location, ", ".join(LOCATIONS)
                    )
                )

            people.append(
                Person(
                    row_number=row_number,
                    name=name,
                    role=(row.get("Role v rodine") or "").strip(),
                    side=(row.get("Rodinna priduzenost") or "").strip(),
                    location=location,
                    relationship=(row.get("Vztah") or "").strip(),
                    parents_relationship=(row.get("Deti") or "").strip(),
                )
            )

    if not people:
        raise ValueError("{} contains no people".format(csv_path))

    groups_by_id = defaultdict(list)
    for person in people:
        if person.relationship:
            key = (person.location, person.relationship)
            if key not in groups_by_id[person.relationship]:
                groups_by_id[person.relationship].append(key)

    for person in people:
        if not person.parents_relationship:
            continue
        matching_groups = groups_by_id.get(person.parents_relationship, [])
        if not matching_groups:
            raise ValueError(
                "CSV row {} references unknown parent relationship {!r} in Deti".format(
                    person.row_number, person.parents_relationship
                )
            )
        if len(matching_groups) > 1:
            locations = ", ".join(LOCATIONS[key[0]][0] for key in matching_groups)
            raise ValueError(
                "CSV row {} references ambiguous relationship {!r} in Deti "
                "(found in {}); make that relationship ID unique".format(
                    person.row_number, person.parents_relationship, locations
                )
            )

    return people


def wrap_text(text: str, max_characters: int) -> List[str]:
    words = text.split()
    if not words:
        return []

    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + len(word) + 1 <= max_characters:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def build_svg(people: List[Person]) -> str:
    translated_roles = {
        "Matka": "Mother",
        "Otec": "Father",
        "Bratr": "Brother",
        "Babicka": "Grandmother",
        "Dedecek": "Grandfather",
        "Teta": "Aunt",
        "Sestrenice": "Female cousin",
        "Bratranec": "Male cousin",
        "Brantranec": "Male cousin",
        "Stryc": "Uncle",
        "Manzelka bratrance": "Cousin's wife",
        "Dite": "Child",
        "Prateta": "Great-aunt",
    }

    relationship_groups: Dict[RelationshipKey, List[Person]] = {}
    for person in people:
        if person.relationship:
            key = (person.location, person.relationship)
            relationship_groups.setdefault(key, []).append(person)

    units: Dict[str, FamilyUnit] = {}
    relation_unit_ids = {}
    relation_keys_by_id = defaultdict(list)
    for index, (key, members) in enumerate(relationship_groups.items()):
        unit_id = "unit_{}".format(index)
        relation_unit_ids[key] = unit_id
        relation_keys_by_id[key[1]].append(key)
        units[unit_id] = FamilyUnit(
            unit_id=unit_id,
            location=key[0],
            members=members,
            relationship_key=key,
            first_row=min(person.row_number for person in members),
        )

    ungrouped_people = defaultdict(list)
    for person in people:
        if person.relationship:
            continue
        if person.parents_relationship:
            group_key = ("children", person.parents_relationship)
        else:
            group_key = ("person", str(person.row_number))
        ungrouped_people[group_key].append(person)

    for index, (key, members) in enumerate(ungrouped_people.items()):
        unit_id = "unit_{}".format(len(units) + index)
        units[unit_id] = FamilyUnit(
            unit_id=unit_id,
            location=members[0].location,
            members=members,
            relationship_key=None,
            first_row=min(person.row_number for person in members),
        )

    def unique_relation_unit(relation_id: str) -> str:
        keys = relation_keys_by_id.get(relation_id, [])
        if len(keys) != 1:
            raise ValueError(
                "relationship {!r} must identify exactly one family group".format(
                    relation_id
                )
            )
        return relation_unit_ids[keys[0]]

    parent_edges = []
    for person in people:
        if person.parents_relationship:
            parent_edges.append(
                (unique_relation_unit(person.parents_relationship), person.node_id)
            )

    side_for_unit = {}
    for unit in units.values():
        sides = {person.side for person in unit.members if person.side}
        side_for_unit[unit.unit_id] = next(iter(sides)) if len(sides) == 1 else ""

    def unit_roles(unit: FamilyUnit):
        return {person.role for person in unit.members}

    mother = next((person for person in people if person.role == "Matka"), None)
    father = next((person for person in people if person.role == "Otec"), None)
    if mother and father and mother.relationship and mother.relationship == father.relationship:
        root_unit_id = unique_relation_unit(mother.relationship)
        units[root_unit_id].generation = 0

    maternal_grandparent_units = [
        unit
        for unit in units.values()
        if {"Babicka", "Dedecek"} & unit_roles(unit)
        and side_for_unit[unit.unit_id] == "Od matky"
    ]
    for unit in maternal_grandparent_units:
        unit.generation = -1
        if mother:
            parent_edges.append((unit.unit_id, mother.node_id))

    great_aunt_units = [
        unit for unit in units.values() if "Prateta" in unit_roles(unit)
    ]
    for unit in great_aunt_units:
        unit.generation = -1

    anchors = {}
    if maternal_grandparent_units and great_aunt_units:
        maternal_ancestor_id = "anchor_maternal_ancestors"
        anchors[maternal_ancestor_id] = {
            "label": "Maternal great-grandparents\\n(not listed)",
            "generation": -2,
            "side": "Od matky",
        }
        for unit in maternal_grandparent_units + great_aunt_units:
            for person in unit.members:
                parent_edges.append((maternal_ancestor_id, person.node_id))

    paternal_anchor_id = None
    paternal_sibling_units = [
        unit
        for unit in units.values()
        if unit_roles(unit) & {"Teta", "Stryc"}
        and side_for_unit[unit.unit_id] == "Od otce"
        and not any(person.parents_relationship for person in unit.members)
    ]
    if father and paternal_sibling_units:
        paternal_anchor_id = "anchor_paternal_grandparents"
        anchors[paternal_anchor_id] = {
            "label": "Paternal grandparents\\n(not listed)",
            "generation": -1,
            "side": "Od otce",
        }
        parent_edges.append((paternal_anchor_id, father.node_id))
        for unit in paternal_sibling_units:
            unit.generation = 0
            for person in unit.members:
                parent_edges.append((paternal_anchor_id, person.node_id))

    for unit in units.values():
        if unit.generation is not None or unit.relationship_key is None:
            continue
        if any(person.parents_relationship for person in unit.members):
            continue
        if not (unit_roles(unit) & {"Bratranec", "Brantranec", "Sestrenice"}):
            continue
        matching_parents = [
            candidate
            for candidate in units.values()
            if candidate.first_row < unit.first_row
            and side_for_unit[candidate.unit_id] == side_for_unit[unit.unit_id]
            and unit_roles(candidate) & {"Teta", "Stryc"}
            and (
                side_for_unit[unit.unit_id] != "Od otce"
                or candidate.location == unit.location
            )
        ]
        if matching_parents:
            parent_unit = max(matching_parents, key=lambda candidate: candidate.first_row)
            for person in unit.members:
                if person.role in {"Bratranec", "Brantranec", "Sestrenice"}:
                    parent_edges.append((parent_unit.unit_id, person.node_id))
            parent_generation = (
                parent_unit.generation if parent_unit.generation is not None else 0
            )
            unit.generation = parent_generation + 1

    unit_by_person = {
        person.node_id: unit.unit_id
        for unit in units.values()
        for person in unit.members
    }
    parent_unit_ids = defaultdict(set)
    for parent_id, child_node_id in parent_edges:
        child_unit_id = unit_by_person.get(child_node_id)
        if child_unit_id and child_unit_id != parent_id:
            parent_unit_ids[child_unit_id].add(parent_id)

    def generation(unit_id: str, visiting=()):
        unit = units[unit_id]
        if unit.generation is not None:
            return unit.generation
        if unit_id in visiting:
            raise ValueError("family relationships contain a cycle")
        parent_generations = []
        for parent_id in parent_unit_ids[unit_id]:
            if parent_id in units:
                parent_generations.append(generation(parent_id, visiting + (unit_id,)))
            elif parent_id in anchors:
                parent_generations.append(anchors[parent_id]["generation"])
        unit.generation = max(parent_generations) + 1 if parent_generations else 0
        return unit.generation

    for unit_id in units:
        generation(unit_id)

    generation_values = [unit.generation for unit in units.values()]
    generation_values.extend(anchor["generation"] for anchor in anchors.values())
    min_generation = min(generation_values)
    max_generation = max(generation_values)
    generation_y = {
        value: 128 + (value - min_generation) * ROW_STEP
        for value in range(min_generation, max_generation + 1)
    }

    def side_rank(unit: FamilyUnit):
        side = side_for_unit[unit.unit_id]
        return {"Od matky": 0, "": 1, "Od otce": 2}.get(side, 1)

    units_by_generation = defaultdict(list)
    for unit in units.values():
        units_by_generation[unit.generation].append(unit)
    row_widths = {}
    for generation_number, row_units in units_by_generation.items():
        widths = [
            len(unit.members) * CARD_WIDTH
            + max(0, len(unit.members) - 1) * CARD_GAP
            for unit in row_units
        ]
        row_widths[generation_number] = sum(widths) + max(0, len(widths) - 1) * 42
    image_width = max(max(row_widths.values()) + 72, 900)
    anchor_positions = {
        anchor_id: (
            image_width * (0.25 if anchor["side"] == "Od matky" else 0.75),
            generation_y[anchor["generation"]],
        )
        for anchor_id, anchor in anchors.items()
    }
    person_positions = {}
    unit_positions = {}
    for generation_number in sorted(units_by_generation):
        row_units = units_by_generation[generation_number]

        def parent_center(unit):
            parent_centers = []
            for parent_id in parent_unit_ids[unit.unit_id]:
                if parent_id in unit_positions:
                    parent_centers.append(unit_positions[parent_id][0])
                elif parent_id in anchor_positions:
                    parent_centers.append(anchor_positions[parent_id][0])
            return (
                sum(parent_centers) / len(parent_centers)
                if parent_centers
                else None
            )

        row_units.sort(
            key=lambda unit: (
                parent_center(unit)
                if parent_center(unit) is not None
                else image_width * side_rank(unit) / 2,
                unit.first_row,
            )
        )
        row_width = row_widths[generation_number]
        parent_centers = [
            parent_center(unit)
            for unit in row_units
            if parent_center(unit) is not None
        ]
        target_center = (
            sum(parent_centers) / len(parent_centers)
            if parent_centers
            else image_width / 2
        )
        cursor_x = max(
            36,
            min(image_width - row_width - 36, target_center - row_width / 2),
        )
        for unit in row_units:
            group_width = (
                len(unit.members) * CARD_WIDTH
                + max(0, len(unit.members) - 1) * CARD_GAP
            )
            y = generation_y[generation_number]
            for member_index, person in enumerate(unit.members):
                x = cursor_x + member_index * (CARD_WIDTH + CARD_GAP)
                person_positions[person.node_id] = (x, y)
            hub_x = cursor_x + group_width / 2
            unit_positions[unit.unit_id] = (hub_x, y + CARD_HEIGHT + 14)
            cursor_x += group_width + 42

    for anchor_id, anchor in anchors.items():
        related_units = set()
        related_people = set()
        for parent_id, child_node_id in parent_edges:
            if parent_id != anchor_id:
                continue
            child_unit_id = unit_by_person.get(child_node_id)
            if child_unit_id:
                related_units.add(child_unit_id)
                related_people.add(child_node_id)
        xs = []
        for unit_id in related_units:
            xs.append(unit_positions[unit_id][0])
        for person_id in related_people:
            x, _ = person_positions[person_id]
            xs.append(x + CARD_WIDTH / 2)
        if xs:
            anchor_positions[anchor_id] = (
                sum(xs) / len(xs),
                generation_y[anchor["generation"]],
            )

    image_height = generation_y[max_generation] + CARD_HEIGHT + 54

    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" viewBox="0 0 {} {}">'.format(
            image_width, image_height, image_width, image_height
        ),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="{}" y="34" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
        'font-size="22" font-weight="bold" fill="#202a35">Family tree</text>'.format(
            image_width / 2
        ),
    ]

    legend_x = max(36, image_width / 2 - 280)
    for index, (_, (name, _, border)) in enumerate(LOCATIONS.items()):
        x = legend_x + index * 120
        svg.extend(
            [
                '<circle cx="{}" cy="68" r="6" fill="{}"/>'.format(x, border),
                '<text x="{}" y="72" font-family="Arial, Helvetica, sans-serif" '
                'font-size="12" fill="#46515c">{}</text>'.format(
                    x + 12, html.escape(name)
                ),
            ]
        )

    for unit in units.values():
        if unit.relationship_key is None:
            continue
        hub_x, hub_y = unit_positions[unit.unit_id]
        border = LOCATIONS[unit.location][2]
        for person in unit.members:
            x, y = person_positions[person.node_id]
            svg.append(
                '<path d="M {} {} L {} {}" fill="none" stroke="{}" stroke-width="1.7"/>'.format(
                    x + CARD_WIDTH / 2,
                    y + CARD_HEIGHT,
                    hub_x,
                    hub_y,
                    border,
                )
            )

    for parent_id, child_node_id in parent_edges:
        if parent_id in anchors:
            start_x, start_y = anchor_positions[parent_id]
            start_y += 36
        else:
            start_x, start_y = unit_positions[parent_id]
        target_x, target_y = person_positions[child_node_id]
        middle_y = (start_y + target_y) / 2
        svg.append(
            '<path d="M {} {} C {} {}, {} {}, {} {}" fill="none" stroke="#65717c" '
            'stroke-width="1.6" stroke-linecap="round"/>'.format(
                start_x,
                start_y,
                start_x,
                middle_y,
                target_x + CARD_WIDTH / 2,
                middle_y,
                target_x + CARD_WIDTH / 2,
                target_y,
            )
        )

    for anchor_id, anchor in anchors.items():
        x, y = anchor_positions[anchor_id]
        label = anchor["label"].split("\\n")
        svg.append(
            '<rect x="{}" y="{}" width="220" height="72" rx="10" fill="#f3f5f7" '
            'stroke="#7a8793" stroke-width="1.5" stroke-dasharray="5 4"/>'.format(
                x - 110, y
            )
        )
        for line_index, line in enumerate(label):
            svg.append(
                '<text x="{}" y="{}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
                'font-size="12" fill="#46515c">{}</text>'.format(
                    x, y + 30 + line_index * 17, html.escape(line)
                )
            )

    for person in people:
        x, y = person_positions[person.node_id]
        border = LOCATIONS[person.location][2]
        svg.append(
            '<rect x="{}" y="{}" width="{}" height="{}" rx="9" fill="#ffffff" '
            'stroke="{}" stroke-width="1.7"/>'.format(
                x, y, CARD_WIDTH, CARD_HEIGHT, border
            )
        )
        label_lines = wrap_text(person.name, 20)
        role = translated_roles.get(person.role, person.role)
        side = {
            "Od matky": "Mother's side",
            "Od otce": "Father's side",
        }.get(person.side, person.side)
        details = " / ".join(
            part for part in (role, side) if part
        )
        detail_lines = wrap_text(details, 23)
        label_lines.extend(detail_lines)
        text_height = 15
        start_y = y + (CARD_HEIGHT - (len(label_lines) - 1) * text_height) / 2 + 4
        for line_index, line in enumerate(label_lines):
            font_size = 13 if line_index < len(label_lines) - len(detail_lines) else 11
            svg.append(
                '<text x="{}" y="{}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
                'font-size="{}" fill="#202a35">{}</text>'.format(
                    x + CARD_WIDTH / 2,
                    start_y + line_index * text_height,
                    font_size,
                    html.escape(line),
                )
            )

    for unit in units.values():
        if unit.relationship_key is None:
            continue
        hub_x, hub_y = unit_positions[unit.unit_id]
        border = LOCATIONS[unit.location][2]
        svg.append(
            '<circle cx="{}" cy="{}" r="4" fill="{}"/>'.format(hub_x, hub_y, border)
        )

    svg.append("</svg>")
    return "\n".join(svg)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Draw a location-grouped family relationship map as a PNG."
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        type=Path,
        default=Path("feriancovci.csv"),
        help="input CSV (default: feriancovci.csv)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("family_map.png"),
        help="output PNG (default: family_map.png)",
    )
    args = parser.parse_args()

    try:
        people = load_people(args.csv_file)
        svg = build_svg(people)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="family-map-") as temp_dir:
            svg_path = Path(temp_dir) / "family_map.svg"
            svg_path.write_text(svg, encoding="utf-8")
            result = subprocess.run(
                [
                    "sips",
                    "-s",
                    "format",
                    "png",
                    str(svg_path),
                    "--out",
                    str(args.output),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
    except (OSError, ValueError) as error:
        parser.error(str(error))

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        parser.error(
            "macOS 'sips' could not convert the map to PNG{}".format(
                ": {}".format(detail) if detail else ""
            )
        )

    print("Wrote {}".format(args.output))


if __name__ == "__main__":
    main()
