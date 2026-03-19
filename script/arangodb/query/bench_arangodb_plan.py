#!/usr/bin/env python3
"""
ArangoDB 执行计划获取器：通过 arangosh 调用 db._profileQuery() 获取原生格式化输出。

用法:
    python3 arango_explain_analyze.py query/*.aql -o plans.txt
    python3 arango_explain_analyze.py query/*.aql -x G3.aql --warmup 3 -o plans.txt
"""
import argparse
import subprocess
from pathlib import Path

ARANGOSH = "arangosh"  # 确保在 PATH 中，或改为绝对路径
DB_CONF = {
    "server.endpoint": "tcp://127.0.0.1:8529",
    "server.database": "mapl",
    "server.username": "root",
    "server.password": "linux123",
}

SEPARATOR = "=" * 100


def run_query(aql: str, timeout: int = 3600, profile: bool = False) -> str:
    """通过 arangosh 执行查询，profile=True 时返回执行计划，否则只执行"""
    
    escaped_aql = aql.replace("\\", "\\\\").replace("`", "\`")
    
    if profile:
        js_code = f"""
var query = `{escaped_aql}`;
db._profileQuery(query, {{}}, {{maxRuntime: {timeout}}});
"""
    else:
        js_code = f"""
var query = `{escaped_aql}`;
db._query(query, {{}}, {{maxRuntime: {timeout}}});
"""

    cmd = [ARANGOSH, "--quiet", "true", "--console.colors", "false"]
    for key, val in DB_CONF.items():
        cmd.extend([f"--{key}", val])
    cmd.extend(["--javascript.execute-string", js_code])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 60
        )
        output = result.stdout
        if result.stderr:
            stderr_lines = [
                line for line in result.stderr.splitlines()
                if not line.startswith("Connected to")
                and not line.startswith("Please note")
                and line.strip()
            ]
            if stderr_lines:
                output += "\n\nSTDERR:\n" + "\n".join(stderr_lines)
        return output if output.strip() else "(empty output)"
    except subprocess.TimeoutExpired:
        return "ERROR: Execution timed out"
    except FileNotFoundError:
        return f"ERROR: '{ARANGOSH}' not found. Please install or set correct path."
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


def main():
    parser = argparse.ArgumentParser(
        description='通过 arangosh db._profileQuery() 获取执行计划')
    parser.add_argument('-o', '--out', type=Path, default=Path('arango_plans.txt'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('--warmup', type=int, default=0,
                        help='预热轮数 (不计时，用于缓存预热，默认: 0)')
    parser.add_argument('--timeout', type=int, default=3600)
    parser.add_argument('files', nargs='+', help='.aql files')
    args = parser.parse_args()

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted(
        [Path(f).resolve() for f in args.files
         if Path(f).name not in exclude_set],
        key=lambda p: p.name
    )
    if not file_list:
        print('No files to process.')
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', encoding='utf-8') as out_f:
        out_f.write(f"ArangoDB Profile Execution Plans (via arangosh)\n")
        out_f.write(f"Warmup rounds: {args.warmup}\n")
        out_f.write(f"{SEPARATOR}\n\n")

        for f in file_list:
            aql = f.read_text().strip()
            print(f'Processing: {f.name}')

            out_f.write(f"{SEPARATOR}\n")
            out_f.write(f"File: {f.name}\n")
            out_f.write(f"{SEPARATOR}\n\n")

            out_f.write("-- Original AQL:\n")
            out_f.write(aql)
            out_f.write("\n\n")

            # 预热阶段：执行但不获取执行计划
            if args.warmup > 0:
                print(f'  Warmup phase ({args.warmup} rounds)...')
                for warmup_idx in range(1, args.warmup + 1):
                    output = run_query(aql, timeout=args.timeout, profile=False)
                    if output.startswith("ERROR:"):
                        print(f'    Warmup {warmup_idx}/{args.warmup}: {output.splitlines()[0]}')
                    else:
                        print(f'    Warmup {warmup_idx}/{args.warmup}: OK')
                print(f'  Warmup completed.')

            # 正式执行：获取执行计划
            out_f.write(f"--- db._profileQuery() ---\n\n")
            output = run_query(aql, timeout=args.timeout, profile=True)
            out_f.write(output)
            out_f.write("\n\n")

            print(f'  db._profileQuery(): OK')

            out_f.write("\n")

    print(f'\nDone: {args.out}')


if __name__ == '__main__':
    main()