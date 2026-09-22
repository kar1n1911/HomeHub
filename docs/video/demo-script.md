# HomeHub 十分钟演示视频计划书

适用版本：frontend 0.2.2，backend 0.2.0。更新日期：2026-09-22。

配套逐段旁白：[演示台词](narration-zh.md)。本文用于安排画面与操作，台词文件用于朗读。

## 一、成片目标

建议时长 **9 分 40 秒**，预留 20 秒缓冲，成片必须保持在作业规定的 5–10 分钟内。时间表是彩排目标，不是经过录音测量的保证。

录制形式：屏幕录制加旁白，使用浏览器、终端、代码编辑器。无需制作复杂幻灯片。

影片要回答：应用做什么、服务如何协作、为什么这样设计、如何部署、数据如何保存、能否独立扩容、安全上做了什么以及还缺什么。

三页面分工：

- **Overview**：家庭汇总、待办预览、设备预览及页面入口。
- **Tasks**：创建任务、筛选、标记完成。
- **Devices**：登记模拟设备、显示读数、查看信号投递与 JSON。

固定使用 Kubernetes 的 `http://localhost:30080/`。不要混入 Compose 的 8080 页面，它们使用不同数据。

## 二、录制时间表

| 段落 | 时间 | 画面与操作 | 必须留下的证据 |
|---|---|---|---|
| 1 开场与导航 | 00:00–00:40 | Overview 首页；依次点击 Tasks、Devices，再回 Overview | 三个真正切换内容的页面，明确应用用途 |
| 2 架构 | 00:40–01:40 | 已打开的架构图；指向浏览器、三个业务 API、数据库和信号链路 | 服务职责、REST 交互、组件映射 |
| 3 Kubernetes 运行 | 01:40–02:25 | 显示集群 context、Deployment、Pod、Service、PVC、数据库集群 | 程序确实在 Kubernetes 上运行；NodePort 外部入口 |
| 4 任务闭环 | 02:25–03:45 | Tasks → Add task → Create task → 勾选完成 → Completed → 刷新 | 创建、修改、服务端保存和刷新读取 |
| 5 设备与信号 | 03:45–05:00 | Devices → Add device → Save device → 找到对应信号并展开 JSON | 设备入口、编码、HTTP 投递状态 |
| 6 REST 与日志 | 05:00–05:50 | Network 中任务请求；fetch 与后端路由代码；终端日志 | 自己实现 REST API，并以程序调用它 |
| 7 配置与持久化 | 05:50–07:05 | 展示部署、Service、数据库和扩容 YAML 的指定字段 | 镜像、探针、持久卷、Secret、HPA/KEDA |
| 8 独立扩容 | 07:05–07:50 | frontend 2→3；显示 Deployments；恢复到 2 | 一个组件单独扩容，其他组件不必跟随 |
| 9 取舍与安全 | 07:50–09:05 | 架构图；已有 HA/队列验证记录，只展示相关结果 | 业务价值、成本、安全边界、故障恢复证据 |
| 10 仓库与结束 | 09:05–09:40 | GitHub 目录、Docker Hub 镜像；回 Overview | 源码和部署代码可查看、镜像已发布 |
| 缓冲 | 09:40–10:00 | 不新增内容 | 自然停顿、加载和转场 |

## 三、开录前准备

1. 启动 OrbStack，确认 `homehub` 应用及数据库就绪。不要在录像中安装 operator、构建镜像或初始化数据库。
2. 若之前执行过清理脚本，先恢复应用，等所有依赖可用；录制过程中不要运行 cleanup。
3. 打开以下标签/文件，避免录像中搜索：
   - 浏览器 Overview、开发者工具 Network，启用 Preserve log。
   - `docs/architecture/architecture.md` 和 `device-signals.md` 的图表预览。
   - `frontend/src/App.jsx` 的 `saveTask()`。
   - `services/task-service/app/main.py` 的任务 POST/PATCH 路由。
   - 本计划第五节的 YAML。
   - `docs/verification/database-ha.md`、`signal-scaling.json`。
   - GitHub 仓库和 Docker Hub 的 frontend 镜像 Tags 页面。
4. 浏览器与终端文字应在成片中清晰可读；关闭私人通知，不展示 `.secrets/`、Secret 内容或完整环境变量。
5. 先录 20 秒检查麦克风音量、屏幕文字和鼠标可见性。
6. 完整彩排一次并计时。语速自然，操作时允许停顿。正式录制使用新的演示名称，避免重复记录混淆。

终端准备：

```bash
cd /Users/coleanderson/Sync/HomeWorks/PA2577/HomeHub
k() { kubectl --context orbstack -n homehub "$@"; }

kubectl config get-contexts orbstack
k get deployments,pods
k get services,pvc
k get clusters.postgresql.cnpg.io
k get hpa,scaledobjects
```

仅在应用之前被清理时，在开录前恢复：

```bash
./scripts/deploy-k8s.sh
k rollout status deployment/frontend --timeout=120s
k rollout status deployment/task-service --timeout=120s
k rollout status deployment/device-service --timeout=120s
```

随后实际打开页面验证读取与写入。frontend Ready 不代表所有下游依赖已就绪。

## 四、现场操作清单

### Tasks：一条完整流程

