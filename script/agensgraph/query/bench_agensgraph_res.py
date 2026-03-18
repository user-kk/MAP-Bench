#!/usr/bin/env python3
"""
AgensGraph 资源采样脚本（优化版）
- 短查询（<500ms）：cpu_times 差值法
- 长查询（≥500ms）：采样法，最小间隔 50ms
- 所有指标取中位数
"""
import argparse
import csv
import os
import socket
import statistics
import subprocess
import threading
import time
from pathlib import Path

import psutil
import psycopg

DB_CONF = dict(
    dbname='mapl',
    user='agensgraph',
    password='linux123',
    host='127.0.0.1',
    port=5555
)

SHORT_QUERY_THRESHOLD_MS = 500
MIN_SAMPLE_INTERVAL = 0.05   # 50ms
MAX_SAMPLE_INTERVAL = 0.2    # 200ms
TARGET_SAMPLE_COUNT = 20


def setup_session(cur, max_parallel: int):
    """统一的会话设置"""
    cur.execute("SET graph_path = academic_net")
    cur.execute("SET plan_cache_mode = force_custom_plan")
    cur.execute(f"SET max_parallel_workers_per_gather = {max_parallel}")
    if max_parallel == 0:
        cur.execute("SET work_mem = '12GB'")
    else:
        cur.execute("SET work_mem = '2GB'")


def pick_interval(latency_ms: float) -> float:
    """
    根据查询延迟选择采样间隔
    - 最小 50ms（cpu_percent 准确性）
    - 最大 200ms
    - 目标采样 20 次
    """
    ideal = latency_ms / TARGET_SAMPLE_COUNT / 1000
    return max(MIN_SAMPLE_INTERVAL, min(MAX_SAMPLE_INTERVAL, ideal))


def measure_short_query(sql: str, conn_params: dict, max_parallel: int) -> tuple:
    """
    短查询：cpu_times 差值法
    返回: (latency_ms, cpu_time_ms, cpu_%, peak_rss_gb, peak_cpu_%, avg_cpu_%)
    """
    conn = psycopg.connect(**conn_params)
    conn.autocommit = True
    cur = conn.cursor()
    setup_session(cur, max_parallel)
    
    cur.execute("SELECT pg_backend_pid()")
    main_pid = cur.fetchone()[0]
    proc = psutil.Process(main_pid)
    
    # 记录开始状态
    cpu_start = proc.cpu_times()
    rss_peak = proc.memory_info().rss
    t0 = time.perf_counter()
    
    # 执行查询
    cur.execute(sql)
    cur.fetchall()
    
    # 记录结束状态
    t1 = time.perf_counter()
    cpu_end = proc.cpu_times()
    rss_end = proc.memory_info().rss
    rss_peak = max(rss_peak, rss_end)
    
    # 计算指标
    elapsed = t1 - t0
    latency_ms = elapsed * 1000
    cpu_time = (cpu_end.user - cpu_start.user) + (cpu_end.system - cpu_start.system)
    cpu_time_ms = cpu_time * 1000
    cpu_percent = (cpu_time_ms / latency_ms) * 100 if latency_ms > 0 else 0.0
    peak_rss_gb = rss_peak / (1024 ** 3)
    
    cur.close()
    conn.close()
    
    # 短查询无采样，peak 和 avg 都用计算值
    return (latency_ms, cpu_time_ms, cpu_percent, peak_rss_gb, cpu_percent, cpu_percent)


