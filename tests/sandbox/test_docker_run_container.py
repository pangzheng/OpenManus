import docker
import time

def run_docker_container():
    try:
        # 创建 Docker 客户端，使用 Windows 默认的命名管道
        client = docker.DockerClient(base_url='npipe:////./pipe/docker_engine')

        # 打印 Docker 版本信息以确认连接
        print("Docker 版本信息：", client.version())

        # 配置并运行容器
        container = client.containers.run(
            image="python:3.10-slim",           # 使用 python:3.10-slim 镜像
            command="tail -f /dev/null",        # 运行 python --version 命令
            detach=True,                       # 在后台运行
            #mem_limit="512m",                  # 内存限制 512MB
            mem_limit="1g",
            hostname="sandbox",
            # cpu_limit=2.0,
            cpu_period=100000,                 # CPU 周期
            cpu_quota=50000,                   # CPU 配额，相当于 0.5 CPU
            # timeout=300,
            # network_enabled=False,
            name="sandbox",
            working_dir="/workspace",          # 工作目录
            environment={"PYTHONUNBUFFERED": "1"}  # 环境变量
        )
        
    
        # 等待容器运行完成并获取日志
        logs = container.logs().decode('utf-8')
        print("容器输出：", logs)
        print("run 容器状态:" ,container.status)
        print("get 容器状态:" ,container.reload())
        print("run 容器状态:" ,container.status)

        # time.sleep(100)
        # 清理容器
        container.stop()
        container.remove()
        print("容器已清理")

    except docker.errors.DockerException as e:
        print("Docker 操作失败：", e)
    except Exception as e:
        print("发生其他错误：", e)

if __name__ == "__main__":
    run_docker_container()