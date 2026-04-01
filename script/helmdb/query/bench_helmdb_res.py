#!/usr/bin/env python3
"""
openGauss/HelmDB 资源占用采样脚本（Python 3.6.8 兼容版）
- 兼容 CentOS 7 / RHEL 7 默认 Python 环境
- 修正了 subprocess 参数和类型注解
"""
import argparse
import csv
import socket
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Dict, Tuple, Set # Python 3.6 必须从 typing 导入

import psutil
import psycopg2

DB_CONF = dict(
    dbname='mapl',
    user='hyh',
    password='Linux123',
    host='127.0.0.1',
    port=9999
)

SHORT_QUERY_THRESHOLD_MS = 500
MIN_SAMPLE_INTERVAL = 0.05   # 50ms
MAX_SAMPLE_INTERVAL = 0.2    # 200ms
TARGET_SAMPLE_COUNT = 20


# -------------------- 兼容性工具函数 --------------------
def run_cmd_get_stdout(cmd: List[str]) -> str:
    """Python 3.6 兼容的 subprocess 调用，获取输出"""
    # 3.6 不支持 capture_output=True 和 text=True
    try:
        if sys.version_info >= (3, 7):
            return subprocess.check_output(cmd, text=True).strip()
        else:
            return subprocess.check_output(cmd, universal_newlines=True).strip()
    except subprocess.CalledProcessError:
        raise RuntimeError(f"命令执行失败: {' '.join(cmd)}")

def find_helmdb_pid() -> int:
    """查找 gaussdb 进程 PID"""
    try:
        # split('\n')[0] 确保只取第一行
        out = run_cmd_get_stdout(['pgrep', '-x', 'gaussdb', '-u', 'hyh'])
        if not out:
            raise RuntimeError("pgrep 返回为空")
        return int(out.split('\n')[0])
    except Exception:
        raise RuntimeError('pgrep 找不到 gaussdb 进程，请确认数据库已启动')


def pick_interval(latency_ms: float) -> float:
    ideal = latency_ms / TARGET_SAMPLE_COUNT / 1000
    return max(MIN_SAMPLE_INTERVAL, min(MAX_SAMPLE_INTERVAL, ideal))


def restart_helmdb(host=DB_CONF['host'], port=DB_CONF['port'], max_wait=60):
    """重启 openGauss 服务"""
    print('♻️  restarting openGauss …')
    # Python 3.6 run 也不支持 capture_output，直接调用即可
    subprocess.check_call(['sudo', 'systemctl', 'restart', 'opengauss.service'])
    
    time.sleep(20)

    for _ in range(max_wait):
        try:
            # socket 库在 3.6 是通用的
            with socket.create_connection((host, port), timeout=20):
                print('✅  openGauss ready')
                return
        except (socket.error, OSError):
            time.sleep(1)
    raise RuntimeError('openGauss 重启超时')


def setup_session(cur):
    """统一的会话设置"""
    cur.execute("SET enable_pbe_optimization = off")
    cur.execute("ALTER SYSTEM SET enable_global_plancache = off")


# -------------------- 短查询测量 --------------------
def measure_short_query(sql: str, conn_params: dict) -> tuple:
    """
    短查询：cpu_times 差值法
    """
    pid = find_helmdb_pid()
    proc = psutil.Process(pid)
    
    conn = psycopg2.connect(**conn_params)
    conn.autocommit = True
    cur = conn.cursor()
    setup_session(cur)
    
    # 记录开始状态
    try:
        cpu_start = proc.cpu_times()
        rss_peak = proc.memory_info().rss
    except psutil.NoSuchProcess:
        return (0, 0, 0, 0, 0, 0)

    t0 = time.perf_counter()
    
    # 执行查询
    cur.execute(sql)
    cur.fetchall()
    
    t1 = time.perf_counter()
    
    # 记录结束状态
    try:
        cpu_end = proc.cpu_times()
        rss_end = proc.memory_info().rss
        rss_peak = max(rss_peak, rss_end)
    except psutil.NoSuchProcess:
        cpu_end = cpu_start
    
    elapsed = t1 - t0
    latency_ms = elapsed * 1000
    cpu_time = (cpu_end.user - cpu_start.user) + (cpu_end.system - cpu_start.system)
    cpu_time_ms = cpu_time * 1000
    cpu_percent = (cpu_time_ms / latency_ms) * 100 if latency_ms > 0 else 0.0
    peak_rss_gb = rss_peak / (1024 ** 3)
    
    cur.close()
    conn.close()
    
    return (latency_ms, cpu_time_ms, cpu_percent, peak_rss_gb, cpu_percent, cpu_percent)


