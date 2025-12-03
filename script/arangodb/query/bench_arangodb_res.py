#!/usr/bin/env python3
"""
ArangoDB AQL 资源占用采样脚本（每轮结束后重启 arangod，保证 RSS 冷启动基线）
用法:
    python3 bench_arangodb_res.py queries/*.aql -n 5 -o result.csv
依赖:
    pip install python-arango psutil
"""
import argparse
import csv
import statistics
import time
import threading
import psutil
import subprocess
import socket
import errno
from pathlib import Path
from arango import ArangoClient
from arango.http import DefaultHTTPClient

# -------------------- 连接参数 --------------------
class MyHTTP(DefaultHTTPClient):
    REQUEST_TIMEOUT = 3600 * 6
    request_timeout = 3600 * 6

DB_CONF = dict(hosts='http://127.0.0.1:8529',
               username='root', password='linux123',
               dbname='openalex_middle')

# -------------------- 采样器 --------------------
class QuerySampler:
    def __init__(self, pid: int, interval: float):
        self.pid = pid
        self.interval = interval
        self.proc = psutil.Process(pid)
        self.stop_flag = threading.Event()
        self.cpu_samples, self.rss_samples = [], []

    def _loop(self):
        try:
            self.proc.cpu_percent(None)  # 丢弃第一次
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
    if latency_ms <= 100:
        interval = 0.001
    elif latency_ms <= 10000:
        interval = 0.01
    else:
        interval = 0.1
    return min(interval, latency_ms / 5 / 1000)


def find_arangod_pid() -> int:
    """用 pgrep 取 arangod 主进程 PID"""
    try:
        out = subprocess.check_output(['pgrep', '-x', 'arangod'], text=True)
        # 如果机器里只有一个 arangod，直接返回
        return int(out.strip())
    except subprocess.CalledProcessError:
        raise RuntimeError('pgrep 找不到 arangod 进程，请手动 -p 指定 PID')


# -------------------- 重启 arangod --------------------
def restart_arangod(host='127.0.0.1', port=8529, max_wait=60):
    print('♻️  restarting arangod …')
    # --wait 表示 systemd 会阻塞到单元再次进入 active 且 ready
    subprocess.run([
        'sudo', 'systemctl', 'restart', 'arangodb3.service'
    ], check=True)
    time.sleep(7) # 给点时间让服务起来

    # 再简单确认端口
    for _ in range(max_wait):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((host, port))
            s.close()
            print('✅  arangod ready')
            return
        except (socket.error, errno.ECONNREFUSED):
            time.sleep(1)
    raise RuntimeError('arangod 重启超时')


# -------------------- 单次采样（新建连接 → 执行 → 关闭连接） --------------------
def sample_resource(aql: str, interval: float, pid: int = None):
    if pid is None:
        pid = find_arangod_pid()

    client = ArangoClient(hosts=DB_CONF['hosts'], http_client=MyHTTP())
    db = client.db(DB_CONF['dbname'], DB_CONF['username'], DB_CONF['password'])

    with QuerySampler(pid, interval) as sampler:
        cursor = db.aql.execute(
            aql, bind_vars={}, memory_limit=500*1024**3,
            profile=False, cache=False, batch_size=None, stream=False
        )
        _ = cursor.batch()          # 拉完结果

    pc, pr, ac = sampler.peak_cpu(), sampler.peak_rss(), sampler.avg_cpu()
    client.close()                  # 立即释放连接
    return pc, pr, ac


# -------------------- 主流程 --------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--rounds', type=int, default=5)
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('-p', '--pid', type=int, default=None,
                        help='手动指定 arangod 进程 PID；缺省则自动查找')
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()

    exclude_set = {Path(f).resolve() for f in args.exclude}
    file_list = sorted([Path(f) for f in args.files
                        if Path(f).resolve() not in exclude_set],
                       key=lambda p: p.name)
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    data = {f.name: [] for f in file_list}
    
    restart_arangod()

    # ---------- 第一轮：只测延迟，定档采样间隔 ----------
    for f in file_list:
        aql = f.read_text().strip()
        client = ArangoClient(hosts=DB_CONF['hosts'], http_client=MyHTTP())
        db = client.db(DB_CONF['dbname'], DB_CONF['username'], DB_CONF['password'])

        t0 = time.perf_counter()
        cursor = db.aql.execute(
            aql, bind_vars={}, memory_limit=500*1024**3,
            profile=False, cache=False, batch_size=None, stream=False
        )
        _ = cursor.batch()
        t1 = time.perf_counter()
        lat_ms = (t1 - t0) * 1000
        interval = pick_interval(lat_ms)
        print(f'{f.name} 定档延迟 {lat_ms:.3f} ms → 采样 {interval*1000:.0f} ms')
        data[f.name].append(('interval', lat_ms, interval))
        client.close()              # 立即释放

    # ---------- 第二轮及以后：正式采样资源 ----------
    for rnd in range(2, args.rounds + 2):
        for f in file_list:
            restart_arangod()
            aql = f.read_text().strip()
            _, _, interval = data[f.name][0]
            pc, pr, ac = sample_resource(aql, interval, args.pid)
            data[f.name].append((pc, pr, ac))
            print(f'R{rnd-1:02d}  {f.name}: '
                  f'peak_cpu={pc:.1f}% peak_rss={pr:.1f}GB avg_cpu={ac:.1f}%')
            flush_csv(args.out, data)

    print(f'资源采样完成 → {args.out}')


# -------------------- 实时落盘 --------------------
def flush_csv(out: Path, data: dict):
    header = ['file', 'first_lat_ms', 'sample_interval_ms',
              'peak_cpu_%', 'peak_rss_gb', 'avg_cpu_%']
    rows = []
    for fname, raw in data.items():
        first_lat, sample_interval = 0.0, 0.0
        samples = []
        for r in raw:
            if isinstance(r, tuple) and len(r) == 3 and r[0] == 'interval':
                first_lat, sample_interval = r[1], r[2]
            elif isinstance(r, tuple) and len(r) == 3:
                samples.append(r)
        if not samples:
            rows.append([fname, f'{first_lat:.3f}', f'{sample_interval*1000:.0f}',
                         '', '', ''])
            continue
        pcu = statistics.median([r[0] for r in samples])
        prss = statistics.median([r[1] for r in samples])
        acu = statistics.median([r[2] for r in samples])
        rows.append([fname,
                     f'{first_lat:.3f}',
                     f'{sample_interval*1000:.0f}',
                     f'{pcu:.1f}', f'{prss:.1f}', f'{acu:.1f}'])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as cf:
        csv.writer(cf).writerows([header] + rows)


if __name__ == '__main__':
    main()