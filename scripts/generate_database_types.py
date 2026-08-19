"""Generate the committed TypeScript database contract from SQL migrations.

This offline generator intentionally covers the SQL shapes used by this repository.
Production activation should additionally compare its output with
`supabase gen types typescript` against a freshly rebuilt local database.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
OUTPUT_PATH = ROOT / "web" / "lib" / "generated" / "database.types.ts"


@dataclass(frozen=True)
class Column:
    name: str
    ts_type: str
    nullable: bool
    has_default: bool


@dataclass(frozen=True)
class Relationship:
    name: str
    columns: tuple[str, ...]
    referenced_relation: str
    referenced_columns: tuple[str, ...]
    is_one_to_one: bool


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    relationships: tuple[Relationship, ...]


@dataclass(frozen=True)
class FunctionArgument:
    name: str
    ts_type: str
    optional: bool


@dataclass(frozen=True)
class Function:
    name: str
    arguments: tuple[FunctionArgument, ...]
    return_type: str


TYPE_MAP = {
    "uuid": "string",
    "text": "string",
    "boolean": "boolean",
    "smallint": "number",
    "integer": "number",
    "bigint": "number",
    "numeric": "number",
    "date": "string",
    "timestamptz": "string",
    "jsonb": "Json",
    "uuid[]": "string[]",
    "text[]": "string[]",
    "void": "undefined",
}


def read_migrations() -> tuple[str, str]:
    paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not paths:
        raise SystemExit("No SQL migrations found")
    parts = [path.read_text(encoding="utf-8") for path in paths]
    joined = "\n".join(parts)
    digest = hashlib.sha256(b"".join(path.read_bytes() for path in paths)).hexdigest()
    return joined, digest


def find_matching_parenthesis(text: str, open_index: int) -> int:
    depth = 0
    index = open_index
    in_single_quote = False
    in_double_quote = False
    dollar_tag: str | None = None
    in_line_comment = False
    in_block_comment = False

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
            else:
                index += 1
            continue
        if dollar_tag is not None:
            if text.startswith(dollar_tag, index):
                index += len(dollar_tag)
                dollar_tag = None
            else:
                index += 1
            continue
        if in_single_quote:
            if char == "'" and next_char == "'":
                index += 2
            elif char == "'":
                in_single_quote = False
                index += 1
            else:
                index += 1
            continue
        if in_double_quote:
            if char == '"' and next_char == '"':
                index += 2
            elif char == '"':
                in_double_quote = False
                index += 1
            else:
                index += 1
            continue

        if char == "-" and next_char == "-":
            in_line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue
        if char == "'":
            in_single_quote = True
            index += 1
            continue
        if char == '"':
            in_double_quote = True
            index += 1
            continue
        if char == "$":
            tag_match = re.match(r"\$[A-Za-z0-9_]*\$", text[index:])
            if tag_match:
                dollar_tag = tag_match.group(0)
                index += len(dollar_tag)
                continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1

    raise ValueError("Unbalanced SQL parentheses")


def split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    in_single_quote = False
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_single_quote:
            if char == "'" and next_char == "'":
                index += 2
                continue
            if char == "'":
                in_single_quote = False
            index += 1
            continue
        if char == "'":
            in_single_quote = True
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
        index += 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def normalize_sql_type(raw_type: str) -> str:
    normalized = raw_type.strip().lower()
    normalized = re.sub(r"numeric\s*\([^)]*\)", "numeric", normalized)
    if normalized not in TYPE_MAP:
        raise ValueError(f"Unsupported SQL type in offline generator: {raw_type}")
    return TYPE_MAP[normalized]


def extract_sql_type(definition: str) -> tuple[str, str]:
    match = re.match(
        r"(uuid\[\]|text\[\]|uuid|text|boolean|smallint|integer|bigint|numeric\s*\([^)]*\)|numeric|date|timestamptz|jsonb)(?=\s|$)(.*)",
        definition,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"Cannot parse column definition: {definition}")
    return match.group(1), match.group(2)


def parse_tables(sql: str) -> tuple[Table, ...]:
    tables: list[Table] = []
    pattern = re.compile(
        r"create\s+table\s+public\.([a-z_][a-z0-9_]*)\s*\(", re.IGNORECASE
    )
    for match in pattern.finditer(sql):
        table_name = match.group(1)
        open_index = match.end() - 1
        close_index = find_matching_parenthesis(sql, open_index)
        items = split_top_level(sql[open_index + 1 : close_index])

        primary_columns = set()
        unique_column_sets = set()
        for item in items:
            primary_match = re.search(
                r"primary\s+key\s*\(([^)]+)\)", item, re.IGNORECASE
            )
            if primary_match:
                columns = tuple(
                    part.strip().strip('"')
                    for part in primary_match.group(1).split(",")
                )
                primary_columns.update(columns)
                unique_column_sets.add(columns)
            unique_match = re.search(r"unique\s*\(([^)]+)\)", item, re.IGNORECASE)
            if unique_match:
                unique_column_sets.add(
                    tuple(
                        part.strip().strip('"')
                        for part in unique_match.group(1).split(",")
                    )
                )

        columns: list[Column] = []
        column_definitions = {}
        for item in items:
            if re.match(
                r"^(constraint|primary\s+key|unique|check|foreign\s+key|exclude)\b",
                item,
                re.IGNORECASE,
            ):
                continue
            column_match = re.match(
                r'^"?([a-z_][a-z0-9_]*)"?\s+(.+)$', item, re.IGNORECASE | re.DOTALL
            )
            if not column_match:
                raise ValueError(f"Cannot parse table item in {table_name}: {item}")
            column_name = column_match.group(1)
            definition = column_match.group(2).strip()
            raw_type, remainder = extract_sql_type(definition)
            inline_primary = bool(
                re.search(r"\bprimary\s+key\b", remainder, re.IGNORECASE)
            )
            inline_unique = bool(re.search(r"\bunique\b", remainder, re.IGNORECASE))
            if inline_primary or inline_unique:
                unique_column_sets.add((column_name,))
            nullable = not (
                inline_primary
                or column_name in primary_columns
                or bool(re.search(r"\bnot\s+null\b", remainder, re.IGNORECASE))
            )
            has_default = bool(
                re.search(
                    r"\bdefault\b|\bgenerated\s+always\b", remainder, re.IGNORECASE
                )
            )
            columns.append(
                Column(
                    name=column_name,
                    ts_type=normalize_sql_type(raw_type),
                    nullable=nullable,
                    has_default=has_default,
                )
            )
            column_definitions[column_name] = definition

        relationships: list[Relationship] = []
        for item in items:
            foreign_match = re.search(
                r"(?:constraint\s+([a-z_][a-z0-9_]*)\s+)?foreign\s+key\s*\(([^)]+)\)\s*references\s+public\.([a-z_][a-z0-9_]*)\s*\(([^)]+)\)",
                item,
                re.IGNORECASE | re.DOTALL,
            )
            if not foreign_match:
                continue
            local_columns = tuple(
                part.strip().strip('"') for part in foreign_match.group(2).split(",")
            )
            referenced_columns = tuple(
                part.strip().strip('"') for part in foreign_match.group(4).split(",")
            )
            relationships.append(
                Relationship(
                    name=foreign_match.group(1)
                    or f"{table_name}_{'_'.join(local_columns)}_fkey",
                    columns=local_columns,
                    referenced_relation=foreign_match.group(3),
                    referenced_columns=referenced_columns,
                    is_one_to_one=local_columns in unique_column_sets,
                )
            )

        for column_name, definition in column_definitions.items():
            reference_match = re.search(
                r"references\s+public\.([a-z_][a-z0-9_]*)\s*\(([^)]+)\)",
                definition,
                re.IGNORECASE,
            )
            if reference_match:
                relationships.append(
                    Relationship(
                        name=f"{table_name}_{column_name}_fkey",
                        columns=(column_name,),
                        referenced_relation=reference_match.group(1),
                        referenced_columns=tuple(
                            part.strip().strip('"')
                            for part in reference_match.group(2).split(",")
                        ),
                        is_one_to_one=(column_name,) in unique_column_sets,
                    )
                )

        tables.append(Table(table_name, tuple(columns), tuple(relationships)))

    alter_relationship_pattern = re.compile(
        r"alter\s+table\s+public\.([a-z_][a-z0-9_]*)\s+"
        r"add\s+constraint\s+([a-z_][a-z0-9_]*)\s+"
        r"foreign\s+key\s*\(([^)]+)\)\s*"
        r"references\s+public\.([a-z_][a-z0-9_]*)\s*\(([^)]+)\)",
        re.IGNORECASE | re.DOTALL,
    )
    extra_relationships = {}
    for relationship_match in alter_relationship_pattern.finditer(sql):
        table_name = relationship_match.group(1)
        extra_relationships.setdefault(table_name, []).append(
            Relationship(
                name=relationship_match.group(2),
                columns=tuple(
                    part.strip().strip('"')
                    for part in relationship_match.group(3).split(",")
                ),
                referenced_relation=relationship_match.group(4),
                referenced_columns=tuple(
                    part.strip().strip('"')
                    for part in relationship_match.group(5).split(",")
                ),
                is_one_to_one=False,
            )
        )

    tables_by_name = {
        table.name: Table(
            table.name,
            table.columns,
            table.relationships + tuple(extra_relationships.get(table.name, ())),
        )
        for table in tables
    }

    alter_table_pattern = re.compile(
        r"alter\s+table\s+public\.([a-z_][a-z0-9_]*)\s+(.+?);",
        re.IGNORECASE | re.DOTALL,
    )
    for alter_match in alter_table_pattern.finditer(sql):
        table_name = alter_match.group(1)
        table = tables_by_name.get(table_name)
        if table is None:
            continue

        columns = list(table.columns)
        relationships = list(table.relationships)
        for clause in split_top_level(alter_match.group(2)):
            add_column_match = re.match(
                r"add\s+column\s+\"?([a-z_][a-z0-9_]*)\"?\s+(.+)$",
                clause,
                re.IGNORECASE | re.DOTALL,
            )
            if add_column_match:
                column_name = add_column_match.group(1)
                definition = add_column_match.group(2).strip()
                if any(column.name == column_name for column in columns):
                    raise ValueError(
                        f"Duplicate added column in {table_name}: {column_name}"
                    )
                raw_type, remainder = extract_sql_type(definition)
                column = Column(
                    name=column_name,
                    ts_type=normalize_sql_type(raw_type),
                    nullable=not bool(
                        re.search(r"\bnot\s+null\b", remainder, re.IGNORECASE)
                    ),
                    has_default=bool(
                        re.search(
                            r"\bdefault\b|\bgenerated\s+always\b",
                            remainder,
                            re.IGNORECASE,
                        )
                    ),
                )
                columns.append(column)

                reference_match = re.search(
                    r"references\s+public\.([a-z_][a-z0-9_]*)\s*\(([^)]+)\)",
                    definition,
                    re.IGNORECASE,
                )
                if reference_match:
                    relationships.append(
                        Relationship(
                            name=f"{table_name}_{column_name}_fkey",
                            columns=(column_name,),
                            referenced_relation=reference_match.group(1),
                            referenced_columns=tuple(
                                part.strip().strip('"')
                                for part in reference_match.group(2).split(",")
                            ),
                            is_one_to_one=False,
                        )
                    )
                continue

            alter_null_match = re.match(
                r"alter\s+column\s+\"?([a-z_][a-z0-9_]*)\"?\s+(set|drop)\s+not\s+null$",
                clause.strip(),
                re.IGNORECASE,
            )
            if alter_null_match:
                column_name = alter_null_match.group(1)
                nullable = alter_null_match.group(2).lower() == "drop"
                for index, column in enumerate(columns):
                    if column.name == column_name:
                        columns[index] = Column(
                            name=column.name,
                            ts_type=column.ts_type,
                            nullable=nullable,
                            has_default=column.has_default,
                        )
                        break
                else:
                    raise ValueError(
                        f"Cannot alter missing column in {table_name}: {column_name}"
                    )

        tables_by_name[table_name] = Table(
            table.name, tuple(columns), tuple(relationships)
        )

    return tuple(tables_by_name[table.name] for table in tables)


def parse_function_arguments(raw_arguments: str) -> tuple[FunctionArgument, ...]:
    if not raw_arguments.strip():
        return ()
    parsed: list[FunctionArgument] = []
    for item in split_top_level(raw_arguments):
        match = re.match(r"([a-z_][a-z0-9_]*)\s+(.+)$", item, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ValueError(f"Cannot parse function argument: {item}")
        name = match.group(1)
        definition = match.group(2).strip()
        optional = bool(re.search(r"\bdefault\b", definition, re.IGNORECASE))
        nullable = bool(re.search(r"\bdefault\s+null\b", definition, re.IGNORECASE))
        raw_type = re.split(
            r"\s+default\s+", definition, maxsplit=1, flags=re.IGNORECASE
        )[0].strip()
        ts_type = normalize_sql_type(raw_type)
        if nullable:
            ts_type = f"{ts_type} | null"
        parsed.append(FunctionArgument(name, ts_type, optional))
    return tuple(parsed)


def parse_functions(sql: str) -> tuple[Function, ...]:
    functions: list[Function] = []
    pattern = re.compile(
        r"create\s+or\s+replace\s+function\s+public\.([a-z_][a-z0-9_]*)\s*\(",
        re.IGNORECASE,
    )
    for match in pattern.finditer(sql):
        name = match.group(1)
        open_index = match.end() - 1
        close_index = find_matching_parenthesis(sql, open_index)
        header_tail = sql[close_index + 1 : close_index + 300]
        returns_match = re.search(
            r"\breturns\s+(uuid|jsonb|void)\b", header_tail, re.IGNORECASE
        )
        if not returns_match:
            raise ValueError(f"Cannot parse return type for public function {name}")
        functions.append(
            Function(
                name=name,
                arguments=parse_function_arguments(sql[open_index + 1 : close_index]),
                return_type=normalize_sql_type(returns_match.group(1)),
            )
        )
    latest_by_name: dict[str, Function] = {}
    for function in functions:
        previous = latest_by_name.get(function.name)
        if previous is not None and tuple(
            argument.ts_type for argument in previous.arguments
        ) != tuple(argument.ts_type for argument in function.arguments):
            raise ValueError(
                f"Overloaded public functions are unsupported: {function.name}"
            )
        latest_by_name[function.name] = function
    return tuple(latest_by_name.values())


def quote_ts_type(column: Column) -> str:
    return f"{column.ts_type} | null" if column.nullable else column.ts_type


def render_property(name: str, value_type: str, optional: bool, indent: int) -> str:
    marker = "?" if optional else ""
    return f"{' ' * indent}{name}{marker}: {value_type}"


def render_tuple(values: Sequence[str]) -> str:
    return "[" + ", ".join(f'"{value}"' for value in values) + "]"


def render_types(
    tables: Iterable[Table], functions: Iterable[Function], schema_hash: str
) -> str:
    lines = [
        "// Generated by scripts/generate_database_types.py; do not edit by hand.",
        f"// Migration SHA-256: {schema_hash}",
        "",
        "export type Json =",
        "  | string",
        "  | number",
        "  | boolean",
        "  | null",
        "  | { [key: string]: Json | undefined }",
        "  | Json[]",
        "",
        "export type Database = {",
        "  public: {",
        "    Tables: {",
    ]
    for table in tables:
        lines.extend([f"      {table.name}: {{", "        Row: {"])
        for column in table.columns:
            lines.append(render_property(column.name, quote_ts_type(column), False, 10))
        lines.extend(["        }", "        Insert: {"])
        for column in table.columns:
            lines.append(
                render_property(
                    column.name,
                    quote_ts_type(column),
                    column.has_default or column.nullable,
                    10,
                )
            )
        lines.extend(["        }", "        Update: {"])
        for column in table.columns:
            lines.append(render_property(column.name, quote_ts_type(column), True, 10))
        lines.extend(["        }", "        Relationships: ["])
        for relationship in table.relationships:
            lines.extend(
                [
                    "          {",
                    f'            foreignKeyName: "{relationship.name}"',
                    f"            columns: {render_tuple(relationship.columns)}",
                    f"            isOneToOne: {str(relationship.is_one_to_one).lower()}",
                    f'            referencedRelation: "{relationship.referenced_relation}"',
                    f"            referencedColumns: {render_tuple(relationship.referenced_columns)}",
                    "          },",
                ]
            )
        lines.extend(["        ]", "      }"])
    lines.extend(
        [
            "    }",
            "    Views: { [_ in never]: never }",
            "    Functions: {",
        ]
    )
    for function in functions:
        lines.extend([f"      {function.name}: {{", "        Args: {"])
        for argument in function.arguments:
            lines.append(
                render_property(argument.name, argument.ts_type, argument.optional, 10)
            )
        lines.extend(
            [
                "        }",
                f"        Returns: {function.return_type}",
                "      }",
            ]
        )
    lines.extend(
        [
            "    }",
            "    Enums: { [_ in never]: never }",
            "    CompositeTypes: { [_ in never]: never }",
            "  }",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="Fail if committed output is stale"
    )
    parser.add_argument(
        "--stdout", action="store_true", help="Print instead of writing"
    )
    args = parser.parse_args()

    sql, schema_hash = read_migrations()
    generated = render_types(parse_tables(sql), parse_functions(sql), schema_hash)

    if args.stdout:
        sys.stdout.write(generated)
        return 0
    if args.check:
        if (
            not OUTPUT_PATH.exists()
            or OUTPUT_PATH.read_text(encoding="utf-8") != generated
        ):
            print(
                "Generated database types are stale. Run scripts/generate_database_types.py.",
                file=sys.stderr,
            )
            return 1
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(generated, encoding="utf-8")
    print(f"Generated {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
