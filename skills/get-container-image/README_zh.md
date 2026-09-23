# 获取容器环境

触发条件：初始缺少辅助容器、用户环境待验证、Dockerfile 存在外部镜像，或后续需要不同工具链/libc 的环境。

目的：取得真实可用、语义兼容的 LoongArch64 镜像及辅助容器。

功能：优先查询 LCR 的真实标签和架构，未知项目默认验证 Debian forky，按需求选择 Alpine、openEuler 或语言镜像。创建辅助容器，安装 git、ca-certificates、curl 和 docker-cli；apt/apk 环境同时安装 ripgrep。随后验证 Docker socket 和工作区。没有合理可用镜像时保存等待条件，用户提供镜像后验证恢复。

详细规则见 [SKILL.md](SKILL.md)。

标签查询使用插件根目录中的 `python3 scripts/image_tags.py library/golang`（按需替换仓库名），自动跟随响应头的下一页链接，全部读取后返回标签和页数。查询失败不能视为镜像不存在。按项目的最低版本或精确版本约束评估完整结果，不排除尚未检查的更高版本；选定后仍需验证镜像架构、libc 和实际工具版本。

环境证据记录在资源清单中，注明服务的产物以及环境、命令的标识；获得环境后继续对应构建操作。
