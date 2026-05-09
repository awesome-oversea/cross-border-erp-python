import pathlib

files = [
    "src/erp/middleware/infrastructure/models.py",
    "src/erp/middleware/content_review/domain/models.py",
    "src/erp/middleware/forex/domain/models.py",
    "src/erp/modules/ads/domain/smart_bid_models.py",
    "src/erp/modules/bi/domain/metric_alert_models.py",
    "src/erp/modules/sys/domain/cdc_models.py",
    "src/erp/modules/sys/domain/connector_models.py",
    "src/erp/modules/sys/domain/connector_spi_models.py",
    "src/erp/modules/sys/domain/dict_models.py",
    "src/erp/modules/sys/domain/event_catalog_models.py",
    "src/erp/modules/sys/domain/param_models.py",
    "src/erp/shared/audit/logger.py",
    "src/erp/shared/workflow/entities.py",
]

fixed = 0
for fpath in files:
    p = pathlib.Path(fpath)
    if not p.exists():
        print(f"SKIP (not found): {fpath}")
        continue
    content = p.read_text(encoding="utf-8")
    lines = content.split("\n")
    new_lines = []
    datetime_import_line = None
    in_type_checking = False
    type_checking_indent = ""

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == "if TYPE_CHECKING:":
            in_type_checking = True
            type_checking_indent = line[: len(line) - len(line.lstrip())]
            new_lines.append(line)
            continue

        if in_type_checking:
            if stripped.startswith("from datetime import"):
                datetime_import_line = stripped
                continue
            elif stripped and not stripped.startswith(("from ", "import ", "#")):
                in_type_checking = False
                if datetime_import_line:
                    new_lines.append(type_checking_indent + datetime_import_line)
                    datetime_import_line = None
                new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if datetime_import_line:
        insert_pos = 0
        for i, line in enumerate(new_lines):
            if line.startswith("from __future__"):
                insert_pos = i + 1
            elif line.startswith("from ") or line.startswith("import "):
                if insert_pos == 0:
                    insert_pos = i
                break
        if insert_pos == 0:
            for i, line in enumerate(new_lines):
                if line.strip() and not line.startswith("#"):
                    insert_pos = i
                    break
        new_lines.insert(insert_pos, datetime_import_line)

    new_content = "\n".join(new_lines)
    if new_content != content:
        p.write_text(new_content, encoding="utf-8")
        fixed += 1
        print(f"Fixed: {fpath}")

print(f"\nTotal fixed: {fixed}")
