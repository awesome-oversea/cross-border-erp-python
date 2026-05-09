import pathlib

files = [
    "src/erp/middleware/infrastructure/models.py",
    "src/erp/middleware/content_review/domain/models.py",
    "src/erp/middleware/forex/domain/models.py",
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
        continue
    content = p.read_text(encoding="utf-8")
    lines = content.split("\n")
    new_lines = []
    seen_datetime = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("from datetime import") and not stripped.startswith("from datetime import "):
            pass
        if stripped == "from datetime import datetime" or stripped.startswith("from datetime import ") and "datetime" in stripped:
            if seen_datetime:
                continue
            seen_datetime = True
        new_lines.append(line)

    new_content = "\n".join(new_lines)
    if new_content != content:
        p.write_text(new_content, encoding="utf-8")
        fixed += 1
        print(f"Fixed: {fpath}")

print(f"\nTotal fixed: {fixed}")
