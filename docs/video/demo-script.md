# HomeHub 十分钟演示视频计划书

## 目标与成片形式

目标：让老师在十分钟内看懂 HomeHub 的用途、微服务边界、REST 调用、Kubernetes 部署、持久化和独立扩容，并看到真实运行证据。

建议成片 **9 分 40 秒**，预留 20 秒给页面加载、口误或转场，总长不要超过 10 分钟。采用屏幕录制加旁白：浏览器、终端和代码编辑器三个窗口即可。可用本计划组织中文排练；正式旁白按课程要求选择语言。

演示环境固定为本地 OrbStack Kubernetes，页面为 `http://localhost:30080/`。
Compose 的 `http://localhost:8080/` 是另一套数据，本视频不要混用。

当前发布：前端 `0.2.2`，后端 `0.2.0`；Docker Hub 用户 `kar1n1911`。

## 分钟安排与现场动作

| 时间 | 画面与动作 | 要讲清楚的内容 | 对应证据 |
|---|---|---|---|
| 00:00–00:40 | 打开 Overview 首页，指出汇总及 Tasks、Devices 页面入口 | 家庭成员用一个页面管理共享任务与模拟设备；设备读数由后台采集并发送给 HTTP 接收端 | 软件用途、浏览器访问 |
| 00:40–01:40 | 展示架构图，沿浏览器到数据库、设备到接收端两条路径讲解 | 各服务职责、REST、独立部署；数据库单独运行，业务拥有独立数据库和账号 | 架构与组件映射 |
| 01:40–02:30 | 终端显示 context、Deployments、Pods、Services、PVC、数据库集群 | 当前确实在 Kubernetes 运行；NodePort 是外部入口；三个数据库实例及各自持久卷 | Kubernetes、持久化、外部访问 |
| 02:30–04:00 | 切换 Tasks，点击 Add task，创建任务，勾选完成，切换 Completed，刷新确认仍完成 | 请求经 Nginx 到 Task REST API，写入 PostgreSQL；刷新后从服务端重新读取 | 提供/调用 REST、真实业务流程 |
| 04:00–05:05 | 切换 Devices，点击 Add device，填写名称、房间、读数和采样间隔，保存；展开对应信号 JSON，刷新 | Device API 保存设备和待发送记录；后台错峰采样、抑制不变读数；JSON 携带唯一 ID 并投递 | 设备入口、服务间交互 |
| 05:05–05:55 | 查看浏览器 Network 中的一次 API 请求，展示相关 fetch 代码和 API 日志 | 前端以代码调用 REST；服务提供 JSON 接口；日志能对应刚才的操作 | 编程调用 REST、日志输出 |
| 05:55–07:15 | 编辑器依次展示 frontend、task-service、数据库和扩容 YAML 的关键字段 | Deployment/Service、探针、Secret 引用、PVC、CPU HPA、KEDA 队列扩容 | YAML 讲解、部署细节 |
| 07:15–08:05 | 单独将 frontend 从 2 扩至 3，展示其他服务副本数未被一起修改；恢复 2 | 应用副本无本地业务状态，因此可独立水平扩容；不同服务按各自负载扩容 | 独立扩容现场证据 |
| 08:05–09:05 | 回到架构图，简要展示已有数据库 HA/信号恢复验证记录 | 可用性与成本取舍、安全措施、尚未解决的问题；历史测试不冒充本次现场测试 | 收益、挑战、安全讨论 |
| 09:05–09:40 | 展示 GitHub 仓库与 Docker Hub 镜像，结束于可操作的首页 | 源码和 Kubernetes 配置的位置、镜像可拉取；总结已验证的核心流程 | 配置管理仓库、镜像发布 |
| 09:40–10:00 | 缓冲，不安排新内容 | 加载延迟和自然停顿 | 控制总时长 |

## 每段旁白要点

### 1. 开场：解决什么问题

“HomeHub 是一个家庭协作应用，可以管理共享任务、登记模拟设备，并查看设备信号的传输状态。这个演示通过浏览器访问运行在 Kubernetes 中的服务。”

不要花时间介绍配色或前端评分；这些不是本次作业的核心证据。

### 2. 架构：按两条请求路径讲

展示 `docs/architecture/architecture.md` 和 `docs/architecture/device-signals.md` 中的图，录制前在支持 Mermaid 的预览中打开。

| 组件 | 职责和微服务实现 |
|---|---|
| React / Nginx frontend | 页面和同源 API 反向代理；NodePort 30080 |
| household-service | 家庭与成员 REST API |
| task-service | 任务 REST API、创建与完成状态持久化 |
| device-service | 设备 REST API、模拟读数、采样计划、事务性 outbox |
| Alertmanager collector/API | 领取设备待发送记录、持久化队列、提供状态 REST API |
| signal-worker | 领取队列任务，将 JSON 发送到接收端；KEDA 按需启停 |
| signal-receiver | HTTP REST 接收端，按消息 ID 去重并持久化 |
| CloudNativePG / PostgreSQL | 单独运行的三实例数据库集群；每个实例一个 PVC |

两条路径：

