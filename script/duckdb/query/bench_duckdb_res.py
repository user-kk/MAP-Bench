#!/usr/bin/env python3
"""
DuckDB 资源占用采样脚本（子进程执行 SQL，父进程纯采样，零干扰）
用法:
    python3 bench_duckdb_res.py *.sql -n 5 -o result.csv
"""
import argparse
import csv
import multiprocessing as mp
import os
import statistics
import threading
import time
from pathlib import Path

import duckdb
import psutil

DB_PATH = '/duckdb_data/openalex_middle.db'

# ---------- 资源采样器 ----------
class QuerySampler:
    def __init__(self, pid: int, interval: float):
        self.pid = pid
        self.interval = interval
        self.proc = psutil.Process(pid)
        self.stop_flag = threading.Event()
        self.cpu_samples, self.rss_samples = [], []

    def _loop(self):
        try:
            self.proc.cpu_percent(None)  # 丢掉第一次
        except psutil.NoSuchProcess:
            return
        while not self.stop_flag.is_set():
            try:
                cpu = self.proc.cpu_percent(interval=self.interval)
                rss = self.proc.memory_info().rss / 1024 ** 3
            except psutil.NoSuchProcess:
                break
            if not self.stop_flag.is_set():
                self.cpu_samples.append(cpu)
                self.rss_samples.append(rss)

    def __enter__(self):
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_flag.set()
        self.thread.join()

    def peak_cpu(self) -> float:
        return max(self.cpu_samples) if self.cpu_samples else 0.0

    def peak_rss(self) -> float:
        return max(self.rss_samples) if self.rss_samples else 0.0

    def avg_cpu(self) -> float:
        return sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0


# ---------- 子进程工作函数 ----------
def _worker(sql: str, db_path: str, res_q: mp.Queue) -> None:
    """
    在独立进程里跑 SQL，并把实际耗时(ms)写回队列
    """
    conn = duckdb.connect(db_path, config={"allow_unsigned_extensions": "true"})
    conn.execute("INSTALL duckpgq FROM community; INSTALL vss;")
    conn.execute("LOAD duckpgq; LOAD vss;")
    conn.execute("SET threads=1")
    conn.execute("SET memory_limit='50GB'")
    conn.execute(sql).fetchall()
    conn.close()


# ---------- 采样间隔策略 ----------
def pick_interval(latency_ms: float) -> float:
    if latency_ms <= 100:
        interval = 0.001
    elif latency_ms <= 10000:
        interval = 0.01
    else:
        interval = 0.1
    return min(interval, latency_ms / 5 / 1000)


# ---------- 采样一次（子进程执行 + 父进程采样） ----------
def sample_resource(sql: str, interval: float) -> tuple[float, float, float]:
    res_q = mp.Queue()
    p = mp.Process(target=_worker, args=(sql, DB_PATH, res_q))
    p.start()
    pid = p.pid 

    with QuerySampler(pid, interval) as sampler:
        p.join()  # 等 SQL 跑完
    return sampler.peak_cpu(), sampler.peak_rss(), sampler.avg_cpu()


# ---------- 主流程 ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--rounds', type=int, default=5)
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()

    exclude_set = {Path(f).name for f in args.exclude}          
    file_list = sorted([Path(f).resolve() for f in args.files
                    if Path(f).name not in exclude_set],    
                   key=lambda p: p.name)
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return
    data = {f.name: [] for f in file_list}  # 存放结果

    # ---------- 第一轮：纯测延迟，定档 ----------
    for f in file_list:
        sql = f.read_text().strip()
        res_q = mp.Queue()
        p = mp.Process(target=_worker, args=(sql, DB_PATH, res_q))
        t0 = time.perf_counter()
        p.start()
        p.join()
        lat_ms = (time.perf_counter() - t0) * 1000  # wall-clock
        interval = pick_interval(lat_ms)
        print(f'{f.name} 定档延迟 {lat_ms:.3f} ms → 采样 {interval*1000:.0f} ms')
        data[f.name].append(('interval', lat_ms, interval))

    # ---------- 第 2 … n+1 轮：正式采样 ----------
    for rnd in range(2, args.rounds + 2):
        for f in file_list:
            sql = f.read_text().strip()
            _, _, interval = data[f.name][0]
            pc, pr, ac = sample_resource(sql, interval)
            data[f.name].append((pc, pr, ac))
            print(
                f'R{rnd-1:02d}  {f.name}: '
                f'peak_cpu={pc:.1f}% peak_rss={pr:.1f}GB avg_cpu={ac:.1f}%'
            )
            flush_csv(args.out, data, args.rounds)

    print(f'资源采样完成 → {args.out}')


# ---------- CSV 落盘 ----------
def flush_csv(out: Path, data: dict, runs: int):
    header = [
        'file',
        'first_lat_ms',
        'sample_interval_ms',
        'peak_cpu_%',
        'peak_rss_gb',
        'avg_cpu_%',
    ]
    rows = []
    for fname, raw in data.items():
        first_lat, sample_interval = 0.0, 0.0
        samples = []
        for r in raw:
            if isinstance(r, tuple) and len(r) == 3 and r[0] == 'interval':
                first_lat, sample_interval = r[1], r[2]
            else:
                samples.append(r)
        if not samples:
            rows.append(
                [
                    fname,
                    f'{first_lat:.3f}',
                    f'{sample_interval*1000:.0f}',
                    '',
                    '',
                    '',
                ]
            )
            continue
        pcu = statistics.median([s[0] for s in samples])
        prss = statistics.median([s[1] for s in samples])
        acu = statistics.median([s[2] for s in samples])
        rows.append(
            [
                fname,
                f'{first_lat:.3f}',
                f'{sample_interval*1000:.0f}',
                f'{pcu:.1f}',
                f'{prss:.1f}',
                f'{acu:.1f}',
            ]
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as cf:
        csv.writer(cf).writerows([header] + rows)


if __name__ == '__main__':
    main()