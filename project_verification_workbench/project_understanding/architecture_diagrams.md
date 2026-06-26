# 架构图

**创建时间**: 2026-06-26 20:35
**创建人**: Project Verifier Skill
**状态**: 完成

---

## 1. 系统架构图

```mermaid
flowchart TD
    %% 节点声明
    USER([用户])
    DASHBOARD[仪表盘]
    API[FastAPI服务器]
    CHAT[聊天服务]
    AGENT[Agent]
    TOOLS[工具集]
    RETRIEVER[混合检索器]
    VECTOR[(ChromaDB)]
    GRAPH[(Neo4j)]
    SEARCH[外部搜索]
    BRIEFS[Briefs]

    %% 连接关系
    USER --> DASHBOARD
    DASHBOARD --> API
    API --> CHAT
    CHAT --> AGENT
    AGENT --> TOOLS
    TOOLS --> RETRIEVER
    RETRIEVER --> VECTOR
    RETRIEVER --> GRAPH
    TOOLS --> SEARCH
    CHAT --> BRIEFS

    %% 样式
    classDef user fill:#dbeafe,stroke:#3b82f6,color:#111827
    classDef frontend fill:#dcfce7,stroke:#22c55e,color:#111827
    classDef backend fill:#fef3c7,stroke:#f59e0b,color:#111827
    classDef storage fill:#ede9fe,stroke:#8b5cf6,color:#111827
    classDef external fill:#fee2e2,stroke:#ef4444,color:#111827

    class USER user
    class DASHBOARD frontend
    class API,CHAT,AGENT,TOOLS backend
    class RETRIEVER,VECTOR,GRAPH storage
    class SEARCH external
```

---

## 2. 数据流图

```mermaid
flowchart LR
    %% 节点声明
    INPUT[用户输入]
    API[API端点]
    SERVICE[聊天服务]
    AGENT[Agent]
    TOOL[工具调用]
    RETRIEVE[检索]
    CITE[引用生成]
    OUTPUT[用户响应]

    %% 连接关系
    INPUT --> API
    API --> SERVICE
    SERVICE --> AGENT
    AGENT --> TOOL
    TOOL --> RETRIEVE
    RETRIEVE --> CITE
    CITE --> OUTPUT

    %% 样式
    classDef input fill:#dbeafe,stroke:#3b82f6,color:#111827
    classDef process fill:#dcfce7,stroke:#22c55e,color:#111827
    classDef output fill:#fef3c7,stroke:#f59e0b,color:#111827

    class INPUT input
    class API,SERVICE,AGENT,TOOL,RETRIEVE,CITE process
    class OUTPUT output
```

---

## 3. 模块依赖图

```mermaid
flowchart TD
    %% 节点声明
    SERVER[server.py]
    CHAT[chat_service.py]
    AGENT[agent.py]
    TOOLS[tools.py]
    HYBRID[hybrid.py]
    DRIVER[driver.py]
    CONFIG[config.py]
    METRICS[metrics.py]
    CONSISTENCY[consistency.py]

    %% 依赖关系
    SERVER --> CONFIG
    SERVER --> CHAT
    SERVER --> METRICS
    CHAT --> AGENT
    CHAT --> TOOLS
    CHAT --> HYBRID
    AGENT --> TOOLS
    TOOLS --> HYBRID
    TOOLS --> DRIVER
    HYBRID --> DRIVER

    %% 样式
    classDef server fill:#dbeafe,stroke:#3b82f6,color:#111827
    classDef service fill:#dcfce7,stroke:#22c55e,color:#111827
    classDef agent fill:#fef3c7,stroke:#f59e0b,color:#111827
    classDef storage fill:#ede9fe,stroke:#8b5cf6,color:#111827
    classDef util fill:#f1f5f9,stroke:#64748b,color:#111827

    class SERVER server
    class CHAT service
    class AGENT,TOOLS agent
    class HYBRID,DRIVER storage
    class CONFIG,METRICS,CONSISTENCY util
```

---

## 4. 安全架构图

```mermaid
flowchart TD
    %% 节点声明
    USER([用户])
    RATE[速率限制]
    AUTH[API Key认证]
    VALIDATE[输入验证]
    XSS[XSS防护]
    SRI[SRI校验]
    MASK[API Key掩码]
    TIMEOUT[超时保护]
    IMMUTABLE[不可变状态]

    %% 连接关系
    USER --> RATE
    RATE --> AUTH
    AUTH --> VALIDATE
    VALIDATE --> XSS
    XSS --> SRI
    SRI --> MASK
    MASK --> TIMEOUT
    TIMEOUT --> IMMUTABLE

    %% 样式
    classDef user fill:#dbeafe,stroke:#3b82f6,color:#111827
    classDef security fill:#fee2e2,stroke:#ef4444,color:#111827

    class USER user
    class RATE,AUTH,VALIDATE,XSS,SRI,MASK,TIMEOUT,IMMUTABLE security
```

---

## 5. 部署架构图

```mermaid
flowchart TD
    %% 节点声明
    USER([用户])
    BROWSER[浏览器]
    NGINX[Nginx]
    FASTAPI[FastAPI]
    NEO4J[Neo4j]
    CHROMA[ChromaDB]
    LLM[LLM API]
    SEARCH[搜索API]

    %% 连接关系
    USER --> BROWSER
    BROWSER --> NGINX
    NGINX --> FASTAPI
    FASTAPI --> NEO4J
    FASTAPI --> CHROMA
    FASTAPI --> LLM
    FASTAPI --> SEARCH

    %% 样式
    classDef user fill:#dbeafe,stroke:#3b82f6,color:#111827
    classDef frontend fill:#dcfce7,stroke:#22c55e,color:#111827
    classDef backend fill:#fef3c7,stroke:#f59e0b,color:#111827
    classDef storage fill:#ede9fe,stroke:#8b5cf6,color:#111827
    classDef external fill:#fee2e2,stroke:#ef4444,color:#111827

    class USER user
    class BROWSER frontend
    class NGINX,FASTAPI backend
    class NEO4J,CHROMA storage
    class LLM,SEARCH external
```

---

## 6. 更新日志

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-06-26 | v1.0 | 初始版本，完成架构图 |