class LongQuerySampler:
    """长查询采样器 - 实时累计 CPU 时间"""
    
    def __init__(self, main_pid: int, interval: float, max_parallel: int, conn_params: dict):
        self.main_pid = main_pid
        self.interval = interval
        self.max_parallel = max_parallel
        self.conn_params = conn_params
        self.stop_flag = threading.Event()
        self.cpu_samples = []
        self.rss_samples = []
        
        self.main_proc = psutil.Process(main_pid)
        self.procs = {main_pid: self.main_proc}
        self.main_proc.cpu_percent(interval=None)  # 初始化
        self.capture_workers = max_parallel > 0
        self.sample_count = 0
        
        # 每 500ms 刷新一次 worker 列表
        self.worker_refresh_every = max(1, int(0.5 / interval))
        
        # CPU 时间累计
        self.cpu_times_last = {main_pid: self.main_proc.cpu_times()}
        self.total_cpu_time = 0.0
        self.lock = threading.Lock()

    def _query_worker_pids(self) -> set:
        """查询当前活跃的 worker 进程"""
        try:
            conn = psycopg.connect(**self.conn_params, connect_timeout=0.5)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(
                "SELECT pid FROM pg_stat_activity WHERE leader_pid = %s",
                (self.main_pid,)
            )
            workers = {row[0] for row in cur.fetchall()}
            cur.close()
            conn.close()
            return workers
        except Exception:
            return set()

    def _refresh_workers(self):
        """刷新 worker 进程列表"""
        if not self.capture_workers:
            return
        
        self.sample_count += 1
        if self.sample_count % self.worker_refresh_every != 0:
            return
        
        worker_pids = self._query_worker_pids()
        
        # 添加新 worker
        for pid in worker_pids:
            if pid not in self.procs:
                try:
                    proc = psutil.Process(pid)
                    proc.cpu_percent(interval=None)
                    self.procs[pid] = proc
                    self.cpu_times_last[pid] = proc.cpu_times()
                except psutil.NoSuchProcess:
                    pass

    def _collect_cpu_delta(self, pid: int, proc) -> float:
        """收集单个进程的 CPU 时间增量"""
        try:
            cpu_now = proc.cpu_times()
            cpu_last = self.cpu_times_last.get(pid)
            if cpu_last:
                delta = (cpu_now.user - cpu_last.user) + (cpu_now.system - cpu_last.system)
            else:
                delta = 0.0
            self.cpu_times_last[pid] = cpu_now
            return max(0.0, delta)
        except psutil.NoSuchProcess:
            return 0.0

    def _loop(self):
        """采样循环"""
        while not self.stop_flag.is_set():
            self._refresh_workers()
            
            total_cpu_pct = 0.0
            total_rss = 0
            dead_pids = []
            
            for pid, proc in list(self.procs.items()):
                try:
                    total_cpu_pct += proc.cpu_percent(interval=None)
                    total_rss += proc.memory_info().rss
                    
                    # 实时累计 CPU 时间
                    delta = self._collect_cpu_delta(pid, proc)
                    with self.lock:
                        self.total_cpu_time += delta
                except psutil.NoSuchProcess:
                    dead_pids.append(pid)
            
            # 清理已退出的进程
            for p in dead_pids:
                self.procs.pop(p, None)
                self.cpu_times_last.pop(p, None)
            
            if not self.stop_flag.is_set():
                self.cpu_samples.append(total_cpu_pct)
                self.rss_samples.append(total_rss / (1024 ** 3))
            
            time.sleep(self.interval)

    def __enter__(self):
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_flag.set()
        self.thread.join()
        
        # 最后收集一次主进程的 CPU 时间
        try:
            delta = self._collect_cpu_delta(self.main_pid, self.main_proc)
            with self.lock:
                self.total_cpu_time += delta
        except psutil.NoSuchProcess:
            pass

    def peak_cpu(self) -> float:
        return max(self.cpu_samples, default=0.0)
    
    def peak_rss(self) -> float:
        return max(self.rss_samples, default=0.0)
    
    def avg_cpu(self) -> float:
        return sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0
    
    def total_cpu_time_ms(self) -> float:
        with self.lock:
            return self.total_cpu_time * 1000


