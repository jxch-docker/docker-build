import os
import time
import threading
from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()

DATACENTER_ID = int(os.getenv("DATACENTER_ID", "1"))
WORKER_ID = int(os.getenv("WORKER_ID", "1"))
LOGICAL_CLOCK = os.getenv("LOGICAL_CLOCK", "false").lower() == "true"

app = Flask(__name__)

# Snowflake 参数
EPOCH = 1609459200000  # 固定起始纪元 (2021-01-01)
datacenter_id_bits = 5
worker_id_bits = 5
sequence_bits = 12

max_datacenter_id = -1 ^ (-1 << datacenter_id_bits)
max_worker_id = -1 ^ (-1 << worker_id_bits)

assert 0 <= DATACENTER_ID <= max_datacenter_id
assert 0 <= WORKER_ID <= max_worker_id

worker_id_shift = sequence_bits
datacenter_id_shift = sequence_bits + worker_id_bits
timestamp_shift = sequence_bits + worker_id_bits + datacenter_id_bits
sequence_mask = -1 ^ (-1 << sequence_bits)

# 线程本地存储（避免显式锁）
thread_local = threading.local()

# 全局的逻辑时钟，使用原子性更新（Python中只能近似实现）
class AtomicTimestamp:
    def __init__(self):
        self.timestamp = int(time.time() * 1000)
        self.lock = threading.Lock()

    def get_and_increment(self, increment=1):
        with self.lock:
            current = int(time.time() * 1000)
            if current > self.timestamp:
                self.timestamp = current
            else:
                self.timestamp += increment
            return self.timestamp

global_clock = AtomicTimestamp()

# 核心无锁化Snowflake生成器（线程本地缓存 + 批量生成优化）
class LockFreeSnowflake:
    def __init__(self, datacenter_id, worker_id):
        self.datacenter_id = datacenter_id
        self.worker_id = worker_id

    def _next_batch(self, amount):
        # 批量预分配逻辑时钟，减少全局时钟竞争
        if LOGICAL_CLOCK:
            base_timestamp = global_clock.get_and_increment(amount)
        else:
            base_timestamp = int(time.time() * 1000)

        ids = []
        for i in range(amount):
            sequence = i & sequence_mask
            snowflake_id = ((base_timestamp - EPOCH) << timestamp_shift) | \
                           (self.datacenter_id << datacenter_id_shift) | \
                           (self.worker_id << worker_id_shift) | \
                           sequence
            ids.append(snowflake_id)
        return ids

    def next_id(self):
        cache = getattr(thread_local, 'cache', [])
        if not cache:
            cache = self._next_batch(1000)  # 每次缓存1000个, 大幅降低竞争
            thread_local.cache = cache
        return cache.pop()

    def next_ids(self, amount):
        ids = []
        while amount > 0:
            cache = getattr(thread_local, 'cache', [])
            if not cache:
                cache = self._next_batch(max(1000, amount))
                thread_local.cache = cache
            fetch_count = min(amount, len(cache))
            ids.extend(cache[-fetch_count:])
            thread_local.cache = cache[:-fetch_count]
            amount -= fetch_count
        return ids

sf = LockFreeSnowflake(DATACENTER_ID, WORKER_ID)

@app.route('/id', methods=['GET'])
def get_id():
    return jsonify({"id": sf.next_id()})

@app.route('/ids', methods=['POST'])
def get_ids():
    data = request.get_json()
    amount = data.get("amount", 1)
    if not isinstance(amount, int) or amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400
    ids = sf.next_ids(amount)
    return jsonify({"ids": ids})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)