"""Parser for AncestryDNA raw data files.

Supports both current and older AncestryDNA tab-separated formats.
Returns a dict mapping rsid → (allele1, allele2).
"""

import io
import re
from typing import Dict, Tuple

# Columns expected in AncestryDNA files (current format)
EXPECTED_COLUMNS = {"rsid", "chromosome", "position", "allele1", "allele2"}

# Older format may use different column names
ALT_COLUMN_MAP = {
    "rs_id": "rsid",
    "rs id": "rsid",
    "snp": "rsid",
    "marker": "rsid",
    "chr": "chromosome",
    "chrom": "chromosome",
    "pos": "position",
    "bp": "position",
    "allele 1": "allele1",
    "allele 2": "allele2",
    "genotype": "genotype",  # some formats pack both alleles in one column
}

# No-call values to skip
NO_CALL_VALUES = {"0", "--", "-", "00", "II", "DD", "DI", ""}

VALID_ALLELES = set("ACGTDI")

RSID_PATTERN = re.compile(r"^rs\d+$", re.IGNORECASE)


def parse_ancestry_file(file_obj: io.StringIO) -> Dict[str, Tuple[str, str]]:
    """Parse an AncestryDNA raw data file.

    Args:
        file_obj: A file-like object (io.StringIO) containing AncestryDNA data.

    Returns:
        Dict mapping rsid (str) → (allele1, allele2) as uppercase single chars.

    Raises:
        ValueError: If the file format is unrecognizable or contains no valid data.
    """
    genotypes: Dict[str, Tuple[str, str]] = {}
    header_found = False
    col_indices: Dict[str, int] = {}
    line_num = 0
    error_lines = 0
    max_errors_to_track = 10
    error_examples = []

    for raw_line in file_obj:
        line_num += 1
        line = raw_line.strip()

        # Skip empty lines and comment lines
        if not line or line.startswith("#"):
            continue

        # Try to detect header row
        if not header_found:
            col_indices = _detect_header(line)
            if col_indices:
                header_found = True
                continue
            # If first non-comment line looks like data (starts with rs), assume default columns
            if line.lower().startswith("rs"):
                col_indices = _default_column_indices()
                header_found = True
                # Fall through to parse this line as data
            else:
                # Try treating it as header with different delimiter
                col_indices = _detect_header(line)
                if col_indices:
                    header_found = True
                    continue
                else:
                    raise ValueError(
                        f"Could not detect file header. First non-comment line "
                        f"(line {line_num}): {line[:100]}"
                    )

        # Parse data line
        fields = line.split("\t")
        if len(fields) < 2:
            # Try comma-separated as fallback
            fields = line.split(",")

        try:
            result = _parse_data_line(fields, col_indices)
            if result:
                rsid, allele1, allele2 = result
                genotypes[rsid] = (allele1, allele2)
        except (IndexError, KeyError):
            error_lines += 1
            if len(error_examples) < max_errors_to_track:
                error_examples.append(f"  Line {line_num}: {line[:80]}")

    if not header_found:
        raise ValueError(
            "No valid data found in file. The file appears to be empty or "
            "contains only comments."
        )

    if not genotypes:
        msg = "No valid genotypes found in file."
        if error_examples:
            msg += " Sample unparseable lines:\n" + "\n".join(error_examples)
        raise ValueError(msg)

    if error_lines > 0 and error_lines > len(genotypes):
        raise ValueError(
            f"Too many parse errors ({error_lines}) vs valid entries "
            f"({len(genotypes)}). File may be in an unsupported format."
        )

    return genotypes


def _detect_header(line: str) -> Dict[str, int]:
    """Detect header row and return column name → index mapping.

    Returns empty dict if line doesn't look like a header.
    """
    # Try tab-separated first, then comma
    for delimiter in ("\t", ","):
        parts = [p.strip().lower() for p in line.split(delimiter)]
        if len(parts) < 3:
            continue

        col_map = {}
        for idx, col in enumerate(parts):
            # Check direct match
            if col in EXPECTED_COLUMNS:
                col_map[col] = idx
            # Check alternate names
            elif col in ALT_COLUMN_MAP:
                normalized = ALT_COLUMN_MAP[col]
                col_map[normalized] = idx

        # Need at minimum rsid + either (allele1,allele2) or genotype
        has_rsid = "rsid" in col_map
        has_alleles = "allele1" in col_map and "allele2" in col_map
        has_genotype = "genotype" in col_map

        if has_rsid and (has_alleles or has_genotype):
            return col_map

    return {}


def _default_column_indices() -> Dict[str, int]:
    """Return default AncestryDNA column indices (no header row)."""
    return {
        "rsid": 0,
        "chromosome": 1,
        "position": 2,
        "allele1": 3,
        "allele2": 4,
    }


def _parse_data_line(
    fields: list, col_indices: Dict[str, int]
) -> Tuple[str, str, str] | None:
    """Parse a single data line into (rsid, allele1, allele2) or None to skip."""
    rsid_idx = col_indices.get("rsid", 0)
    if rsid_idx >= len(fields):
        return None

    rsid = fields[rsid_idx].strip()

    # Validate rsid format
    if not RSID_PATTERN.match(rsid):
        return None

    # Get alleles - either from two columns or from a combined genotype column
    if "genotype" in col_indices:
        geno_idx = col_indices["genotype"]
        if geno_idx >= len(fields):
            return None
        genotype = fields[geno_idx].strip().upper()
        if len(genotype) == 2:
            allele1, allele2 = genotype[0], genotype[1]
        elif len(genotype) == 1:
            allele1, allele2 = genotype, genotype
        else:
            return None
    else:
        a1_idx = col_indices.get("allele1", 3)
        a2_idx = col_indices.get("allele2", 4)
        if max(a1_idx, a2_idx) >= len(fields):
            return None
        allele1 = fields[a1_idx].strip().upper()
        allele2 = fields[a2_idx].strip().upper()

    # Skip no-call values
    if allele1 in NO_CALL_VALUES or allele2 in NO_CALL_VALUES:
        return None

    # Validate alleles are single valid nucleotides (or indel markers)
    if not (len(allele1) == 1 and allele1 in VALID_ALLELES):
        return None
    if not (len(allele2) == 1 and allele2 in VALID_ALLELES):
        return None

    return (rsid.lower(), allele1, allele2)