def measure_long_query(sql: str, interval: float, conn_params: dict, max_parallel: int) -> tuple:
    """
    长查询：采样法
    返回: (latency_ms, cpu_time_ms, cpu_%, peak_rss_gb, peak_cpu_%, avg_cpu_%)
    """
    conn = psycopg.connect(**conn_params)
    conn.autocommit = True
    cur = conn.cursor()
    setup_session(cur, max_parallel)
    
    cur.execute("SELECT pg_backend_pid()")
    main_pid = cur.fetchone()[0]

    with LongQuerySampler(main_pid, interval, max_parallel, conn_params) as sampler:
        t0 = time.perf_counter()
        cur.execute(sql)
        cur.fetchall()
        t1 = time.perf_counter()

    latency_ms = (t1 - t0) * 1000
    cpu_time_ms = sampler.total_cpu_time_ms()
    
    # cpu_% 根据 cpu_time 计算（与短查询一致）
    cpu_percent = (cpu_time_ms / latency_ms) * 100 if latency_ms > 0 else 0.0
    
    cur.close()
    conn.close()
    
    return (latency_ms, cpu_time_ms, cpu_percent,
            sampler.peak_rss(), sampler.peak_cpu(), sampler.avg_cpu())


def restart_agens(host=DB_CONF['host'], port=DB_CONF['port'], max_wait=60):
    """重启 AgensGraph 服务"""
    print('♻️  restarting agensgraph …')
    subprocess.run(['sudo', 'systemctl', 'restart', 'agensgraph.service'], check=True)
    time.sleep(7)
    
    for _ in range(max_wait):
        try:
            with socket.create_connection((host, port), timeout=1):
                print('✅  agensgraph ready')
                return
        except (socket.error, OSError):
            time.sleep(1)
    raise RuntimeError('agensgraph 重启超时')


def warmup_query(sql: str, conn_params: dict, max_parallel: int) -> float:
    """预热查询，返回延迟(ms)"""
    conn = psycopg.connect(**conn_params)
    conn.autocommit = True
    cur = conn.cursor()
    setup_session(cur, max_parallel)

    t0 = time.perf_counter()
    cur.execute(sql)
    cur.fetchall()
    lat_ms = (time.perf_counter() - t0) * 1000
    
    cur.close()
    conn.close()
    return lat_ms


def flush_csv(out: Path, data: dict, max_parallel: int):
    """实时写入 CSV"""
    header = [
        'file',
        'parallel',
        'method',
        'latency_ms',
        'cpu_time_ms',
        'cpu_%',
        'rss_gb',
        'peak_cpu_%',
        'avg_cpu_%'
    ]
    rows = []
    
    for fname, info in data.items():
        method = info['method']
        samples = info['samples']
        
        if not samples:
            rows.append([fname, max_parallel, method] + [''] * 6)
            continue
        
        # 取中位数
        lat = statistics.median([s[0] for s in samples])
        cpu_time = statistics.median([s[1] for s in samples])
        cpu_pct = statistics.median([s[2] for s in samples])
        rss = statistics.median([s[3] for s in samples])
        peak_cpu = statistics.median([s[4] for s in samples])
        avg_cpu = statistics.median([s[5] for s in samples])
        
        rows.append([
            fname,
            max_parallel,
            method,
            f'{lat:.1f}',
            f'{cpu_time:.1f}',
            f'{cpu_pct:.1f}',
            f'{rss:.2f}',
            f'{peak_cpu:.1f}',
            f'{avg_cpu:.1f}'
        ])
    
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as f:
        csv.writer(f).writerows([header] + rows)


