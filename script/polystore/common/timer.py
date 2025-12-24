#!/usr/bin/env python3

import time
from typing import Dict, List, Optional


class MultiDatabaseTimer:
    """多数据库查询计时器，存储r/d/g/v四种类型的总耗时"""
    
    def __init__(self):
        self.clear()
        
    def clear(self):
        # r=关系型(PostgreSQL), d=文档型(MongoDB), g=图数据库(Neo4j), v=向量数据库(Milvus)
        self.times: Dict[str, float] = {'r': 0.0, 'd': 0.0, 'g': 0.0, 'v': 0.0}
        self._current_phase: Optional[str] = None
        self._start_time: Optional[float] = None
    
    def start_phase(self, phase_type: str):
        """开始一个新的计时阶段，phase_type必须是r/d/g/v之一"""
        if phase_type not in ['r', 'd', 'g', 'v']:
            raise ValueError(f"phase_type必须是r/d/g/v之一，当前值: {phase_type}")
        
        if self._current_phase is not None:
            self.stop_phase()
        
        self._current_phase = phase_type
        self._start_time = time.perf_counter()
    
    def stop_phase(self):
        """结束当前计时阶段并累加时间"""
        if self._current_phase is None or self._start_time is None:
            return
        
        elapsed = time.perf_counter() - self._start_time
        self.times[self._current_phase] += elapsed
        self._current_phase = None
        self._start_time = None
    
    def get_times_map(self) -> Dict[str, float]:
        """返回r/d/g/v的时间map（毫秒）"""
        # 如果有未结束的phase，先结束它
        if self._current_phase is not None:
            self.stop_phase()
        
        return {k: round(v * 1000, 2) for k, v in self.times.items()}


class TimerPhase:
    """自动计时上下文管理器"""
    def __init__(self, timer: Optional[MultiDatabaseTimer], phase_type: str):
        self.timer = timer
        self.phase_type = phase_type
    
    def __enter__(self):
        if self.timer is not None:
            self.timer.start_phase(self.phase_type)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.timer is not None:
            self.timer.stop_phase()