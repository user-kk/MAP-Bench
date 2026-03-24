#!/usr/bin/env python3
"""
Polystore 资源占用采样脚本（架构对齐 DuckDB 版 - 修复版）
- 执行模式：Python 子进程运行查询逻辑（客户端）
- 监控范围：Python 子进程 + 所有 Docker 容器进程
- 修正：确保在回收子进程前读取其最终资源消耗

用法:
    python3 bench_polystore_res.py query/*.py -n 5 -o result.csv -f docker-compose.yml
"""
import argparse
import csv
import importlib.util
import multiprocessing as mp
import os
import socket
import statistics
import subprocess
import sys
import threading
import time
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Set

import psutil

warnings.simplefilter("ignore", UserWarning)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_CONF = dict(
    host='127.0.0.1',
    pg_port=30000,
    mongo_port=30001,
    neo4j_port=30003,
    milvus_port=30004,
    user="root",
    pwd="linux123",
    db_name='mapl'
)

SHORT_QUERY_THRESHOLD_MS = 500
MIN_SAMPLE_INTERVAL = 0.05
MAX_SAMPLE_INTERVAL = 0.2
TARGET_SAMPLE_COUNT = 20


# -------------------- Docker 工具 --------------------
def get_container_name_by_port(target_port: int) -> Optional[str]:
    try:
        # 使用 inspect 也许更稳，但 ps grep 够用了
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}|{{.Ports}}'],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.strip().split('\n'):
            if not line or '|' not in line: continue
            name, ports = line.split('|', 1)
            if f':{target_port}->' in ports or f'0.0.0.0:{target_port}->' in ports:
                return name.strip()
    except: pass
    return None