1. 浏览器 → Nginx → Task API → Task 数据库 → JSON 响应。
2. Device API 的状态和 outbox → collector → 持久队列 → worker → HTTP receiver → 去重存储。

明确说明：这是**项目自定义的 Alertmanager，不是 Prometheus Alertmanager**。
Collector、worker、receiver 复用同一镜像，但作为不同执行角色部署；因此镜像数量不等于 Deployment 数量。

### 3. 任务操作：展示最完整的业务闭环

- 新任务名称：`Prepare the weekly shopping list`。
- Priority 选 High；日期可留空，减少录制操作。
- 点击 Create task，说明 POST 请求创建记录。
- 勾选完成，说明 PATCH 请求修改记录。
- 点击 Completed，刷新，再确认这条任务仍处于完成状态。

刷新只能证明服务端保存了数据，**不能单独证明数据库在基础设施重启后仍保留数据**。后面还要展示 PVC 配置及已完成的数据库恢复验证记录。

### 4. 添加设备与 JSON

准备以下表单值：

| 字段 | 演示值 |
|---|---|
| Device name | Demo kitchen sensor |
| Room | Kitchen |
| Initial reading | 22.5 C |
| Sampling interval | 30 秒 |

保存后先展示设备卡片，再查看 Signal delivery。若默认三条中没有该设备，点击 Show all recent signals 后找到对应记录。

展开 JSON，只指出 `id`、`time`、`source` 和 `data`。不要逐行念完整报文。

旁白要点：

- 设备创建时会立即生成第一条信号，不需要等完整采样周期。
- 不同设备的采样时间错开；多个 collector 通过数据库领取任务，减少重复抓取。
- 读数未变化时不反复发送，但会按规则发送心跳。
- 队列保存在数据库中；失败会重试，接收端通过唯一 ID 去重。
- 这是 **at-least-once 传输、接收端去重**，不能称为网络层 exactly-once，也不能保证任何灾难下都不丢数据。
- JSON 是编码格式，不是加密。

worker 可能需要等待 KEDA 激活。等待时先讲上述机制；若还没有 Delivered，展示 Pending 并说明后台处理中，稍后返回确认。不要把 Pending 解说成成功投递。

### 5. REST 和日志

录制前打开浏览器开发者工具 Network，保留一次任务 POST/PATCH 的记录。展示请求方法、路径、状态码和 JSON，即可证明页面实际调用了 API。

代码编辑器预先定位：

- `frontend/src/App.jsx`：`saveTask()` 中的 `fetch`，展示前端程序化调用 REST。
- `services/task-service/app/main.py`：任务路由，展示自己实现的 REST API。

随后在终端看 `task-service` 日志。多副本请求可能落到任意 Pod，使用后面的标签日志命令，不要只查看一个随机 Pod。

### 6. YAML：只讲关键字段

预先打开文件，避免现场查找：

1. `kubernetes/frontend/deployment.yaml`：`image`、`replicas`、`imagePullPolicy`、NodePort `30080`。
2. `kubernetes/task-service/deployment.yaml`：探针、资源限制、独立 Secret 引用。
3. `kubernetes/postgres/postgres.yaml`：`instances: 3`、`storage.size`、同步复制、角色访问限制。
4. `kubernetes/config/hpa.yaml`：不同 API 的 CPU 扩容范围。
5. `kubernetes/config/signal-scaling.yaml`：队列深度指标、worker `0–4`、冷却时间。

说明本机使用 `kubernetes-local/` overlay，允许数据库副本位于同一个节点；正式基础配置要求跨节点。**单机三副本不等于能抵御整台电脑故障。**

### 7. 独立扩容

现场扩容 frontend，它没有被当前 CPU HPA 管理，手动演示不容易被自动缩回。展示 frontend 的副本数变化，同时 task/device 等服务的目标副本数没有因这条命令一起改变。

KEDA 的完整故障注入、积压、扩至多个 worker、恢复、缩零测试不安排现场完整运行，避免占满视频时间。可以展示 `docs/verification/signal-scaling.json`，明确说这是提前执行并保存的测试结果，展示其记录的日期。

### 8. 收益、挑战和安全

用一分钟讲四个重点：

- **收益与业务价值**：任务和设备处理可以分别发布和扩容，高设备流量不必要求所有组件同时增加副本；数据库故障切换和持久队列有助于降低中断影响。
- **代价**：服务发现、日志追踪、数据库连接和队列管理增加复杂度；三数据库实例与多个基础副本存在持续资源成本。家庭演示规模本身不需要这种架构，可以假设部署给大量家庭或设备群来说明扩容价值，但当前版本并未实现多租户隔离。
- **已做安全措施**：数据库账号/数据库按服务隔离、限制角色权限、数据库 TLS 校验、Secret 引用、内部信号端点令牌。不要展示 Secret 内容、`.secrets/` 或完整环境变量。
- **仍需改进**：用户认证授权、浏览器入口 HTTPS、NetworkPolicy、服务身份与 mTLS、异地备份。队列及去重记录还需要保留/归档策略；同步复制不是备份。

