#!/usr/bin/env python3
"""
ArangoDB AQL 资源占用采样脚本（优化版）
- 短查询（<500ms）：cpu_times 差值法
- 长查询（≥500ms）：采样法，最小间隔 50ms
- 所有指标取中位数

用法:
    python3 bench_arangodb_res.py queries/*.aql -n 5 -o result.csv
依赖:
    pip install python-arango psutil
"""
import argparse
import csv
import socket
import statistics
import subprocess
import threading
import time
from pathlib import Path

import psutil
from arango import ArangoClient
from arango.http import DefaultHTTPClient


# -------------------- 连接参数 --------------------
class MyHTTP(DefaultHTTPClient):
    REQUEST_TIMEOUT = 3600 * 6
    request_timeout = 3600 * 6


DB_CONF = dict(
    hosts='http://127.0.0.1:8529',
    username='root',
    password='linux123',
    dbname='openalex_middle',
    ip='127.0.0.1',
    port=8529
)

SHORT_QUERY_THRESHOLD_MS = 500
MIN_SAMPLE_INTERVAL = 0.05   # 50ms
MAX_SAMPLE_INTERVAL = 0.2    # 200ms
TARGET_SAMPLE_COUNT = 20


# -------------------- 工具函数 --------------------
def find_arangod_pid() -> int:
    """用 pgrep 取 arangod 主进程 PID"""
    try:
        out = subprocess.check_output(['pgrep', '-x', 'arangod'], text=True)
        return int(out.strip().split('\n')[0])
    except subprocess.CalledProcessError:
        raise RuntimeError('pgrep 找不到 arangod 进程')


def pick_interval(latency_ms: float) -> float:
    """
    根据查询延迟选择采样间隔
    - 最小 50ms（cpu_percent 准确性）
    - 最大 200ms
    - 目标采样 20 次
    """
    ideal = latency_ms / TARGET_SAMPLE_COUNT / 1000
    return max(MIN_SAMPLE_INTERVAL, min(MAX_SAMPLE_INTERVAL, ideal))


def restart_arangod(host=DB_CONF['ip'], port=DB_CONF['port'], max_wait=60):
    """重启 ArangoDB 服务"""
    print('♻️  restarting arangod …')
    subprocess.run(['sudo', 'systemctl', 'restart', 'arangodb3.service'], check=True)
    time.sleep(7)

    for _ in range(max_wait):
        try:
            with socket.create_connection((host, port), timeout=1):
                print('✅  arangod ready')
                return
        except (socket.error, OSError):
            time.sleep(1)
    raise RuntimeError('arangod 重启超时')


# -------------------- 短查询测量 --------------------
def measure_short_query(aql: str) -> tuple:
    """
    短查询：cpu_times 差值法（单进程）
    返回: (latency_ms, cpu_time_ms, cpu_%, peak_rss_gb, peak_cpu_%, avg_cpu_%)
    """
    pid = find_arangod_pid()
    proc = psutil.Process(pid)
    
    client = ArangoClient(hosts=DB_CONF['hosts'], http_client=MyHTTP())
    db = client.db(DB_CONF['dbname'], DB_CONF['username'], DB_CONF['password'])
    
    # 记录开始状态
    cpu_start = proc.cpu_times()
    rss_peak = proc.memory_info().rss
    t0 = time.perf_counter()
    
    # 执行查询
    cursor = db.aql.execute(
        aql, bind_vars={}, memory_limit=500 * 1024 ** 3,
        profile=False, cache=False, batch_size=None, stream=False
    )
    _ = cursor.batch()
    
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
    
    client.close()
    
    # 短查询无采样，peak 和 avg 都用计算值
    return (latency_ms, cpu_time_ms, cpu_percent, peak_rss_gb, cpu_percent, cpu_percent)


# -------------------- 长查询采样器 --------------------
class LongQuerySampler:
    """长查询采样器 - 实时累计 CPU 时间"""
    
    def __init__(self, pid: int, interval: float):
        self.pid = pid
        self.interval = interval
        self.proc = psutil.Process(pid)
        self.stop_flag = threading.Event()
        self.cpu_samples = []
        self.rss_samples = []
        
        # 初始化 cpu_percent
        self.proc.cpu_percent(interval=None)
        
        # CPU 时间累计
        self.cpu_times_last = self.proc.cpu_times()
        self.total_cpu_time = 0.0
        self.lock = threading.Lock()

    def _collect_cpu_delta(self) -> float:
        """收集 CPU 时间增量"""
        try:
            cpu_now = self.proc.cpu_times()
            delta = (cpu_now.user - self.cpu_times_last.user) + \
                    (cpu_now.system - self.cpu_times_last.system)
            self.cpu_times_last = cpu_now
            return max(0.0, delta)
        except psutil.NoSuchProcess:
            return 0.0

    def _loop(self):
        """采样循环"""
        while not self.stop_flag.is_set():
            try:
                cpu_pct = self.proc.cpu_percent(interval=None)
                rss = self.proc.memory_info().rss / (1024 ** 3)
                
                # 实时累计 CPU 时间
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
        
        # 最后收集一次 CPU 时间
        try:
            delta = self._collect_cpu_delta()
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