def get_all_pids_in_container(container_name: str) -> Set[int]:
    pids = set()
    try:
        result = subprocess.run(
            ['docker', 'top', container_name, '-o', 'pid'],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.strip().split('\n')[1:]:
            if line.strip():
                pids.add(int(line.strip()))
    except: pass
    return pids

def get_backend_info() -> tuple[Set[int], List[str]]:
    pids = set()
    container_names = []
    port_map = [DB_CONF['pg_port'], DB_CONF['mongo_port'], 
                DB_CONF['neo4j_port'], DB_CONF['milvus_port']]
    
    for port in port_map:
        cname = get_container_name_by_port(port)
        if cname:
            container_names.append(cname)
            pids.update(get_all_pids_in_container(cname))
            
    return {p for p in pids if psutil.pid_exists(p)}, container_names


# -------------------- 子进程 Worker --------------------
def _worker(py_file: Path, ready_evt: mp.Event, start_evt: mp.Event, res_q: mp.Queue):
    """
    子进程：客户端逻辑
    """
    # 重新插入路径防止子进程丢失
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from common.context import Context

    try:
        # 加载模块
        mod_name = py_file.stem
        spec = importlib.util.spec_from_file_location(mod_name, py_file)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        func = getattr(mod, mod_name)

        # 初始化连接（不计入查询时间）
        ctx = Context(
            host=DB_CONF['host'], pg_port=DB_CONF['pg_port'],
            mongo_port=DB_CONF['mongo_port'], neo4j_port=DB_CONF['neo4j_port'],
            milvus_port=DB_CONF['milvus_port'], user=DB_CONF['user'], pwd=DB_CONF['pwd']
        )
        ctx.use(DB_CONF['db_name'])

        # 就绪
        ready_evt.set()
        start_evt.wait()

        # 执行并计时
        t0 = time.perf_counter()
        func(ctx)
        t1 = time.perf_counter()
        
        ctx.close()
        res_q.put((t1 - t0) * 1000)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        res_q.put(e)


# -------------------- 采样逻辑 --------------------
class PolystoreSampler:
    def __init__(self, worker_pid: int, backend_pids: Set[int], interval: float, container_names: List[str]):
        self.interval = interval
        self.container_names = container_names
        self.stop_flag = threading.Event()
        self.cpu_samples = []
        self.rss_samples = []
        
        # 监控列表：Worker + Docker Backend
        all_pids = {worker_pid} | backend_pids
        self.procs = {}
        for pid in all_pids:
            try:
                p = psutil.Process(pid)
                p.cpu_percent(interval=None)
                self.procs[pid] = p
            except psutil.NoSuchProcess: pass
        
        self.cpu_times_last = {pid: p.cpu_times() for pid, p in self.procs.items()}
        self.total_cpu_time = 0.0
        self.lock = threading.Lock()

    def _refresh_containers(self):
        for cname in self.container_names:
            new_pids = get_all_pids_in_container(cname)
            for pid in new_pids:
                if pid not in self.procs:
                    try:
                        p = psutil.Process(pid)
                        p.cpu_percent(interval=None)
                        self.procs[pid] = p
                        self.cpu_times_last[pid] = p.cpu_times()
                    except: pass

    def _collect_delta(self, pid, proc):
        try:
            now = proc.cpu_times()
            last = self.cpu_times_last.get(pid)
            if last:
                delta = (now.user - last.user) + (now.system - last.system)
            else:
                delta = 0.0
            self.cpu_times_last[pid] = now
            return max(0.0, delta)
        except: return 0.0

    def _loop(self):
        step = 0
        while not self.stop_flag.is_set():
            if step % 10 == 0: self._refresh_containers()
            step += 1

            total_pct, total_rss = 0.0, 0
            dead = []

            for pid, proc in list(self.procs.items()):
                try:
                    total_pct += proc.cpu_percent(interval=None)
                    total_rss += proc.memory_info().rss
                    delta = self._collect_delta(pid, proc)
                    with self.lock: self.total_cpu_time += delta
                except psutil.NoSuchProcess:
                    dead.append(pid)
            
            for pid in dead:
                self.procs.pop(pid, None)
                self.cpu_times_last.pop(pid, None)

            if not self.stop_flag.is_set():
                self.cpu_samples.append(total_pct)
                self.rss_samples.append(total_rss / (1024**3))
            
            time.sleep(self.interval)

    def __enter__(self):
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_flag.set()
        self.thread.join()
        for pid, proc in list(self.procs.items()):
            delta = self._collect_delta(pid, proc)
            with self.lock: self.total_cpu_time += delta

    def peak_rss(self): return max(self.rss_samples, default=0.0)
    def peak_cpu(self): return max(self.cpu_samples, default=0.0)
    def avg_cpu(self): return sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0
    def total_cpu_time_ms(self):
        with self.lock: return self.total_cpu_time * 1000


# -------------------- 核心测量函数 --------------------
def measure_short_query(py_file: Path) -> tuple:
    """短查询：精确测量 (修正了进程退出读不到数据的问题)"""
    ready_evt = mp.Event()
    start_evt = mp.Event()
    res_q = mp.Queue()

    p = mp.Process(target=_worker, args=(py_file, ready_evt, start_evt, res_q))
    p.start()
    
    # 1. 等待导入和连接
    ready_evt.wait()

    # 2. 获取所有 PID (Worker + Docker Backends)
    backend_pids, _ = get_backend_info()
    all_pids = backend_pids | {p.pid}
    procs = {pid: psutil.Process(pid) for pid in all_pids if psutil.pid_exists(pid)}

    # 3. 记录初始状态
    cpu_start = {}
    rss_peak = 0
    for pid, proc in procs.items():
        try:
            cpu_start[pid] = proc.cpu_times()
            rss_peak += proc.memory_info().rss
        except: pass

    # 4. 启动查询
    start_evt.set()

    # 5. 等待结果 (阻塞直到 Worker 完成)
    #    此时 Worker 处于 Zombie 状态 (已结束但未 join)，数据仍可读取
    result = res_q.get()
    
    # 6. 立即读取结束状态
    total_cpu_time = 0.0
    for pid, proc in procs.items():
        try:
            # 持续采样 RSS 峰值 (防止最后时刻内存飙升)
            rss_peak = max(rss_peak, proc.memory_info().rss)
            
            # 计算 CPU 差值
            end = proc.cpu_times()
            start = cpu_start.get(pid)
            if start:
                total_cpu_time += (end.user - start.user) + (end.system - start.system)
        except psutil.NoSuchProcess:
            # 只有极少数情况会在这里丢失数据
            pass

    # 7. 回收子进程
    p.join()

    if isinstance(result, Exception): raise result
    
    latency_ms = result
    cpu_time_ms = total_cpu_time * 1000
    cpu_percent = (cpu_time_ms / latency_ms) * 100 if latency_ms > 0 else 0.0
    
    return (latency_ms, cpu_time_ms, cpu_percent, rss_peak/(1024**3), cpu_percent, cpu_percent)


def measure_long_query(py_file: Path, interval: float) -> tuple:
    """长查询：采样线程"""
    ready_evt = mp.Event()
    start_evt = mp.Event()
    res_q = mp.Queue()

    p = mp.Process(target=_worker, args=(py_file, ready_evt, start_evt, res_q))
    p.start()
    ready_evt.wait()

    backend_pids, container_names = get_backend_info()
    
    # 采样器会同时监控 p.pid 和后端进程
    with PolystoreSampler(p.pid, backend_pids, interval, container_names) as sampler:
        start_evt.set()
        # 阻塞等待结果
        result = res_q.get()
        # 在 join 之前，Sampler 上下文管理器退出会自动做最后一次采集
    
    p.join()

    if isinstance(result, Exception): raise result
    
    latency_ms = result
    cpu_time_ms = sampler.total_cpu_time_ms()
    cpu_percent = (cpu_time_ms / latency_ms) * 100 if latency_ms > 0 else 0.0

    return (latency_ms, cpu_time_ms, cpu_percent, 
            sampler.peak_rss(), sampler.peak_cpu(), sampler.avg_cpu())


def warmup_query(py_file: Path) -> float:
    ready_evt = mp.Event()
    start_evt = mp.Event()
    res_q = mp.Queue()
    p = mp.Process(target=_worker, args=(py_file, ready_evt, start_evt, res_q))
    p.start()
    ready_evt.wait()
    start_evt.set()
    res = res_q.get()
    p.join()
    if isinstance(res, Exception): raise res
    return res


# -------------------- 主流程 --------------------
def pick_interval(latency_ms: float) -> float:
    ideal = latency_ms / TARGET_SAMPLE_COUNT / 1000
    return max(MIN_SAMPLE_INTERVAL, min(MAX_SAMPLE_INTERVAL, ideal))

def restart_polystore(compose_file: Path, max_wait=120):
    print(f'♻️  重启 Polystore ...')
    subprocess.run(['docker', 'compose', '-f', str(compose_file), 'restart'], 
                   check=True, capture_output=True)
    
    ports = [DB_CONF['pg_port'], DB_CONF['mongo_port'], 
             DB_CONF['neo4j_port'], DB_CONF['milvus_port']]
    
    time.sleep(60)
    for port in ports:
        for _ in range(max_wait):
            try:
                with socket.create_connection((DB_CONF['host'], port), timeout=20):
                    break
            except: time.sleep(1)
        else: raise RuntimeError(f'端口 {port} 超时')
    print('✅  就绪')

def flush_csv(out: Path, data: dict):
    header = ['file', 'method', 'latency_ms', 'cpu_time_ms', 
              'cpu_%', 'rss_gb', 'peak_cpu_%', 'avg_cpu_%']
    rows = []
    for fname, info in data.items():
        if not info['samples']:
            rows.append([fname, info['method']] + ['']*6)
            continue
        
        medians = [statistics.median([s[i] for s in info['samples']]) for i in range(6)]
        rows.append([fname, info['method']] + [f'{v:.1f}' if i!=3 else f'{v:.2f}' for i,v in enumerate(medians)])
    
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as f:
        csv.writer(f).writerows([header] + rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--rounds', type=int, default=5)
    parser.add_argument('-o', '--out', type=Path, default=Path('polystore_result.csv'))
    parser.add_argument('-f', '--compose-file', type=Path, default=Path('docker-compose.yml'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()

    exclude = {Path(f).name for f in args.exclude}
    files = sorted([Path(f).resolve() for f in args.files if Path(f).name not in exclude], key=lambda p:p.name)
    data = {f.name: {'method': '', 'interval': 0.0, 'samples': []} for f in files}

    print("="*60 + "\n预热轮\n" + "="*60)
    for f in files:
        restart_polystore(args.compose_file)
        try:
            lat = warmup_query(f)
            method = "cpu_times" if lat < SHORT_QUERY_THRESHOLD_MS else "sampling"
            data[f.name].update({'method': method, 'interval': pick_interval(lat)})
            print(f'{f.name}: {lat:.1f}ms → {method}')
        except Exception as e:
            print(f'❌ {f.name}: {e}')

    print("\n" + "="*60 + "\n正式采样\n" + "="*60)
    for rnd in range(1, args.rounds + 1):
        print(f"\n----- 第 {rnd} 轮 -----")
        for f in files:
            restart_polystore(args.compose_file)
            try:
                info = data[f.name]
                if info['method'] == "cpu_times":
                    res = measure_short_query(f)
                else:
                    res = measure_long_query(f, info['interval'])
                
                info['samples'].append(res)
                print(f'{f.name}: lat={res[0]:.1f}ms cpu_time={res[1]:.1f}ms cpu={res[2]:.1f}% rss={res[3]:.2f}GB')
                flush_csv(args.out, data)
            except Exception as e:
                print(f'❌ {f.name}: {e}')

    print(f'\n✅ 完成 → {args.out}')

if __name__ == '__main__':
    main()