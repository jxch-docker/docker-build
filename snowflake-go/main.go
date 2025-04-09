package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync/atomic"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/sony/sonyflake"
)

// LockFreeRingBuffer 使用原子操作实现无锁环形缓冲区
type LockFreeRingBuffer struct {
	buffer   []uint64 // 存储数据的数组
	capacity uint64   // 缓冲区总容量
	read     uint64   // 读索引（原子更新）
	write    uint64   // 写索引（原子更新）
}

// NewLockFreeRingBuffer 创建一个新的无锁环形缓冲区
func NewLockFreeRingBuffer(capacity uint64) *LockFreeRingBuffer {
	return &LockFreeRingBuffer{
		buffer:   make([]uint64, capacity),
		capacity: capacity,
		read:     0,
		write:    0,
	}
}

// IsFull 判断缓冲区是否已满
func (rb *LockFreeRingBuffer) IsFull() bool {
	return atomic.LoadUint64(&rb.write)-atomic.LoadUint64(&rb.read) >= rb.capacity
}

// IsEmpty 判断缓冲区是否为空
func (rb *LockFreeRingBuffer) IsEmpty() bool {
	return atomic.LoadUint64(&rb.write) == atomic.LoadUint64(&rb.read)
}

// Enqueue 尝试写入数据到缓冲区，写入成功返回 true，否则返回 false（缓冲区满）
func (rb *LockFreeRingBuffer) Enqueue(item uint64) bool {
	write := atomic.LoadUint64(&rb.write)
	read := atomic.LoadUint64(&rb.read)
	if write-read >= rb.capacity {
		// 缓冲区已满
		return false
	}
	// 写入数据到环形位置
	rb.buffer[write%rb.capacity] = item
	atomic.AddUint64(&rb.write, 1)
	return true
}

// Dequeue 从缓冲区取出一个数据，成功返回 (item, true)，否则返回 (0, false)
func (rb *LockFreeRingBuffer) Dequeue() (uint64, bool) {
	read := atomic.LoadUint64(&rb.read)
	write := atomic.LoadUint64(&rb.write)
	if read >= write {
		// 缓冲区为空
		return 0, false
	}
	item := rb.buffer[read%rb.capacity]
	atomic.AddUint64(&rb.read, 1)
	return item, true
}

// DoubleBuffer 使用两个无锁环形缓冲区构成双缓冲设计
type DoubleBuffer struct {
	buffers  [2]*LockFreeRingBuffer // 双缓冲数组
	active   int32                  // 当前活跃缓冲区索引（0 或 1），通过原子操作管理
	refilling [2]int32              // 每个缓冲区是否正在回填标识 0 - 未回填，1 - 正在回填
	sf       *sonyflake.Sonyflake   // Sonyflake 发号器实例
	size     uint64                 // 每个环形缓冲区的容量
	// refillThreshold 定义当缓冲区内剩余数据低于该阈值时触发回填
	refillThreshold uint64
}

// NewDoubleBuffer 初始化双缓冲区，先同步预填充两个缓冲区，然后后续通过异步回填触发
func NewDoubleBuffer(size uint64, sf *sonyflake.Sonyflake) *DoubleBuffer {
	db := &DoubleBuffer{
		buffers:  [2]*LockFreeRingBuffer{NewLockFreeRingBuffer(size), NewLockFreeRingBuffer(size)},
		active:   0,
		sf:       sf,
		size:     size,
		refillThreshold: size / 10, // 当剩余数据低于 10% 时触发回填
	}

	// 同步预填充两个缓冲区
	for i := 0; i < 2; i++ {
		db.syncFillBuffer(i)
	}
	return db
}

// syncFillBuffer 同步填充环形缓冲区直到满
func (db *DoubleBuffer) syncFillBuffer(idx int) {
	rb := db.buffers[idx]
	for !rb.IsFull() {
		id, err := db.sf.NextID()
		if err != nil {
			log.Printf("syncFillBuffer error on buffer %d: %v", idx, err)
			time.Sleep(1 * time.Millisecond)
			continue
		}
		rb.Enqueue(id)
	}
}

