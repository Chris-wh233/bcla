# BCLA Remote

在远端原生 LoongArch64 主机部署 BCLA 服务容器，让本机 Codex 通过 SSH 使用远端 Docker 完成任务。默认按会话指定远端，不安装本机远端客户端；固定远端的 SSH + stdio MCP 客户端是可选方式。SSH 由宿主机提供，服务镜像不运行 sshd，也不开放 HTTP 端口。

本目录只维护部署与连接层。runtime、Skills、脚本和文档直接来自上级 BCLA 源码。Docker 镜像和生成的客户端各自携带运行所需的共享文件，因此部署后不依赖本机插件缓存或源码目录挂载。

```text
本机 Codex 的指定会话
  -> SSH -> docker exec bcla-remote bcla-remote-call <工具名>
     -> 远端常驻服务容器 /opt/bcla
        -> 同路径绑定远端 BCLA_HOME，保存任务、日志、知识库和导出
        -> 远端 Docker socket，创建辅助容器并构建目标镜像

可选固定客户端 -> SSH stdio MCP -> 同一服务和工具实现
```

## 环境要求

- 远端：原生 Linux/LoongArch64、Bash、Docker Engine、本机 `/var/run/docker.sock`。构建服务镜像还需 Python 3；Git 用于记录可用的源码 revision。
- 本机：可执行 SSH 命令的 Codex 会话。可直接指定用户、地址和端口，或使用 SSH config 别名 `build-host`。仅可选客户端生成/安装需要 Python 3.10+、Git 和支持插件的 Codex。
- SSH 用户可执行远端 Docker。先按当前环境建立连接并确认主机身份；使用固定客户端时还需免交互认证。连接检查：`ssh build-host 'docker --host unix:///var/run/docker.sock version'`。
- 数据目录使用远端本地文件系统，以支持 SQLite 和文件锁。当前部署入口针对标准宿主 Docker，不支持 rootless 或另一个远程 daemon。

服务镜像安装 Python、Docker CLI、Git、CA、curl、ripgrep、tar。项目编译器和依赖仍在任务辅助容器中准备。基础镜像默认使用 LCR Debian 的固定 digest，历史 manifest 核验记录见 [base-image.json](docs/base-image.json)，不代表已验证当前软件包安装或服务启动。

## 构建与部署

远端需要完整 BCLA 源码树，不能只上传 `remote/`。例如在本机的 BCLA 根目录执行：

```bash
ssh build-host 'mkdir -p ~/bcla'
tar --exclude=./.git --exclude=./remote/deploy.env --exclude=./remote/dist \
    --exclude=__pycache__ --exclude='*.swp' -cf - . \
  | ssh build-host 'tar -xf - -C ~/bcla'
```

在远端执行：

```bash
cd ~/bcla/remote
cp deploy.env.example deploy.env
# 按需编辑 deploy.env，然后：
./deploy.sh deploy
```

`deploy` 构建并启动；其它常用命令：

| 命令 | 行为 |
| --- | --- |
| `./deploy.sh build` | 仅构建镜像 |
| `./deploy.sh up` | 使用已有本地镜像启动或复用服务，不重新构建、不拉取 |
| `./deploy.sh status` | 查看状态和健康情况 |
| `./deploy.sh stdio` | 连接一次 MCP stdio 会话 |
| `./deploy.sh down` | 停止并删除此部署管理的服务容器，保留数据、镜像和辅助容器 |

默认镜像为 `bcla-remote:local`，容器名为 `bcla-remote`，数据目录为部署用户的 `~/.local/share/bcla`。可在 `deploy.env` 配置 `BCLA_IMAGE`、`BCLA_CONTAINER`、`BCLA_DATA_DIR` 和 `BCLA_BASE_IMAGE`。此文件是受信任的 Bash 配置，不随插件安装或镜像复制。

脚本使用根目录作为 Docker 构建上下文，相当于在根目录执行 `docker build -f remote/Dockerfile ... .`；`remote/Dockerfile.dockerignore` 只放行共享核心及服务入口，排除 Git、配置和生成目录。不要使用 COPY ../ 或父目录符号链接。镜像 OCI 标签记录核心版本与可用的 Git revision；无 Git checkout 时 revision 为 unknown，存在修改时可能带 dirty。它们用于追踪来源，不证明内容逐字一致。

数据目录以宿主机相同绝对路径绑定到服务容器，辅助容器也沿用该路径。Docker socket 来自远端宿主机，无需 Docker-in-Docker。不要为每次连接运行临时 `docker run --rm` 服务：常驻容器及 `--init` 用于保持 worker 生命周期和回收子进程。SSH 断开不等于任务停止；服务容器重启则会终止其中的 worker，辅助容器命令是否仍在运行需另外检查。

服务只复用镜像和数据目录配置一致的已登记容器。升级时先处理运行中的任务并确认实际进程，再执行 down/up。不要让原生宿主 BCLA 和服务容器同时写同一任务库；不同 PID 命名空间中的 worker PID 不能直接复用来恢复运行中执行。已有本机或旧服务的数据不会自动迁移。

## 默认：在指定会话中使用远端

部署服务后，在需要远端任务的会话中告诉模型：

