# Go 模块代理

触发条件：辅助容器即将执行 Go 模块命令，或访问 proxy.golang.org 出现明确网络错误。

目的：通过 `https://goproxy.cn,direct` 改善 Go 模块下载。

功能：设置辅助命令环境、验证 GOPROXY，按需进行一次去除 HTTP 代理重试和一次 Go direct 重试。不得写入宿主机全局配置、目标镜像或知识库构建配方；已启动容器可直接使用命令级变量。

详细规则见 [SKILL.md](SKILL.md)。
