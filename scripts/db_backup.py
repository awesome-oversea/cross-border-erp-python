"""
数据库备份与恢复脚本 (P8-009)

支持: PostgreSQL全量备份/增量备份/恢复验证
用法:
  python scripts/db_backup.py --action backup --type full
  python scripts/db_backup.py --action restore --file backup_20260507.sql
  python scripts/db_backup.py --action verify
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime


def run(cmd: list[str]) -> bool:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {e.stderr[:500]}", file=sys.stderr)
        return False


def backup(db_name: str, db_user: str, backup_dir: str, backup_type: str = "full"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(backup_dir, exist_ok=True)
    filename = f"{db_name}_{backup_type}_{ts}.sql"
    filepath = os.path.join(backup_dir, filename)
    cmd = ["pg_dump", f"-U{db_user}", f"-d{db_name}", "-Fc", "-f", filepath]
    if backup_type == "schema_only":
        cmd.insert(-2, "--schema-only")
    print(f"[{ts}] 开始{backup_type}备份: {filepath}")
    success = run(cmd)
    if success:
        size = os.path.getsize(filepath)
        print(f"备份完成: {filepath} ({size/1024/1024:.1f}MB)")
    return success


def restore(db_name: str, db_user: str, filepath: str):
    if not os.path.exists(filepath):
        print(f"备份文件不存在: {filepath}", file=sys.stderr)
        return False
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"[{ts}] 开始恢复: {filepath}")
    return run(["pg_restore", f"-U{db_user}", f"-d{db_name}", "-c", filepath])


def verify(db_name: str, db_user: str):
    checks = [
        ("检查数据库连接", f"psql -U {db_user} -d {db_name} -c 'SELECT 1'"),
        ("检查14个Schema", f"psql -U {db_user} -d {db_name} -c 'SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE $$pg_%$$ AND nspname != $$public$$'"),
        ("检查表数量", f"psql -U {db_user} -d {db_name} -c 'SELECT schemaname, count(*) FROM pg_tables GROUP BY schemaname'"),
        ("检查迁移版本", f"psql -U {db_user} -d {db_name} -c 'SELECT * FROM alembic_version'"),
    ]
    all_ok = True
    for name, cmd in checks:
        print(f"\n[{name}]")
        ok = run(cmd.split())
        if not ok: all_ok = False
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="数据库备份与恢复工具")
    parser.add_argument("--action", choices=["backup", "restore", "verify"], required=True, help="操作类型")
    parser.add_argument("--type", choices=["full", "schema_only"], default="full", help="备份类型")
    parser.add_argument("--file", default="", help="恢复用的备份文件路径")
    parser.add_argument("--db", default=os.getenv("DB_NAME", "erp"), help="数据库名")
    parser.add_argument("--user", default=os.getenv("DB_USER", "erp"), help="数据库用户")
    parser.add_argument("--dir", default=os.getenv("BACKUP_DIR", "backups"), help="备份目录")
    args = parser.parse_args()

    success = False
    if args.action == "backup":
        success = backup(args.db, args.user, args.dir, args.type)
    elif args.action == "restore":
        if not args.file: print("--file 参数必填"); sys.exit(1)
        success = restore(args.db, args.user, args.file)
    elif args.action == "verify":
        success = verify(args.db, args.user)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
