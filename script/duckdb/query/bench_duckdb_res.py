#!/usr/bin/env python3
"""
DuckDB 资源占用采样脚本（修复版）
- 修复了进程退出后无法读取最终 CPU 时间的 Race Condition
- 逻辑对齐 Polystore/ArangoDB 脚本
- 使用 Queue 同步代替 join 同步

用法:
    python3 bench_duckdb_res.py *.sql -n 5 -t 4 -o result.csv
"""
import argparse
import csv
import multiprocessing as mp
import statistics
import threading
import time
from pathlib import Path

import duckdb
import psutil

DB_PATH = '/duckdb_data/mapl.db'

SHORT_QUERY_THRESHOLD_MS = 500
MIN_SAMPLE_INTERVAL = 0.05   # 50ms
MAX_SAMPLE_INTERVAL = 0.2    # 200ms
TARGET_SAMPLE_COUNT = 20


# -------------------- 工具函数 --------------------
def pick_interval(latency_ms: float) -> float:
    ideal = latency_ms / TARGET_SAMPLE_COUNT / 1000
    return max(MIN_SAMPLE_INTERVAL, min(MAX_SAMPLE_INTERVAL, ideal))


# -------------------- 子进程 Worker --------------------
def _worker(sql: str, db_path: str, threads: int, 
            ready_event: mp.Event, start_event: mp.Event, 
            result_queue: mp.Queue) -> None:
    """
    子进程：负责执行 SQL
    """
    try:
        # 建立连接、加载扩展
        conn = duckdb.connect(db_path, config={"allow_unsigned_extensions": "true"})
        conn.execute("INSTALL duckpgq FROM community; INSTALL vss;")
        conn.execute("LOAD duckpgq; LOAD vss;")
        conn.execute(f"SET threads={threads}")
        
        # 通知父进程：连接已建立
        ready_event.set()
        
        # 等待开始信号
        start_event.wait()
        # 执行查询并计时
        t0 = time.perf_counter()
        conn.execute(sql).fetchall()
        t1 = time.perf_counter()
        
        # 发送耗时结果
        result_queue.put((t1 - t0) * 1000)
        
        conn.close()
    except Exception as e:
        result_queue.put(e)


# -------------------- 短查询测量 --------------------
def measure_short_query(sql: str, threads: int) -> tuple:
    """
    短查询：cpu_times 差值法 (精确测量)
    """
    ready_event = mp.Event()
    start_event = mp.Event()
    result_queue = mp.Queue()
    
    p = mp.Process(target=_worker, args=(sql, DB_PATH, threads, ready_event, start_event, result_queue))
    p.start()
    
    # 1. 等待连接建立
    ready_event.wait()
    
    proc = psutil.Process(p.pid)
    
    # 2. 记录开始状态
    try:
        cpu_start = proc.cpu_times()
        rss_peak = proc.memory_info().rss
    except psutil.NoSuchProcess:
        p.kill()
        return (0, 0, 0, 0, 0, 0)
    
    # 3. 开始执行
    start_event.set()
    
    # 4. 等待结果 (阻塞直到 Worker 完成)
    #    关键点：Queue.get() 返回时，子进程逻辑已跑完，但尚未 join，此时读取资源最准确
    result = result_queue.get()
    
    # 5. 立即读取结束状态 & 计算 CPU 时间
    total_cpu_time = 0.0
    try:
        # 尝试捕获最后时刻的 RSS 峰值
        rss_peak = max(rss_peak, proc.memory_info().rss)
        
        cpu_end = proc.cpu_times()
        total_cpu_time = (cpu_end.user - cpu_start.user) + (cpu_end.system - cpu_start.system)
    except psutil.NoSuchProcess:
        # 极少数情况进程退出极快，可能捕获不到，忽略
        pass
    
    # 6. 回收子进程
    p.join()
    
    if isinstance(result, Exception):
        print(f"Worker Error: {result}")
        return (0, 0, 0, 0, 0, 0)
    
    latency_ms = result
    cpu_time_ms = total_cpu_time * 1000
    cpu_percent = (cpu_time_ms / latency_ms) * 100 if latency_ms > 0 else 0.0
    peak_rss_gb = rss_peak / (1024 ** 3)
    
    return (latency_ms, cpu_time_ms, cpu_percent, peak_rss_gb, cpu_percent, cpu_percent)


