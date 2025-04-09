
```yaml
services:
  snowflake:
    image: jxch/snowflake  
    ports:
      - "5000:8000"  
    environment:
      DATACENTER_ID: 1           # 数据中心 ID
      WORK_ID: 1               # 工作节点 ID
      BUFFER_SIZE: 2000      # 每个号码缓冲池的大小
```


批量获取号码（post）：
```bash
curl --location 'http://localhost:5000/ids?count=20'
```


获取单个号码（get）：
```bash
curl --location 'http://localhost:5000/id'
```