def measure_long_query(aql: str, interval: float) -> tuple:
    """
    长查询：采样法
    返回: (latency_ms, cpu_time_ms, cpu_%, peak_rss_gb, peak_cpu_%, avg_cpu_%)
    """
    pid = find_arangod_pid()
    
    client = ArangoClient(hosts=DB_CONF['hosts'], http_client=MyHTTP())
    db = client.db(DB_CONF['dbname'], DB_CONF['username'], DB_CONF['password'])

    with LongQuerySampler(pid, interval) as sampler:
        t0 = time.perf_counter()
        cursor = db.aql.execute(
            aql, bind_vars={}, memory_limit=500 * 1024 ** 3,
            profile=False, cache=False, batch_size=None, stream=False
        )
        _ = cursor.batch()
        t1 = time.perf_counter()

    latency_ms = (t1 - t0) * 1000
    cpu_time_ms = sampler.total_cpu_time_ms()
    
    # cpu_% 根据 cpu_time 计算
    cpu_percent = (cpu_time_ms / latency_ms) * 100 if latency_ms > 0 else 0.0
    
    client.close()
    
    return (latency_ms, cpu_time_ms, cpu_percent,
            sampler.peak_rss(), sampler.peak_cpu(), sampler.avg_cpu())


# -------------------- 预热查询 --------------------
def warmup_query(aql: str) -> float:
    """预热查询，返回延迟(ms)"""
    client = ArangoClient(hosts=DB_CONF['hosts'], http_client=MyHTTP())
    db = client.db(DB_CONF['dbname'], DB_CONF['username'], DB_CONF['password'])

    t0 = time.perf_counter()
    cursor = db.aql.execute(
        aql, bind_vars={}, memory_limit=500 * 1024 ** 3,
        profile=False, cache=False, batch_size=None, stream=False
    )
    _ = cursor.batch()
    lat_ms = (time.perf_counter() - t0) * 1000
    
    client.close()
    return lat_ms


# -------------------- CSV 输出 --------------------
def flush_csv(out: Path, data: dict):
    """实时写入 CSV"""
    header = [
        'file',
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
            rows.append([fname, method] + [''] * 6)
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


# -------------------- 主流程 --------------------
def main():
    parser = argparse.ArgumentParser(description='ArangoDB AQL 资源采样脚本')
    parser.add_argument('-n', '--rounds', type=int, default=5,
                        help='采样轮数 (默认: 5)')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出CSV路径 (默认: result.csv)')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='排除的文件名列表')
    parser.add_argument('files', nargs='+',
                        help='AQL文件列表')
    args = parser.parse_args()

    # 打印配置
    print("=" * 60)
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
        print('所有文件均被排除，无事可做。')
        return

    # 初始化数据结构
    data = {f.name: {'method': '', 'interval': 0.0, 'samples': []} for f in file_list}

    # ========== 预热轮：确定测量方法 ==========
    print("\n" + "=" * 60)
    print("预热轮：确定测量方法")
    print("=" * 60)
    
    for f in file_list:
        restart_arangod()
        aql = f.read_text().strip()
        lat_ms = warmup_query(aql)
        
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
            restart_arangod()
            aql = f.read_text().strip()
            method = data[f.name]['method']
            interval = data[f.name]['interval']
            
            if method == "cpu_times":
                result = measure_short_query(aql)
            else:
                result = measure_long_query(aql, interval)
            
            lat, cpu_t, cpu_pct, rss, peak_cpu, avg_cpu = result
            data[f.name]['samples'].append(result)
            
            print(f'{f.name}: lat={lat:.1f}ms cpu_time={cpu_t:.1f}ms '
                  f'cpu={cpu_pct:.1f}% rss={rss:.2f}GB peak={peak_cpu:.1f}%')
            
            flush_csv(args.out, data)

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