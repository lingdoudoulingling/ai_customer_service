基于deepagents的智能客服

## 安装依赖

```bash
pip install -r requirements.txt
```

## 服务启动

记忆管理依赖两个本地服务：

- `Postgres`：用于短期记忆、会话线程恢复、LangGraph checkpoint
- `Qdrant`：作为 `Mem0` 的向量存储

推荐流程：

1. 先启动 `Docker Desktop`
2. 确认 Docker 已就绪
3. 在项目根目录执行一键启动脚本

默认启动命令：

```powershell
.\start_memory_services.ps1
```

如果 PowerShell 限制脚本执行，可改用：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_memory_services.ps1
```

脚本会自动完成以下动作：

- 检查 Docker 是否可用
- 创建或启动 `ai-cs-postgres`
- 创建或启动 `ai-cs-qdrant`
- 等待服务端口可用

默认端口：

- `Postgres`：`5432`
- `Qdrant`：`6333`

如果本机 `5432` 已被占用，推荐改用自定义端口并强制重建容器：

```powershell
.\start_memory_services.ps1 -PostgresHostPort 15432 -ForceRecreate
```

同时把 `config.yaml` 中的 `POSTGRES_URL` 改为：

```yaml
POSTGRES_URL: "postgresql://postgres:postgres@localhost:15432/ai_customer_service"
```

服务启动成功后，控制台会看到类似输出：

```text
Postgres is ready on port 15432
Qdrant is ready on port 6333