展示 `docs/verification/database-ha.md` 或对应 JSON 中的数据库 Pod 故障恢复证据。明确说明“这是之前的测试记录”，不要在十分钟主片中临时删除数据库主节点。

### 9. 仓库与镜像

展示 GitHub：<https://github.com/kar1n1911/HomeHub>，指出 `frontend/`、`services/`、`kubernetes/` 和 `kubernetes-local/`。

Docker Hub 已使用五个应用镜像：

- `kar1n1911/homehub-frontend:0.2.2`
- `kar1n1911/homehub-household:0.2.0`
- `kar1n1911/homehub-task:0.2.0`
- `kar1n1911/homehub-device:0.2.0`
- `kar1n1911/homehub-alertmanager:0.2.0`

可以展示 `docs/verification/release-images.json` 与 `release-node-pull.json` 作为发布和节点拉取的历史验证记录。录制前重新核对仓库和运行镜像，若版本更新，以当时实际结果为准。

## 录制前准备，放在视频之外完成

- 确认 OrbStack、Kubernetes、CloudNativePG、KEDA 已运行，浏览器页面可访问。
- 不要在录制前执行 cleanup 脚本。如果之前清理过，先恢复应用并等待就绪。
- 不在十分钟内安装 operator、构建镜像或等待数据库初始化。
- 提前打开：首页、Network、终端、架构图预览、五个 YAML 文件、GitHub、镜像/故障验证记录。
- 浏览器缩放到内容清晰可读的比例，终端字体适当放大，关闭私人通知。
- 预演任务和设备操作；正式录制换一个可辨认的新名称，避免和旧记录混淆。
- 检查录屏音频，先录 20 秒回放，确认文字和旁白都清楚。
- 完成一次计时彩排。若超时，优先减少原理细节，不删掉任务闭环、日志和 YAML。

### 终端准备命令

在项目根目录执行。以下函数将每次操作固定到演示集群和命名空间，不修改全局 current-context：

```bash
cd /Users/coleanderson/Sync/HomeWorks/PA2577/HomeHub
k() { kubectl --context orbstack -n homehub "$@"; }

# 录制前检查
kubectl config get-contexts orbstack
k get deployments,pods,services,pvc
k get clusters.postgresql.cnpg.io
k get hpa,scaledobjects

# 仅在应用先前已被清理时恢复；在开录前完成
kubectl --context orbstack apply -k kubernetes-local/
k rollout status deployment/frontend --timeout=120s
k rollout status deployment/task-service --timeout=120s
k rollout status deployment/device-service --timeout=120s
```

所有服务还应通过首页实际读写确认，单独 frontend Ready 不代表下游全部可用。

### 录制时备用命令

```bash
# 部署现场证据
k get deployments
k get pods
k get services,pvc
k get clusters.postgresql.cnpg.io

# HTTP REST 读取，可在 Network 不便展示时补充
curl -sS http://localhost:30080/api/tasks | python3 -m json.tool

# 显示所有任务服务副本的最近日志
k logs -l app=task-service --all-containers=true --prefix=true --tail=10 --max-log-requests=10

# 仅扩容 frontend，随后恢复
k scale deployment/frontend --replicas=3
k rollout status deployment/frontend --timeout=60s
k get deployments
k scale deployment/frontend --replicas=2
k rollout status deployment/frontend --timeout=60s
```

自动扩容状态可能正在变化；如出现 HPA 指标 `<unknown>`，录制前诊断 Metrics Server，不能声称 CPU 自动扩容已现场验证。

## 时间不足或临时异常时

| 情况 | 处理 |
|---|---|
| 信号暂时 Pending | 先讲队列与重试，再返回查看；如仍未成功，如实说明，修复后重录该段 |
| worker 当前为 0 | 这是无积压时的设计行为，不是故障；collector/API 仍运行 |
| 扩容耗时超过预算 | 提前预拉镜像并彩排；若仍失败，保留真实状态，排查后重录，不伪造就绪 |
| 日志没有刚才的请求 | 查看所有 task-service 副本日志，确认使用的是 30080 页面 |
| 视频超过 10 分钟 | 缩短开场、JSON 字段和细节解释；不删课程明确要求的日志/YAML/浏览器操作 |
| 想展示更多故障实验 | 放到补充视频或文档；主片引用有日期的结果并明确证据来源 |

## 提交前核对

- [ ] 成片为 5–10 分钟，建议约 9:40。
- [ ] 说明应用 idea、组件职责和交互。
- [ ] 真实展示 Kubernetes 资源和浏览器访问。
- [ ] 完成创建任务 → 标记完成 → 刷新仍存在。
- [ ] 展示添加设备和对应的 JSON 信号状态。
- [ ] 展示 REST 调用、日志和 Kubernetes YAML。
- [ ] 解释独立扩容、持久化、安全、成本与局限。
- [ ] 源码仓库链接包含 Kubernetes 部署代码。
- [ ] 视频链接可由老师访问；用未登录窗口检查共享权限。
- [ ] 在正式报告中填写视频链接，保留本计划作为录制辅助材料。

本计划不替代最终视频或正式报告。视频录制、上传和最终链接提交仍需完成。
