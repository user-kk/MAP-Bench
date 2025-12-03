#!/usr/bin/env python3
"""
AgensGraph 资源占用采样脚本（每条 SQL 重新建连，首轮只定档，不输出执行时间）
用法:
    python3 bench_res.py queries/*.sql -n 5 -o result.csv
"""
import argparse, csv, statistics, time
from pathlib import Path
import psycopg
import psutil
import threading

DB_CONF = dict(dbname='openalex_middle', user='agensgraph',
               password='linux123', host='127.0.0.1', port=5555)


# ---------- 采样器 ----------
class QuerySampler:
    def __init__(self, pid: int, interval: float):
        self.pid = pid
        self.interval = interval
        self.proc = psutil.Process(pid)
        self.stop_flag = threading.Event()
        self.cpu_samples, self.rss_samples = [], []

    def _loop(self):
        try:
            self.proc.cpu_percent(None)          # 丢弃第一次
        except psutil.NoSuchProcess:
            return
        while not self.stop_flag.is_set():
            try:
                cpu = self.proc.cpu_percent(interval=self.interval)
                rss = self.proc.memory_info().rss / 1024 ** 3
            except psutil.NoSuchProcess:
                break
            # 只有在完整采完一次后才追加
            if not self.stop_flag.is_set():
                self.cpu_samples.append(cpu)
                self.rss_samples.append(rss)

    def __enter__(self):
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop_flag.set()
        self.thread.join()

    def peak_cpu(self) -> float:
        return max(self.cpu_samples) if self.cpu_samples else 0.0

    def peak_rss(self) -> float:
        return max(self.rss_samples) if self.rss_samples else 0.0

    def avg_cpu(self) -> float:
        return sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0


def pick_interval(latency_ms: float) -> float:
    """
    根据首轮延迟给出采样间隔，并保证至少采 5 个点
    """
    if latency_ms <= 100:
        interval = 0.001          # 1 ms 该级别受限于 psutil 精度，误差较大
    elif latency_ms <= 10000:
        interval = 0.01           # 10 ms
    else:
        interval = 0.1            # 100 ms
    # 至少 5 个点
    return min(interval, latency_ms / 5 / 1000)


def sample_resource(sql: str, interval: float, conn_params: dict,pid: int = None):
    """
    在采样线程存活期间执行 SQL，只返回资源数据, pid: 为 None 时自动查询，否则直接使用传入值
    """
    conn = psycopg.connect(**conn_params)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET graph_path = academic_net")
    cur.execute("SET plan_cache_mode = force_custom_plan")
    cur.execute("SELECT pg_backend_pid()")
    cur.execute("SET max_parallel_workers_per_gather = 0")
    # 如果命令行没给 PID，就查一次
    if pid is None:
        cur.execute("SELECT pg_backend_pid()")
        pid = cur.fetchone()[0]

    with QuerySampler(pid, interval) as sampler:
        cur.execute(sql)          # 真正执行 SQL
        cur.fetchall()            # 消费结果
    # 汇总资源
    pc, pr, ac = sampler.peak_cpu(), sampler.peak_rss(), sampler.avg_cpu()
    cur.close()
    conn.close()
    return pc, pr, ac


# ---------- 主流程 ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--rounds', type=int, default=5)
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('-p', '--pid', type=int, default=None,
                    help='手动指定后端进程 PID；缺省则自动查询 pg_backend_pid()')
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()

    exclude_set = {Path(f).name for f in args.exclude}          
    file_list = sorted([Path(f).resolve() for f in args.files
                    if Path(f).name not in exclude_set],    
                   key=lambda p: p.name)
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    # ← 改动：用 list 存第一轮数据，其余仍是 tuple
    data = {f.name: [] for f in file_list}      # 每项存 (peak_cpu, peak_rss, avg_cpu)

    # ---------- 第一轮：仅测延迟，用于定档 ----------
    for f in file_list:
        sql = f.read_text().strip()
        conn = psycopg.connect(**DB_CONF)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET graph_path = academic_net")
        cur.execute("SET plan_cache_mode = force_custom_plan")
        cur.execute("SET max_parallel_workers_per_gather = 0")

        t0 = time.perf_counter()
        cur.execute(sql)
        cur.fetchall()
        t1 = time.perf_counter()
        lat_ms = (t1 - t0) * 1000
        interval = pick_interval(lat_ms)
        print(f'{f.name} 定档延迟 {lat_ms:.3f} ms → 采样 {interval*1000:.0f} ms')
        # ← 改动：把首延迟 & 间隔一起存
        data[f.name].append(('interval', lat_ms, interval))
        cur.close()
        conn.close()

    # ---------- 第二轮及以后：正式采样资源 ----------
    for rnd in range(2, args.rounds + 2):       # 从 2 开始方便打印
        for f in file_list:
            sql = f.read_text().strip()

            _, _, interval = data[f.name][0]
            pc, pr, ac = sample_resource(sql, interval, DB_CONF,args.pid)
            data[f.name].append((pc, pr, ac))   # 覆盖掉之前的 interval
            print(f'R{rnd-1:02d}  {f.name}: '
                  f'peak_cpu={pc:.1f}% peak_rss={pr:.1f}GB avg_cpu={ac:.1f}%')

            flush_csv(args.out, data)  # 实时落盘

    print(f'资源采样完成 → {args.out}')


def flush_csv(out: Path, data: dict):
    # ← 改动：新增两列
    header = ['file', 'first_lat_ms', 'sample_interval_ms', 'peak_cpu_%', 'peak_rss_gb', 'avg_cpu_%']
    rows = []
    for fname, raw in data.items():
        # 找出第一轮存的 interval 记录
        first_lat, sample_interval = 0.0, 0.0
        samples = []
        for r in raw:
            if isinstance(r, tuple) and len(r) == 3 and r[0] == 'interval':
                first_lat, sample_interval = r[1], r[2]
            elif isinstance(r, tuple) and len(r) == 3:
                samples.append(r)
        if not samples:
            rows.append([fname, f'{first_lat:.3f}', f'{sample_interval*1000:.0f}', '', '', ''])
            continue
        pcu = statistics.median([r[0] for r in samples])
        prss = statistics.median([r[1] for r in samples])
        acu = statistics.median([r[2] for r in samples])
        rows.append([fname,
                     f'{first_lat:.3f}',
                     f'{sample_interval*1000:.0f}',
                     f'{pcu:.1f}' if isinstance(pcu, float) else pcu,
                     f'{prss:.1f}' if isinstance(prss, float) else prss,
                     f'{acu:.1f}' if isinstance(acu, float) else acu])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as cf:
        csv.writer(cf).writerows([header] + rows)


if __name__ == '__main__':
    main()