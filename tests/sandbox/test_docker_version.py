import docker

# 创建 Docker 客户端，使用默认的命名管道连接
client = docker.DockerClient(base_url='npipe:////./pipe/docker_engine')

try:
    # 获取 Docker 版本信息
    version = client.version()
    print("Docker 版本信息：", version)

    # 列出所有容器
    containers = client.containers.list()
    print("当前运行的容器：", containers)

except docker.errors.DockerException as e:
    print("连接 Docker API 失败：", e)