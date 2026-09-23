# BCLA

LoongArch64 容器镜像构建插件。模型根据 Skills 决定构建路径，Codex Agent 负责执行循环，MCP 只提供任务持久化、容器执行和证据读取。

插件名和 MCP 名均为 `bcla`，默认数据目录为 `~/.local/share/bcla`。当前实现不包含 Controller 工作项、依赖状态机、Stop Hook 和硬预算。

## 安装

要求 Linux、Python 3.10+（仅标准库）、可使用本地 Docker socket 的 Codex 进程，以及原生 LoongArch64 Docker 环境。准备辅助容器时需要包仓库网络访问。

在此源码目录执行：

```bash
./install.sh
```

安装脚本创建独立本地 marketplace，通过当前 Codex CLI 的 `plugin marketplace add` 和 `plugin add` 安装。不删除旧插件或旧缓存。每次执行生成带版本后缀的独立包，保留以前的包以免影响已有进程。更新后开启新会话。

只生成安装包而不修改 Codex 配置：

```bash
./install.sh --prepare-only
```

可用 `BCLA_HOME` 指定持久化目录，用 `BCLA_DOCKER_BIN` 指定 Docker 客户端。安装脚本的 `--home` 只指定包和 marketplace 位置；运行时数据位置仍由 MCP 进程继承的 `BCLA_HOME` 决定。

## 卸载

使用安装时相同的用户和 `CODEX_HOME` 环境执行：

```bash
./uninstall.sh
```

脚本通过 `codex plugin remove bcla@bcla-local` 卸载插件及其 Codex 安装缓存，保留本地 marketplace、安装包、任务记录、日志和知识库。卸载后开启新会话。脚本支持从任意工作目录调用，无需 Python；本操作不停止已运行的构建命令或删除辅助容器。

## 使用

| 操作 | 示例 |
| --- | --- |
| 开始任务 | `@BCLA $bcla:bcla 构建 beszel 指定版本的 hub 和 agent，仅 Alpine` |
| 提供产物恢复 | `@BCLA $bcla:bcla 恢复 bcla-...，静态资源位于 /tmp/static.zip` |
| 查看问题 | `分析任务 bcla-... 的构建日志，暂时不要继续` |
| 暂停任务 | `@BCLA 暂停当前构建，保存检查点` |
| 清理辅助容器 | `@BCLA 清理任务 bcla-... 的环境`，仅停止并删除已登记且归属匹配的自建辅助容器，保留 workspace 并显示其路径 |
| 生成经验 | `@BCLA $bcla:gen-experience 为 bcla-... 生成经验` |
| 自动本地 CI | 首轮请求说明 `release_ci_mode=local-build`；默认 `manual` |

知识库只在显式调用 gen-experience 时写入，默认仅在本地 main 提交。`goal.options.kb_publication=push-main` 或当前明确授权才允许推送。

## 实现边界

任务记录通过目标、检查点、决策和资源清单保存当前进度、路线依据、已验证事实及恢复位置。工具保存命令与执行结果，供模型恢复上下文。

工具记录命令提交时的任务版本，在返回结果中提供当前上下文和未整理结果提示。模型可把记录更新与下一条命令一并提交；版本冲突不会启动命令。提示不阻断构建，也不能保证模型绝不会忘记整理。带有历史节点的任务仍可读取；历史节点仅作为资料读取，当前信息写入任务级检查点和资源清单。

- 任务状态只有 ACTIVE、WAITING_FOR_USER、PAUSED、SUCCEEDED、CANCELLED。状态是记录，不会自动调度或杀死命令。
- SQLite 事务用于原子保存任务和事件；并发修改通过 revision 检测。没有资源父子状态门禁。
- 命令异步执行，使用 request_key 去重，日志可分页读取。MCP 重启不代表构建中止；超时后需要检查容器内实际进程。
- 新辅助容器挂载 Docker socket，设置较高 nofile，并由 bootstrap 工具安装 git、ca-certificates、curl、docker-cli；使用 apt 或 apk 时同时安装 ripgrep。默认不安装 Docker daemon、compose 或 buildx。
- 工作区使用相同的宿主机/容器绝对路径，兼容通过宿主 Docker daemon 创建的兄弟容器挂载。
- 代理通过 exec 环境注入，目标镜像不继承辅助容器配置。是否遵循镜像来源、是否应等待 x86 产物、是否完成测试由 Skills 和模型判断，工具不提供强制保证。
- 无额外 Agent 循环或自动续跑。Codex 会话结束时，应保存检查点，用户可再次调用恢复。

## 文件结构

```text
.codex-plugin/plugin.json  插件入口
.mcp.json                  MCP 配置
runtime/                   任务存储、容器工具、后台执行、MCP
skills/                    8 个轻量技能及中文说明
docs/task-protocol.md      工具和记录协议
scripts/install.py         可重复安装和打包
scripts/kb_index.py        经验结构/哈希检查及索引生成
scripts/smoke_container.py 可选真实容器测试
tests/                     存储、执行、容器参数和知识库测试
docs/behavior-evaluation.md 模型行为验收场景（不同于单元测试）
```

## 验证

```bash
python3 -m unittest discover -s tests -v
python3 scripts/smoke_container.py --image <已存在的LoongArch镜像>
python3 scripts/smoke_container.py --image <已存在的LoongArch镜像> --bootstrap
```

真实容器测试只创建临时任务和辅助容器，结束后删除该临时容器，不删除镜像。单元测试不构建业务项目。通过这些测试不代表模型在所有真实任务中都能正确选择技能；仍需以实际构建案例验证。

备份时同时保存数据目录中的 records.sqlite3 和 tasks/；在没有写入时复制，或使用 SQLite backup API 备份数据库。辅助容器和 Docker 镜像由 Docker 独立管理。