// asyncRefillBuffer 异步填充指定缓冲区（如果未在回填中）直到缓冲区满
func (db *DoubleBuffer) asyncRefillBuffer(idx int) {
	// 如果已经在回填，则直接返回
	if !atomic.CompareAndSwapInt32(&db.refilling[idx], 0, 1) {
		return
	}

	go func() {
		rb := db.buffers[idx]
		// 只要缓冲区未满，持续填充
		for !rb.IsFull() {
			id, err := db.sf.NextID()
			if err != nil {
				log.Printf("asyncRefillBuffer error on buffer %d: %v", idx, err)
				time.Sleep(1 * time.Millisecond)
				continue
			}
			if !rb.Enqueue(id) {
				// 若缓冲区满，退出循环
				break
			}
		}
		atomic.StoreInt32(&db.refilling[idx], 0)
	}()
}

// GetID 从当前活跃缓冲区中获取一个 ID  
// 如果活跃缓冲区为空，则切换到备用缓冲区，并异步回填被切换出去的缓冲区
func (db *DoubleBuffer) GetID() uint64 {
	current := atomic.LoadInt32(&db.active)
	if id, ok := db.buffers[current].Dequeue(); ok {
		// 若消费后，剩余数据不足，则异步触发回填
		rb := db.buffers[current]
		if atomic.LoadUint64(&rb.write)-atomic.LoadUint64(&rb.read) < db.refillThreshold {
			db.asyncRefillBuffer(int(current))
		}
		return id
	}

	// 活跃缓冲区没有数据，则切换到备用缓冲区
	standby := 1 - current
	atomic.StoreInt32(&db.active, standby)
	// 异步触发之前活跃缓冲区的回填操作
	db.asyncRefillBuffer(int(current))

	// 等待备用缓冲区有数据
	for {
		if id, ok := db.buffers[standby].Dequeue(); ok {
			// 读取成功后检查备用缓冲区是否需要补充
			rb := db.buffers[standby]
			if atomic.LoadUint64(&rb.write)-atomic.LoadUint64(&rb.read) < db.refillThreshold {
				db.asyncRefillBuffer(int(standby))
			}
			return id
		}
		time.Sleep(1 * time.Millisecond)
	}
}

func main() {
	// 通过环境变量读取配置：WORK_ID、DATACENTER_ID、BUFFER_SIZE 与 PORT
	workID, err := strconv.Atoi(os.Getenv("WORK_ID"))
	if err != nil || workID < 0 {
		workID = 1
	}
	datacenterID, err := strconv.Atoi(os.Getenv("DATACENTER_ID"))
	if err != nil || datacenterID < 0 {
		datacenterID = 1
	}
	bufferSize, err := strconv.Atoi(os.Getenv("BUFFER_SIZE"))
	if err != nil || bufferSize <= 0 {
		bufferSize = 10000
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	// 合拼 datacenterID 与 workID 生成唯一机器标识（假定均小于 100）
	machineID := uint16(datacenterID*100 + workID)

	// 配置 Sonyflake（StartTime 建议使用业务上线时间或相对固定时间）
	settings := sonyflake.Settings{
		StartTime: time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC),
		MachineID: func() (uint16, error) {
			return machineID, nil
		},
	}
	sf := sonyflake.NewSonyflake(settings)
	if sf == nil {
		log.Fatal("Failed to initialize Sonyflake")
	}

	// 初始化双缓冲区
	doubleBuffer := NewDoubleBuffer(uint64(bufferSize), sf)

	// 使用 Gin 提供 HTTP 接口
	router := gin.Default()

	// 单个 ID 接口：/id
	router.GET("/id", func(c *gin.Context) {
		id := doubleBuffer.GetID()
		c.JSON(http.StatusOK, gin.H{"id": id})
	})

	// 批量 ID 接口：/ids，默认返回 10 个，最多返回 100 个
	router.GET("/ids", func(c *gin.Context) {
		countStr := c.Query("count")
		count := 10
		if countStr != "" {
			if cnt, err := strconv.Atoi(countStr); err == nil && cnt > 0 {
				if cnt > 100 {
					count = 100
				} else {
					count = cnt
				}
			}
		}
		ids := make([]uint64, 0, count)
		for i := 0; i < count; i++ {
			ids = append(ids, doubleBuffer.GetID())
		}
		c.JSON(http.StatusOK, gin.H{"ids": ids})
	})

	// 健康检查接口
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	addr := fmt.Sprintf(":%s", port)
	log.Printf("Server running on %s", addr)
	router.Run(addr)
}