def main():
    parser = argparse.ArgumentParser(description='AgensGraph 资源采样脚本')
    parser.add_argument('-n', '--rounds', type=int, default=5,
                        help='采样轮数 (默认: 5)')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出CSV路径 (默认: result.csv)')
    parser.add_argument('-p', '--parallel', type=int, default=12,
                        help='max_parallel_workers_per_gather 值 (默认: 12, 设为0禁用并行)')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='排除的文件名列表')
    parser.add_argument('files', nargs='+',
                        help='SQL文件列表')
    args = parser.parse_args()

    max_parallel = args.parallel
    
    # 打印配置
    print("=" * 60)
    print(f"📊 max_parallel_workers_per_gather = {max_parallel}")
    print(f"📊 采样间隔范围: {MIN_SAMPLE_INTERVAL*1000:.0f}ms ~ {MAX_SAMPLE_INTERVAL*1000:.0f}ms")
    print(f"📊 短查询阈值: < {SHORT_QUERY_THRESHOLD_MS}ms 使用 cpu_times 差值法")
    print("=" * 60)

    # 处理文件列表
    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted(
        [Path(f).resolve() for f in args.files if Path(f).name not in exclude_set],
        key=lambda p: p.name
    )
    
    if not file_list:
        print("没有要处理的文件")
        return

    # 初始化数据结构
    # samples: [(latency_ms, cpu_time_ms, cpu_%, rss_gb, peak_cpu_%, avg_cpu_%), ...]
    data = {f.name: {'method': '', 'interval': 0.0, 'samples': []} for f in file_list}

    # ========== 预热轮：确定测量方法 ==========
    print("\n" + "=" * 60)
    print("预热轮：确定测量方法")
    print("=" * 60)
    
    for f in file_list:
        restart_agens()
        sql = f.read_text().strip()
        lat_ms = warmup_query(sql, DB_CONF, max_parallel)
        
        is_short = lat_ms < SHORT_QUERY_THRESHOLD_MS
        method = "cpu_times" if is_short else "sampling"
        interval = pick_interval(lat_ms)
        
        data[f.name]['method'] = method
        data[f.name]['interval'] = interval
        
        print(f'{f.name}: {lat_ms:.1f}ms → {method} (interval={interval*1000:.0f}ms)')

    # ========== 正式采样 ==========
    print("\n" + "=" * 60)
    print(f"正式采样：{args.rounds} 轮")
    print("=" * 60)
    
    for rnd in range(1, args.rounds + 1):
        print(f"\n----- 第 {rnd} 轮 -----")
        
        for f in file_list:
            restart_agens()
            sql = f.read_text().strip()
            method = data[f.name]['method']
            interval = data[f.name]['interval']
            
            if method == "cpu_times":
                result = measure_short_query(sql, DB_CONF, max_parallel)
            else:
                result = measure_long_query(sql, interval, DB_CONF, max_parallel)
            
            lat, cpu_t, cpu_pct, rss, peak_cpu, avg_cpu = result
            data[f.name]['samples'].append(result)
            
            print(f'{f.name}: lat={lat:.1f}ms cpu_time={cpu_t:.1f}ms '
                  f'cpu={cpu_pct:.1f}% rss={rss:.2f}GB peak={peak_cpu:.1f}%')
            
            # 每次测量后实时保存
            flush_csv(args.out, data, max_parallel)

    # ========== 完成 ==========
    print("\n" + "=" * 60)
    print(f"✅ 完成 → {args.out}")
    print("=" * 60)
    
    # 打印汇总
    print("\n📋 汇总结果：")
    print("-" * 100)
    print(f"{'file':<20} {'method':<10} {'latency_ms':>12} {'cpu_time_ms':>14} "
          f"{'cpu_%':>8} {'rss_gb':>8} {'peak_%':>8} {'avg_%':>8}")
    print("-" * 100)
    
    for fname, info in data.items():
        samples = info['samples']
        if samples:
            lat = statistics.median([s[0] for s in samples])
            cpu_t = statistics.median([s[1] for s in samples])
            cpu_pct = statistics.median([s[2] for s in samples])
            rss = statistics.median([s[3] for s in samples])
            peak = statistics.median([s[4] for s in samples])
            avg = statistics.median([s[5] for s in samples])
            print(f'{fname:<20} {info["method"]:<10} {lat:>12.1f} {cpu_t:>14.1f} '
                  f'{cpu_pct:>8.1f} {rss:>8.2f} {peak:>8.1f} {avg:>8.1f}')


if __name__ == '__main__':
    main()