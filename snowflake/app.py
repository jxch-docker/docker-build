import os
import time
import threading
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from queue import SimpleQueue, Empty

load_dotenv()

DATACENTER_ID = int(os.getenv("DATACENTER_ID", "1"))
WORKER_ID = int(os.getenv("WORKER_ID", "1"))
LOGICAL_CLOCK = os.getenv("LOGICAL_CLOCK", "false").lower() == "true"
BUFFER_CAPACITY = int(os.getenv("BUFFER_CAPACITY", "2000"))

app = Flask(__name__)

# Snowflake 参数设置
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

# 全局逻辑时钟（仅在使用逻辑时钟模式下需要）
class AtomicTimestamp:
    def __init__(self):
        self.timestamp = int(time.time() * 1000)
  
    def get_and_increment(self, increment=1):
        # 利用 GIL 下的原子性，此处认为读写操作是安全的
        current = int(time.time() * 1000)
        if current > self.timestamp:
            self.timestamp = current
        else:
            self.timestamp += increment
        return self.timestamp

global_clock = AtomicTimestamp()

class DoubleBufferSnowflake:
    def __init__(self, datacenter_id, worker_id, buffer_capacity):
        self.datacenter_id = datacenter_id
        self.worker_id = worker_id
        self.buffer_capacity = buffer_capacity

        # 使用 SimpleQueue 作为线程安全（无显式锁）的队列
        self.active_queue = SimpleQueue()
        self.standby_queue = SimpleQueue()

        # 启动时同步预填充两个缓冲池
        self._fill_queue(self.active_queue, self.buffer_capacity)
        self._fill_queue(self.standby_queue, self.buffer_capacity)

    def _next_batch(self, amount):
        """
        批量生成 Snowflake ID，并返回列表
        """
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

    def _fill_queue(self, queue_obj, amount):
        """
        同步填充队列，将批量生成的 ID 放入队列中
        """
        for snowflake_id in self._next_batch(amount):
            queue_obj.put(snowflake_id)

    def _async_fill_queue(self, queue_obj, amount):
        """
        异步填充备用队列，方法内容与 _fill_queue 一致
        """
        try:
            self._fill_queue(queue_obj, amount)
        except Exception as e:
            # 这里可以增加错误日志
            print("备用缓冲池填充失败：", e)

    def _async_fill_standby(self):
        """
        异步填充备用缓冲池到指定容量，新构造一个 SimpleQueue 填满后替换
        """
        new_queue = SimpleQueue()
        self._async_fill_queue(new_queue, self.buffer_capacity)
        # 利用赋值替换 standby_queue，赋值在 CPython 下是原子操作
        self.standby_queue = new_queue

    def next_id(self):
        """
        获取单个 ID，整个流程均不显式使用锁
        """
        try:
            # 优先从 active_queue 获取
            return self.active_queue.get_nowait()
        except Empty:
            # active_queue 为空时尝试从 standby_queue 取一个
            try:
                _id = self.standby_queue.get_nowait()
                # 直接用 standby_queue 替换 active_queue
                self.active_queue = self.standby_queue
                # 异步填充备用缓冲池
                threading.Thread(target=self._async_fill_standby, daemon=True).start()
                return _id
            except Empty:
                # 两个缓冲池都空时，同步填充 active_queue
                new_queue = SimpleQueue()
                self._fill_queue(new_queue, self.buffer_capacity)
                self.active_queue = new_queue
                return self.next_id()

    def next_ids(self, amount):
        """
        批量获取 ID，不使用显式锁，同样靠内置队列保证线程安全
        """
        ids = []
        while amount > 0:
            try:
                # 尝试从 active_queue 非阻塞获取
                ids.append(self.active_queue.get_nowait())
                amount -= 1
            except Empty:
                try:
                    # active_queue 空时，尝试 standby_queue
                    _id = self.standby_queue.get_nowait()
                    ids.append(_id)
                    amount -= 1
                    # 替换 active_queue 为 standby_queue
                    self.active_queue = self.standby_queue
                    threading.Thread(target=self._async_fill_standby, daemon=True).start()
                except Empty:
                    # 两个缓冲池均空时，同步补充 active_queue
                    new_queue = SimpleQueue()
                    self._fill_queue(new_queue, self.buffer_capacity)
                    self.active_queue = new_queue
        return ids

# 使用双缓冲池版的 Snowflake 生成器实例
sf = DoubleBufferSnowflake(DATACENTER_ID, WORKER_ID, BUFFER_CAPACITY)

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