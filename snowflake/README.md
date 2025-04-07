
采用双Buffer缓冲区设计，采用gunicorn服务器，默认4个工作进程


```yaml
services:
  snowflake:
    image: jxch/snowflake  
    ports:
      - "5000:8000"  
    environment:
      DATACENTER_ID: 1           # 数据中心 ID
      WORKER_ID: 1               # 工作节点 ID
      LOGICAL_CLOCK: "true"      # 是否启用逻辑时钟 (1=启用, 0=禁用)
      BUFFER_CAPACITY: 2000      # 每个号码缓冲池的大小
```


批量获取号码（post）：
```bash
curl --location 'http://localhost:5000/ids' \
--header 'Content-Type: application/json' \
--data '{
    "amount": 1234
}'
```


获取单个号码（get）：
```bash
curl --location 'http://localhost:5000/id'
```


修改启动参数参考：
```dockerfile
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
```
