# BCLA (Build Container for LoongArch)

BCLA 是面向原生 LoongArch64 环境的 Codex 容器镜像构建插件。它复用 Codex 当前会话和 Agent Loop，通过 Skills 提供 LoongArch64 构建经验，通过 MCP 工具保存任务状态、管理辅助容器、执行命令并记录结果。

用户可以在同一会话中启动、暂停和恢复构建，也可以在不触发 BCLA 的普通对话中分析任务日志或讨论构建方案。

## 工作方式

使用 `@BCLA` 后，Codex 会根据项目和目标选择构建路线：

1. 识别仓库、版本、目标镜像及用户约束。
2. 查找可复用的构建经验、LoongArch64 产物和容器镜像。
3. 在 LoongArch64 辅助容器中分析、构建和测试。
4. 保存检查点、资源来源、执行记录和最终产物信息，供后续会话恢复。

Skills 负责镜像选择、依赖获取、源码适配、网络配置和经验复用等决策。MCP 层只提供持久化与执行能力，不替模型选择构建路线。

## 安装

运行环境需要 Linux、Python 3.10+、支持插件的 Codex CLI、可访问的 Docker socket，以及原生 LoongArch64 Docker 环境。

在源码根目录执行：

```bash
./install.sh
```

安装或更新后开启新的 Codex 会话。只准备本地安装包时使用：

```bash
./install.sh --prepare-only
```

默认数据目录是 `~/.local/share/bcla`。可通过 `BCLA_HOME` 修改数据目录，通过 `BCLA_DOCKER_BIN` 指定 Docker 客户端。

卸载插件：

```bash
./uninstall.sh
```

卸载会保留任务记录、workspace、日志、知识库和本地安装包。

## 使用

直接使用 `@BCLA` 加自然语言描述即可，不需要附加技能限定名。每个任务都有 `bcla-...` 格式的 ID。恢复、清理或生成经验时建议明确提供任务 ID。

| 操作 | 示例 |
| --- | --- |
| 开始任务 | `@BCLA 构建 beszel 指定版本的 hub 和 agent 镜像，仅构建 Alpine 版本` |
| 恢复任务 | `@BCLA 恢复任务 bcla-...，所需静态资源位于 /tmp/static.zip` |
| 暂停任务 | `@BCLA 暂停当前构建并保存检查点` |
| 清理环境 | `@BCLA 清理任务 bcla-... 的辅助容器` |
| 生成经验 | `@BCLA 为已完成的任务 bcla-... 生成构建经验` |

可选参数：
本质是由 Skills 解释的任务偏好，并无强制校验

| 参数 | 可选值 | 默认值 | 作用 |
| --- | --- | --- | --- |
| release_ci_mode | manual、auto | manual | 当 loongarch64-releases 有可用 CI、但没有所需 Release 时，选择暂停并让用户构建（manual），或在本地自动运行该 CI 的 scripts/build_in_docker.sh（auto）|
| kb_publication | local-commit、push-main | local-commit | 生成经验后只提交到本地知识库，或明确允许推送到知识库远端 main |

可在首轮请求中指定，例如：

  @BCLA 构建项目 A 的镜像，release_ci_mode=auto

补充说明：
如需讨论任务细节而不继续执行 BCLA，请省略 @BCLA。模型可以结合任务的记录和日志进行分析，但不会主动推进构建。例如：请给我一个简洁的 GitHub Actions 工作流，用于在 x86_64 环境中构建任务 bcla-... 所需的前端资源

## 数据与边界

- 项目分析、依赖安装、编译和测试在任务辅助容器中执行。workspace 位于 `~/.local/share/bcla/tasks/<task-id>/workspace`，并挂载到容器中的相同路径。
- 辅助容器可以访问宿主 Docker socket。默认安装 git、ca-certificates、curl 和 docker-cli。（使用 apt 或 apk 的环境会额外安装 ripgrep）
- 命令异步执行并保存日志。会话结束不会删除任务，后续可以通过任务 ID 恢复。
- BCLA 只在用户明确要求时清理已登记且归属于该任务的辅助容器。清理不会删除 workspace、镜像或卷。
- 知识库用于复用已经验证的构建经验。生成经验需要用户主动触发；发布或推送需要用户明确授权。
- Skills 和模型负责技术判断。实际构建结果、镜像架构及基础功能仍需通过任务中的构建和测试证据确认。

## 文件结构

```text
.codex-plugin/plugin.json   插件清单
.mcp.json                   MCP 服务配置
install.sh                  安装入口
uninstall.sh                卸载入口
runtime/                    任务存储、辅助容器和命令执行
skills/                     BCLA 构建 Skills
docs/                       任务协议和行为验收说明
scripts/install.py          本地打包与安装实现
scripts/image_tags.py       LCR 镜像标签完整分页查询
scripts/kb_index.py         知识库校验与索引生成
scripts/smoke_container.py  辅助容器冒烟检查
tests/                      运行时与持久化测试
```