# -------------------- 长查询采样器 --------------------
class LongQuerySampler:
    """长查询采样器"""
    def __init__(self, pid: int, interval: float):
        self.pid = pid
        self.interval = interval
        self.stop_flag = threading.Event()
        self.cpu_samples = []
        self.rss_samples = []
        
        try:
            self.proc = psutil.Process(pid)
            self.proc.cpu_percent(interval=None) # init
            self.cpu_times_last = self.proc.cpu_times()
        except psutil.NoSuchProcess:
            self.proc = None
            
        self.total_cpu_time = 0.0
        self.lock = threading.Lock()

    def _collect_cpu_delta(self):
        if not self.proc: return 0.0
        try:
            now = self.proc.cpu_times()
            delta = (now.user - self.cpu_times_last.user) + (now.system - self.cpu_times_last.system)
            self.cpu_times_last = now
            return max(0.0, delta)
        except psutil.NoSuchProcess:
            return 0.0

    def _loop(self):
        while not self.stop_flag.is_set():
            try:
                if not self.proc: break
                
                cpu_pct = self.proc.cpu_percent(interval=None)
                rss = self.proc.memory_info().rss / (1024 ** 3)
                
                delta = self._collect_cpu_delta()
                with self.lock:
                    self.total_cpu_time += delta
                
                if not self.stop_flag.is_set():
                    self.cpu_samples.append(cpu_pct)
                    self.rss_samples.append(rss)
            except psutil.NoSuchProcess:
                break
            time.sleep(self.interval)

    def __enter__(self):
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_flag.set()
        self.thread.join()
        # 最后采集一次
        delta = self._collect_cpu_delta()
        with self.lock:
            self.total_cpu_time += delta

    def peak_cpu(self): return max(self.cpu_samples, default=0.0)
    def peak_rss(self): return max(self.rss_samples, default=0.0)
    def avg_cpu(self): return sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0
    def total_cpu_time_ms(self): 
        with self.lock: return self.total_cpu_time * 1000


def measure_long_query(sql: str, interval: float, threads: int) -> tuple:
    """
    长查询：采样法
    """
    ready_event = mp.Event()
    start_event = mp.Event()
    result_queue = mp.Queue()
    
    p = mp.Process(target=_worker, args=(sql, DB_PATH, threads, ready_event, start_event, result_queue))
    p.start()
    
    ready_event.wait()
    
    with LongQuerySampler(p.pid, interval) as sampler:
        start_event.set()
        # 阻塞等待结果 (此时子进程尚未 join，Sampler 仍能采集到最后的数据)
        result = result_queue.get()
    
    p.join()
    
    if isinstance(result, Exception):
        print(f"Worker Error: {result}")
        return (0, 0, 0, 0, 0, 0)
    
    latency_ms = result
    cpu_time_ms = sampler.total_cpu_time_ms()
    cpu_percent = (cpu_time_ms / latency_ms) * 100 if latency_ms > 0 else 0.0
    
    return (latency_ms, cpu_time_ms, cpu_percent,
            sampler.peak_rss(), sampler.peak_cpu(), sampler.avg_cpu())


# -------------------- 预热查询 --------------------
def warmup_query(sql: str, threads: int) -> float:
    """预热查询，返回延迟(ms)"""
    ready_event = mp.Event()
    start_event = mp.Event()
    result_queue = mp.Queue()
    
    p = mp.Process(target=_worker, args=(sql, DB_PATH, threads, ready_event, start_event, result_queue))
    p.start()
    ready_event.wait()
    start_event.set()
    res = result_queue.get()
    p.join()
    
    if isinstance(res, Exception): return 0.0
    return res


# -------------------- CSV 输出 --------------------
def flush_csv(out: Path, data: dict, threads: int):
    header = ['file', 'threads', 'method', 'latency_ms', 'cpu_time_ms', 
              'cpu_%', 'rss_gb', 'peak_cpu_%', 'avg_cpu_%']
    rows = []
    
    for fname, info in data.items():
        if not info['samples']:
            rows.append([fname, threads, info['method']] + ['']*6)
            continue
        
        medians = [statistics.median([s[i] for s in info['samples']]) for i in range(6)]
        rows.append([fname, threads, info['method']] + [f'{v:.1f}' if i!=3 else f'{v:.2f}' for i,v in enumerate(medians)])
    
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as f:
        csv.writer(f).writerows([header] + rows)


# -------------------- 主流程 --------------------
def main():
    parser = argparse.ArgumentParser(description='DuckDB 资源采样脚本')
    parser.add_argument('-n', '--rounds', type=int, default=5)
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'))
    parser.add_argument('-t', '--threads', type=int, default=1)
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()

    exclude = {Path(f).name for f in args.exclude}
    files = sorted([Path(f).resolve() for f in args.files if Path(f).name not in exclude], key=lambda p: p.name)
    data = {f.name: {'method': '', 'interval': 0.0, 'samples': []} for f in files}

    print("="*60 + "\n预热轮\n" + "="*60)
    for f in files:
        sql = f.read_text().strip()
        try:
            lat = warmup_query(sql, args.threads)
            method = "cpu_times" if lat < SHORT_QUERY_THRESHOLD_MS else "sampling"
            data[f.name].update({'method': method, 'interval': pick_interval(lat)})
            print(f'{f.name}: {lat:.1f}ms → {method}')
        except Exception as e:
            print(f'❌ {f.name}: {e}')

    print("\n" + "="*60 + "\n正式采样\n" + "="*60)
    for rnd in range(1, args.rounds + 1):
        print(f"\n----- 第 {rnd} 轮 -----")
        for f in files:
            sql = f.read_text().strip()
            try:
                info = data[f.name]
                if info['method'] == "cpu_times":
                    res = measure_short_query(sql, args.threads)
                else:
                    res = measure_long_query(sql, info['interval'], args.threads)
                
                info['samples'].append(res)
                print(f'{f.name}: lat={res[0]:.1f}ms cpu_time={res[1]:.1f}ms cpu={res[2]:.1f}% rss={res[3]:.2f}GB')
                flush_csv(args.out, data, args.threads)
            except Exception as e:
                print(f'❌ {f.name}: {e}')

    print(f'\n✅ 完成 → {args.out}')


if __name__ == '__main__':
    main()