All memory services are up.
Postgres: postgresql://postgres:postgres@localhost:15432/ai_customer_service
Qdrant:   http://localhost:6333
```

如果 Docker 没有启动，脚本会直接提示你先启动 Docker Desktop。

## 启动方式

确认以下条件满足后，再启动应用：

- `config.yaml` 已正确配置
- `Postgres` 和 `Qdrant` 已成功启动
- `POSTGRES_URL` 与实际端口一致

启动命令：

```bash
python app.py
```

程序启动后会先要求输入 `user_id`。`user_id` 用于隔离长期记忆。

如果这个 `user_id` 之前有会话记录，程序会提示选择会话模式：

- `new`：创建新会话
- `resume`：恢复旧会话

两种模式的区别：

- `new`
  - 生成新的 `thread_id`
  - 短期记忆从空白会话开始
  - 长期记忆仍然会按 `user_id` 召回
- `resume`
  - 继续使用历史 `thread_id`
  - 可恢复该线程下的短期上下文
  - 也会继续使用相同 `user_id` 的长期记忆

选择 `resume` 后：

- 直接回车：恢复上一次的 `thread_id`
- 手动输入：恢复指定的 `thread_id`

程序会打印当前的 `thread_id`，并把最近会话记录写入 `data/session_history.json`，方便后续恢复。

退出程序可输入：

```text
exit
```

## 测试用例

### 测试用例1：客户业务进度查询
- **用户输入**：查询客户id1009的业务办理进度
- **预期输出**：返回客户的宽带服务和手机服务的办理进度
- **验证点**：
  - 宽带服务状态为"已审核"，显示"已审核，等待安装排期"
  - 手机服务显示"未找到办理记录"

### 测试用例2：资源状态异常诊断（内验后资源仍在建）
- **用户输入**：查一下资源编码500135100000000013123839，项目已经内验了但资源系统里还是在建。
- **预期输出**：
  - 调用query_resource_system查询资源状态
  - 调用query_public_library查询内验状态
  - 调用query_resource_system_receive_log查询接收日志
  - 输出诊断结果，包含证据和建议
  - 询问用户是否提交工单
- **验证点**：
  - 资源系统状态显示"在建"
  - 公共库状态为"INNER_ACCEPTANCE_PASSED"但未转发
  - 接收日志显示未收到INNER_ACCEPTANCE报文

### 测试用例3：用户确认提交工单（HITL审批流程）
- **用户输入**（续用例2）：好的
- **预期输出**：
  - 调用build_manual_ticket_draft生成工单草稿
  - 触发人工审批（HITL）
  - 用户输入approve批准
  - 调用submit_manual_ticket提交工单
- **验证点**：
  - 工单成功提交，生成工单编号
  - 显示工单信息（编号、标题、目标团队）

### 测试用例4：利旧资源查找异常诊断
- **用户输入**：查不到利旧资产对应的资源，资产编码A00002493300
- **预期输出**：
  - 调用query_resource_system查询资产状态
  - 调用query_public_library查询公共库状态
  - 输出诊断结果，说明利旧资源查找异常原因
  - 建议处理方式
- **验证点**：
  - 资产编码A00002493300对应资源状态为"在网"
  - 绑定状态为"unbound"
  - PMS系统有发起利旧流程但未推送到资源系统

### 测试用例5：非业务问题处理
- **用户输入**：今天天气如何
- **预期输出**：回复无法获取天气信息，引导用户使用其他渠道
- **验证点**：
  - 不调用任何业务工具
  - 给出友好提示，说明无天气查询功能

### 测试用例6：历史上下文记忆
- **用户输入**（续用例4）：我想就刚才那个问题提交工单
- **预期输出**：
  - 系统识别"刚才那个问题"指的是利旧资源查找异常
  - 自动填充之前的诊断信息
  - 生成工单并提交
- **验证点**：
  - 工单标题正确反映利旧资源问题
  - 诊断记录包含之前的完整分析

### 测试用例7：LangGraph子智能体接入（电视套餐查询）
- **用户输入**：查询北京地区VIP客户可用的电视套餐
- **预期输出**：
  - 调用tv-package-query子智能体查询电视套餐
  - 返回VIP客户可用的电视套餐列表
- **验证点**：
  - 使用tv-package-query子智能体
  - 返回套餐名称、价格、包含内容等信息

## 长期记忆验证

本项目当前的记忆分层如下：

- 短期记忆：按 `thread_id` 隔离，保存在 `Postgres checkpoint`
- 长期记忆：按 `user_id` 隔离，保存在 `Mem0 + Qdrant`

因此验证长期记忆时，关键是：

- `user_id` 保持不变
- 可以重启 `app.py`
- 可以重新选择 `new`，故意生成新的 `thread_id`

### 场景1：重启后仍记住用户偏好

第一次启动应用，输入：

```text
请输入 user_id：zhangsan
请选择会话模式：new
用户：请记住：我是平台创新中心的张三，负责北京地区铁塔资源问题。以后回答请先给结论，再给依据。
```

看到助手正常回复后，输入：

```text
exit
```

再次启动应用，仍然使用相同 `user_id`，并选择 `new`：

```text
请输入 user_id：zhangsan
请选择会话模式：new
用户：你还记得我负责哪个区域吗？请按我的偏好回答。
```

预期结果：

- 能回答出“北京地区”
- 回答风格体现“先给结论，再给依据”
- 即使是新的 `thread_id`，长期记忆仍然生效

### 场景2：区分短期记忆和长期记忆

第一次启动时输入：

```text
请输入 user_id：zhangsan
请选择会话模式：new
用户：请记住：我偏好简洁回答。这次工单号是 T123456。
```

再次启动应用，使用相同 `user_id`，选择 `new`，再输入：

```text
用户：请按我的偏好回答。你还记得刚才的工单号吗？
```

预期结果：

- 助手应尽量体现“简洁回答”的偏好
- 不应把一次性的工单号 `T123456` 当作长期记忆稳定召回

### 场景3：恢复旧会话验证短期记忆

如果你想同时验证短期记忆，可以在同一个 `user_id` 下选择 `resume` 恢复之前的 `thread_id`。此时：

- 与当前任务直接相关的短期上下文应被恢复
- 长期记忆也仍然可用

也就是说：

- `new` 更适合验证长期记忆是否跨会话生效
- `resume` 更适合验证短期记忆是否按线程恢复

## todo-list

- [ ] 复杂场景意图识别功能
- [x] 槽位填充（当前由主智能体进行槽位填充）
- [x] 支持langraph子智能体
- [ ] 支持langfuse
- [x] 支持skills
- [x] 支持思考
- [ ] 支持流式输出
- [ ] 支持jinjia SOP流程模板
- [x] 支持记忆管理（Postgres Checkpoint + Mem0）
- [ ] 美观UI前端
- [ ] 前端支持流式输出
- [ ] 前端支持显示todo-list
