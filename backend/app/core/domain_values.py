"""Centralized reference values for extensible free-text fields.

`Incident.type` and `Resource.type` are plain strings in the database and
schemas — deliberately NOT enums or CHECK constraints — so new incident or
resource types can be introduced by ingestion/AI without a migration or code
change anywhere else.

The lists below exist only for OpenAPI documentation/examples and seed data.
They are not enforced. If you need to add a new type for the demo, add it
here; do not add `if type == "..."` branches elsewhere in the codebase.
"""

KNOWN_INCIDENT_TYPES = [
    "flood",
    "medical",
    "fire",
    "structural_collapse",
    "other",
]

KNOWN_RESOURCE_TYPES = [
    "ambulance",
    "rescue_unit",
    "volunteer",
    "shelter",
    "hospital",
]

# Maps a resource type to the prefix used for its human-readable ID
# (e.g. "ambulance" -> "AMB-01"). Used only by app.services.id_generator.
# An unrecognized type still gets a valid, stable prefix derived from its
# own name (see id_generator.resource_prefix_for_type) — this map is a
# cosmetic override for the known demo types, not a hard requirement.
RESOURCE_TYPE_PREFIXES = {
    "ambulance": "AMB",
    "rescue_unit": "RESCUE",
    "volunteer": "VOL",
    "shelter": "SHELTER",
    "hospital": "HOSP",
}