- 点击导航 **Tasks**，明确当前页只展示任务相关内容。
- 点击 **Add task**。
- Task name：`Prepare the weekly shopping list`；Priority：High；Due date 留空。
- 点击 **Create task**，找到新任务并勾选。
- 点击 **Completed**，确认任务在筛选结果中。
- 刷新页面：仍在 Tasks，任务仍勾选。刷新后筛选默认恢复 All，不能说筛选也被保存了。
- 回 Overview 指出汇总已更新，再进入 Devices。

### Devices：登记并查看投递

| 字段 | 填写内容 |
|---|---|
| Device name | Demo kitchen sensor |
| Room | Kitchen |
| Initial reading | 22.5 C |
| Sampling interval (seconds) | 30 |

- 保存后展示新设备卡片。
- 滚动到 Signal delivery；若默认三条里没有新设备，展开 Show all recent signals。
- 找到该设备的记录，指向状态并展开 JSON；只讲 `id`、`time`、`source`、`data`。
- worker 从零启动可能有延迟。Pending 时讲队列机制，Delivered 后才说投递成功。
- 刷新后仍在 Devices，设备信息继续存在。

### REST 和日志

展示 Network 中刚才的 `POST /api/tasks` 或 `PATCH /api/tasks/{id}` 的方法、请求 JSON、响应状态和响应内容，然后切换到对应前后端代码。

```bash
k logs -l app=task-service --all-containers=true --prefix=true --tail=10 --max-log-requests=10
```

日志可能跨多个副本，因此按标签读取。若 Network 不便展示，可补充：

```bash
curl -sS http://localhost:30080/api/tasks | python3 -m json.tool
```

不要只展示 curl 而跳过自己写的 fetch 和 API 路由：作业还要求体现程序化调用及实现 REST 的能力。

### 独立扩容

frontend 未被当前 CPU HPA 管理，适合短时间手动演示：

```bash
k get deployments
k scale deployment/frontend --replicas=3
k rollout status deployment/frontend --timeout=60s
k get deployments
k scale deployment/frontend --replicas=2
k rollout status deployment/frontend --timeout=60s
```

操作前后对照副本数。该演示证明独立手动水平扩容；不能说这就是 CPU 自动扩容测试。其他服务可能因自身负载发生自动变化，应按实际输出解释。

## 五、YAML 镜头清单

| 文件 | 画面定位 | 讲解重点 |
|---|---|---|
| `kubernetes/frontend/deployment.yaml` | `image`、`replicas`、Service `nodePort` | Docker Hub 镜像、多个副本、外部入口 30080 |
| `kubernetes/task-service/deployment.yaml` | probes、resources、Secret 引用 | 就绪/存活检查、资源预算、独立凭据 |
| `kubernetes/postgres/postgres.yaml` | `instances`、`storage`、`synchronous` | 三实例、各自 PVC、同步复制要求 |
| `kubernetes/config/hpa.yaml` | API target、min/max、CPU metric | 原有业务 API 独立自动扩容 |
| `kubernetes/config/signal-scaling.yaml` | metric URL、min/max、cooldown | 根据队列深度启停 0–4 个 worker |
| `kubernetes/postgres/postgres.yaml` | preferred anti-affinity | 三个数据库实例都部署在同一节点 |

共 75 秒，提前定位，每份只讲一两个字段，不逐行朗读。HPA 若显示 `<unknown>`，应在彩排时排查 Metrics Server，不应声称该机制已现场验证。

## 六、证据边界与异常处理

- 刷新后数据存在说明保存到了服务端；持久卷配置及数据库恢复测试才补充重启后持久化的证据。
- 数据库 HA 记录是在独立测试环境中完成的历史测试，曾有 API 中断；恢复读取约用了 192 秒。不是当前视频现场故障切换，也不是整机故障测试。
- `signal-scaling.json` 是提前执行的积压、恢复和扩缩容验证记录。展示日期及实际字段，不把它说成本次录像产生的结果。
- 现场信号未投递成功时如实说明 Pending。可先完成其他段落后返回；如持续失败，修复后重录。
- 不在主片里临时删除数据库主节点、运行完整故障注入脚本或等待 scale-to-zero 全流程。
- 自定义 Alertmanager 不是 Prometheus Alertmanager；JSON 编码不是加密；至少一次传输不等于 exactly-once。
- 单节点上的三个数据库 Pod 不能抵御整台主机故障；同步复制与 PVC 不能替代异地备份。
- 如果超时，缩短开场、JSON 字段讲解和配置细节，保留浏览器操作、日志、YAML、安全讨论。

## 七、提交清单

- [ ] 视频 5–10 分钟，画面文字、旁白清晰。
- [ ] 展示三页面导航、任务闭环、设备入口。
- [ ] 展示 Kubernetes 资源、REST 代码与请求、日志、YAML。
- [ ] 解释扩容、持久化、安全、成本和系统局限。
- [ ] 给出源码与部署仓库：<https://github.com/kar1n1911/HomeHub>。
- [ ] 展示 Docker Hub 镜像：frontend 0.2.2；household/task/device/alertmanager 0.2.0，均在 `kar1n1911` 下。
- [ ] 用未登录窗口验证最终视频链接对老师可访问。
- [ ] 在正式报告中填入视频链接；计划与台词不能代替实际录制和提交。