```text
本会话使用 SSH 主机 build-host 上的 BCLA，服务容器名为 bcla-remote。
先读取该容器内 /opt/bcla/docs/remote-session.md 和主 Skill，
通过远端工具入口构建项目 A 的镜像，不调用本机 BCLA MCP 工具，
不修改本机插件配置。
```

可以同时在另一个会话中使用本机 `@BCLA`，也可以给其它会话指定不同远端。此方式不依赖本机原生 BCLA 插件支持远端；会话通过 SSH 读取远端版本的 Skills 并执行相同工具。仅口头指定主机不会重定向本机已注册工具，模型需要遵循该会话的远端指引。

读取指引和查询工具接口的示例：

```bash
ssh -T build-host 'docker --host unix:///var/run/docker.sock exec -i bcla-remote cat /opt/bcla/docs/remote-session.md'
ssh -T build-host 'docker --host unix:///var/run/docker.sock exec -i bcla-remote cat /opt/bcla/skills/bcla/SKILL.md'
ssh -T build-host 'docker --host unix:///var/run/docker.sock exec -i bcla-remote /usr/local/bin/bcla-remote-call --list'
```

调用工具时通过 stdin 发送 JSON，例如：

```bash
ssh -T build-host 'docker --host unix:///var/run/docker.sock exec -i bcla-remote /usr/local/bin/bcla-remote-call task_open' <<'JSON'
{"action":"list"}
JSON
```

入口直接复用现有 Server 分发，不需要客户端手写 MCP 握手，也不另建任务库或调度器。输出包含 structuredContent，工具错误返回 isError 和非零退出码。长任务仍通过 environment_exec/execution_read 异步提交和查询，不能把一次长 SSH shell 编译当成 BCLA 任务执行。会话应记住主机、容器、远端数据目录和任务 ID，恢复时沿用它们。

## 可选：固定远端客户端

只有希望共享当前 Codex 配置的会话固定使用同一远端时，才生成并安装客户端。按会话指定 SSH 不需要这一步。

在本机同一版本的 BCLA 根目录执行：

```bash
python3 remote/scripts/prepare_client.py build-host
# 默认生成 remote/dist/bcla-remote，已有目录不会覆盖。
cd remote/dist/bcla-remote
./install.sh
```

生成器仅写输出目录；运行生成插件的安装器才会修改 Codex 插件配置。可通过 `--output /PATH/NEW-CLIENT` 和 `--container NAME` 指定输出目录及远端容器名。客户端包含 `bcla-remote.json`、SSH `.mcp.json`、转发脚本和各 Skill 的远端指引，不携带 remote 子项目。

客户端与服务应来自同一源码版本。更新核心后同时重建服务镜像、重新生成并安装客户端；服务不会实时读取本机源码。当前生成器不自动探测或升级远端。

插件身份、MCP 服务名和调用方式保持 `bcla` / `@BCLA`。安装远端客户端会将原本机 BCLA 切换到远端执行，并非同时启用两个同名插件。开启新会话使用；需要切回本机时，在原 BCLA 源码根目录重新运行 `./install.sh`。两边的任务记录均保留。

若 PATH 中的 codex 是不转发参数的自定义包装脚本，应让安装器通过 PATH 找到实际 Codex CLI。

## 路径、知识库与文件传输

工具返回的路径、默认知识库缓存、经验生成目录和 gen-maker 导出均在远端。最新的项目／版本／运行镜像家族规则与本机共用；不能用本机同名目录代替远端目录。按会话方式遵循 [会话操作规则](docs/session.md)，可选固定客户端的各 Skill 引用 [客户端操作规则](docs/client.md)。

按会话使用时直接通过 SSH 执行服务容器内的相应命令，并按 [会话操作规则](docs/session.md) 传输文件。以下便利转发命令仅用于可选固定客户端，在生成客户端根目录运行，替换示例路径：

```bash
python3 scripts/remote.py printenv BCLA_HOME
python3 scripts/remote.py python3 /opt/bcla/scripts/image_tags.py library/debian

# 上传本机输入，然后由任务辅助容器验证内容。
tar -C /LOCAL/INPUT -cf - artifact.tar.gz \
  | python3 scripts/remote.py tar -xf - -C /REMOTE/WORKSPACE

# 下载远端已组装的导出目录。
python3 scripts/remote.py tar -cf - -C /REMOTE/EXPORTS export-directory \
  | tar -xf - -C /LOCAL/OUTPUT
```

转发仅用于允许的元数据、知识库维护、文件传输和导出静态处理；项目分析、修改、构建与测试仍通过 MCP 辅助容器执行。镜像属于远端 daemon，保存镜像包或推送仍需显式请求。Git 提交身份、私有仓库凭据和代理由实际远端环境配置，不复制本机密钥或全局配置。

服务以 root 写入绑定目录，产物可能为 root 所有；通过转发传输可避免 SSH 用户直接读取时的权限差异。备份应停止写入并一起保存数据库和任务文件。构建日志位于远端 `tasks/<id>/executions/`，通过 execution_read 查询。

## 检查

```bash
make -C remote check
```

该命令执行部署脚本语法检查、连接层测试及共享核心测试。部署测试使用模拟 Docker；不会构建镜像、创建真实容器、连接远端或安装插件。实际包安装、服务启动、SSH 连接、辅助容器执行与断线恢复需要另行联调。验证范围见 [validation.md](docs/validation.md)。