# -------------------- 长查询采样器 --------------------
class LongQuerySampler:
    """长查询采样器 - 实时累计 CPU 时间"""
    
    def __init__(self, pid: int, interval: float):
        self.pid = pid
        self.interval = interval
        self.proc = psutil.Process(pid)
        self.stop_flag = threading.Event()
        self.cpu_samples = [] # type: List[float]
        self.rss_samples = [] # type: List[float]
        
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
        self.thread = threading.Thread(target=self._loop)
        self.thread.daemon = True # Python 3.6 写法
        self.thread.start()
        return self

    def __exit__(self, *args):
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
        if not self.cpu_samples: return 0.0
        return max(self.cpu_samples)
    
    def peak_rss(self) -> float:
        if not self.rss_samples: return 0.0
        return max(self.rss_samples)
    
    def avg_cpu(self) -> float:
        if not self.cpu_samples: return 0.0
        return sum(self.cpu_samples) / len(self.cpu_samples)
    
    def total_cpu_time_ms(self) -> float:
        with self.lock:
            return self.total_cpu_time * 1000


def measure_long_query(sql: str, interval: float, conn_params: dict) -> tuple:
    pid = find_helmdb_pid()
    
    conn = psycopg2.connect(**conn_params)
    conn.autocommit = True
    cur = conn.cursor()
    setup_session(cur)

    with LongQuerySampler(pid, interval) as sampler:
        t0 = time.perf_counter()
        cur.execute(sql)
        cur.fetchall()
        t1 = time.perf_counter()

    latency_ms = (t1 - t0) * 1000
    cpu_time_ms = sampler.total_cpu_time_ms()
    
    cpu_percent = (cpu_time_ms / latency_ms) * 100 if latency_ms > 0 else 0.0
    
    cur.close()
    conn.close()
    
    return (latency_ms, cpu_time_ms, cpu_percent,
            sampler.peak_rss(), sampler.peak_cpu(), sampler.avg_cpu())


# -------------------- 预热查询 --------------------
def warmup_query(sql: str, conn_params: dict) -> float:
    conn = psycopg2.connect(**conn_params)
    conn.autocommit = True
    cur = conn.cursor()
    setup_session(cur)

    t0 = time.perf_counter()
    cur.execute(sql)
    cur.fetchall()
    lat_ms = (time.perf_counter() - t0) * 1000
    
    cur.close()
    conn.close()
    return lat_ms


# -------------------- CSV 输出 --------------------
def flush_csv(out: Path, data: dict):
    header = [
        'file', 'method', 'latency_ms', 'cpu_time_ms',
        'cpu_%', 'rss_gb', 'peak_cpu_%', 'avg_cpu_%'
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
            fname, method,
            f'{lat:.1f}', f'{cpu_time:.1f}', f'{cpu_pct:.1f}',
            f'{rss:.2f}', f'{peak_cpu:.1f}', f'{avg_cpu:.1f}'
        ])
    
    if not out.parent.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        
    with out.open('w', newline='') as f:
        csv.writer(f).writerows([header] + rows)


# -------------------- 主流程 --------------------
def main():
    parser = argparse.ArgumentParser(description='openGauss/HelmDB 资源采样')
    parser.add_argument('-n', '--rounds', type=int, default=5, help='采样轮数')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'), help='输出路径')
    parser.add_argument('-x', '--exclude', nargs='*', default=[], help='排除文件')
    parser.add_argument('files', nargs='+', help='SQL文件')
    args = parser.parse_args()

    # 打印配置 (Python 3.6 支持 f-string)
    print("=" * 60)
    print(f"📊 采样间隔范围: {MIN_SAMPLE_INTERVAL*1000:.0f}ms ~ {MAX_SAMPLE_INTERVAL*1000:.0f}ms")
    print(f"📊 短查询阈值: < {SHORT_QUERY_THRESHOLD_MS}ms 使用 cpu_times 差值法")
    print(f"📊 Python 版本: {sys.version}")
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

    # ========== 预热轮 ==========
    print("\n" + "=" * 60)
    print("预热轮：确定测量方法")
    print("=" * 60)
    
    for f in file_list:
        restart_helmdb()
        # Path.read_text() 在 3.5+ 可用
        sql = f.read_text().strip()
        lat_ms = warmup_query(sql, DB_CONF)
        
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
            restart_helmdb()
            sql = f.read_text().strip()
            method = data[f.name]['method']
            interval = data[f.name]['interval']
            
            if method == "cpu_times":
                result = measure_short_query(sql, DB_CONF)
            else:
                result = measure_long_query(sql, interval, DB_CONF)
            
            lat, cpu_t, cpu_pct, rss, peak_cpu, avg_cpu = result
            data[f.name]['samples'].append(result)
            
            print(f'{f.name}: lat={lat:.1f}ms cpu_time={cpu_t:.1f}ms '
                  f'cpu={cpu_pct:.1f}% rss={rss:.2f}GB peak={peak_cpu:.1f}%')
            
            flush_csv(args.out, data)

    print(f"\n✅ 完成 → {args.out}")


if __name__ == '__main__':
    main()