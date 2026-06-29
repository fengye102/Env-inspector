"""
core/registry.py — 工具定义注册表(唯一数据源)

新增/修改工具只改此文件。
"""

from dataclasses import dataclass, field


@dataclass
class ScanResult:
    """单次工具扫描的结果"""
    tool_id: str
    installed: bool
    version: str | None = None
    raw_output: str | None = None
    install_path: str | None = None
    extra_info: str | None = None
    error: str | None = None
    scan_duration_ms: int = 0


@dataclass
class ToolDefinition:
    """单个工具的完整定义"""
    id: str
    display_name: str
    category: str
    description: str
    commands: list[str]
    extra_info_cmd: str | None = None
    docs_url: str = ""
    common_cmds: list[dict] = field(default_factory=list)
    registry_keys: list[str] = field(default_factory=list)
    fallback_paths: list[str] = field(default_factory=list)


# ── 分类元数据 ─────────────────────────────────────────────
CATEGORIES = [
    {"id": "lang",      "label": "编程语言"},
    {"id": "pkg",       "label": "包管理器"},
    {"id": "vcs",       "label": "版本控制"},
    {"id": "container", "label": "容器"},
    {"id": "db",        "label": "数据库"},
    {"id": "cloud",     "label": "云工具"},
    {"id": "build",     "label": "构建工具"},
    {"id": "runtime",   "label": "运行时/其他"},
]

CATEGORY_ORDER = {c["id"]: i for i, c in enumerate(CATEGORIES)}


# ── 工具定义列表(共 25 种,第一版 MVP) ────────────────────

def _build_tools() -> list[ToolDefinition]:
    """集中构造所有工具定义,返回列表"""
    return [

        # ── 编程语言 ──────────────────────────────────────
        ToolDefinition(
            id="python",
            display_name="Python",
            category="lang",
            description="用来运行 Python 程序的解释器",
            commands=["python --version", "python3 --version"],
            extra_info_cmd="pip list --format=columns 2>nul | findstr /i /v Package",
            docs_url="https://docs.python.org/",
            common_cmds=[
                {"label": "查看版本", "cmd": "python --version", "desc": "显示当前 Python 版本"},
                {"label": "安装包", "cmd": "pip install <包名>", "desc": "安装 Python 包"},
                {"label": "运行脚本", "cmd": "python 脚本.py", "desc": "运行 Python 脚本文件"},
            ],
            registry_keys=[
                r"SOFTWARE\Python\PythonCore\*\InstallPath",
                r"SOFTWARE\Wow6432Node\Python\PythonCore\*\InstallPath",
            ],
            fallback_paths=[
                r"C:\Python313\python.exe",
                r"C:\Python312\python.exe",
                r"C:\Python311\python.exe",
                r"C:\Program Files\Python313\python.exe",
                r"C:\Program Files\Python312\python.exe",
                r"C:\Program Files\Python311\python.exe",
            ],
        ),
        ToolDefinition(
            id="java",
            display_name="Java",
            category="lang",
            description="用来运行 Java 程序的运行时环境",
            commands=["java -version"],
            docs_url="https://docs.oracle.com/en/java/",
            common_cmds=[
                {"label": "查看版本", "cmd": "java -version", "desc": "显示 Java 版本信息"},
                {"label": "编译程序", "cmd": "javac Hello.java", "desc": "编译 Java 源文件"},
                {"label": "运行程序", "cmd": "java Hello", "desc": "运行编译后的 Java 类"},
            ],
            registry_keys=[
                r"SOFTWARE\JavaSoft\Java Runtime Environment",
                r"SOFTWARE\JavaSoft\JDK",
                r"SOFTWARE\Wow6432Node\JavaSoft\Java Runtime Environment",
            ],
            fallback_paths=[
                r"C:\Program Files\Java\*\bin\java.exe",
                r"C:\Program Files (x86)\Java\*\bin\java.exe",
            ],
        ),
        ToolDefinition(
            id="nodejs",
            display_name="Node.js",
            category="lang",
            description="用来运行 JavaScript 程序的服务器端运行环境",
            commands=["node --version"],
            docs_url="https://nodejs.org/docs/",
            common_cmds=[
                {"label": "查看版本", "cmd": "node --version", "desc": "显示 Node.js 版本"},
                {"label": "运行脚本", "cmd": "node 脚本.js", "desc": "运行 JavaScript 文件"},
                {"label": "交互模式", "cmd": "node", "desc": "进入 Node.js 交互式 REPL"},
            ],
            registry_keys=[
                r"SOFTWARE\Node.js",
            ],
            fallback_paths=[
                r"C:\Program Files\nodejs\node.exe",
                r"C:\Program Files (x86)\nodejs\node.exe",
            ],
        ),
        ToolDefinition(
            id="go",
            display_name="Go",
            category="lang",
            description="Google 开发的编译型编程语言",
            commands=["go version"],
            docs_url="https://go.dev/doc/",
            common_cmds=[
                {"label": "查看版本", "cmd": "go version", "desc": "显示 Go 版本"},
                {"label": "编译程序", "cmd": "go build main.go", "desc": "编译 Go 程序"},
                {"label": "运行程序", "cmd": "go run main.go", "desc": "直接运行 Go 源文件"},
            ],
            registry_keys=[
                r"SOFTWARE\Go",
            ],
            fallback_paths=[
                r"C:\Go\bin\go.exe",
                r"C:\Program Files\Go\bin\go.exe",
            ],
        ),
        ToolDefinition(
            id="rust",
            display_name="Rust",
            category="lang",
            description="Mozilla 开发的系统级编程语言,强调安全与性能",
            commands=["rustc --version"],
            docs_url="https://doc.rust-lang.org/",
            common_cmds=[
                {"label": "查看版本", "cmd": "rustc --version", "desc": "显示 Rust 编译器版本"},
                {"label": "编译程序", "cmd": "rustc main.rs", "desc": "编译 Rust 源文件"},
                {"label": "构建项目", "cmd": "cargo build", "desc": "使用 Cargo 构建项目"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Users\%USERNAME%\.cargo\bin\rustc.exe",
                r"C:\Users\%USERNAME%\.rustup\toolchains\*\bin\rustc.exe",
            ],
        ),
        ToolDefinition(
            id="ruby",
            display_name="Ruby",
            category="lang",
            description="简洁灵活的脚本语言,常用于 Web 开发",
            commands=["ruby --version"],
            docs_url="https://www.ruby-lang.org/en/documentation/",
            common_cmds=[
                {"label": "查看版本", "cmd": "ruby --version", "desc": "显示 Ruby 版本"},
                {"label": "运行脚本", "cmd": "ruby 脚本.rb", "desc": "运行 Ruby 脚本文件"},
                {"label": "安装 gem", "cmd": "gem install <包名>", "desc": "安装 Ruby 包"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Ruby*\bin\ruby.exe",
                r"C:\Program Files\Ruby*\bin\ruby.exe",
            ],
        ),
        ToolDefinition(
            id="php",
            display_name="PHP",
            category="lang",
            description="广泛用于 Web 开发的服务器端脚本语言",
            commands=["php --version"],
            docs_url="https://www.php.net/docs.php",
            common_cmds=[
                {"label": "查看版本", "cmd": "php --version", "desc": "显示 PHP 版本"},
                {"label": "运行脚本", "cmd": "php 脚本.php", "desc": "运行 PHP 脚本文件"},
                {"label": "内置服务器", "cmd": "php -S localhost:8000", "desc": "启动 PHP 内置 Web 服务器"},
            ],
            registry_keys=[
                r"SOFTWARE\PHP",
                r"SOFTWARE\Wow6432Node\PHP",
            ],
            fallback_paths=[
                r"C:\PHP\php.exe",
                r"C:\Program Files\PHP\php.exe",
                r"C:\Program Files (x86)\PHP\php.exe",
            ],
        ),
        ToolDefinition(
            id="dotnet",
            display_name=".NET SDK",
            category="lang",
            description="Microsoft 开发的跨平台开发框架",
            commands=["dotnet --version"],
            docs_url="https://learn.microsoft.com/en-us/dotnet/",
            common_cmds=[
                {"label": "查看版本", "cmd": "dotnet --version", "desc": "显示 .NET SDK 版本"},
                {"label": "创建项目", "cmd": "dotnet new console", "desc": "创建新控制台项目"},
                {"label": "编译运行", "cmd": "dotnet run", "desc": "编译并运行 .NET 项目"},
            ],
            registry_keys=[
                r"SOFTWARE\dotnet\Setup\InstalledVersions\*\sdk",
            ],
            fallback_paths=[
                r"C:\Program Files\dotnet\dotnet.exe",
            ],
        ),

        # ── 包管理器 ──────────────────────────────────────
        ToolDefinition(
            id="pip",
            display_name="pip",
            category="pkg",
            description="Python 的官方包管理器,用来安装第三方库",
            commands=["pip --version"],
            docs_url="https://pip.pypa.io/",
            common_cmds=[
                {"label": "查看版本", "cmd": "pip --version", "desc": "显示 pip 版本"},
                {"label": "安装包", "cmd": "pip install <包名>", "desc": "安装 Python 包"},
                {"label": "列出已安装包", "cmd": "pip list", "desc": "列出所有已安装的 Python 包"},
            ],
            registry_keys=[],
            fallback_paths=[],
        ),
        ToolDefinition(
            id="npm",
            display_name="npm",
            category="pkg",
            description="Node.js 的官方包管理器,用来安装 JavaScript 库",
            commands=["npm --version"],
            docs_url="https://docs.npmjs.com/",
            common_cmds=[
                {"label": "查看版本", "cmd": "npm --version", "desc": "显示 npm 版本"},
                {"label": "安装包", "cmd": "npm install <包名>", "desc": "安装 npm 包"},
                {"label": "初始化项目", "cmd": "npm init", "desc": "创建 package.json 文件"},
            ],
            registry_keys=[],
            fallback_paths=[],
        ),
        ToolDefinition(
            id="yarn",
            display_name="Yarn",
            category="pkg",
            description="Facebook 开发的 JavaScript 包管理器,比 npm 更快",
            commands=["yarn --version"],
            docs_url="https://yarnpkg.com/docs/",
            common_cmds=[
                {"label": "查看版本", "cmd": "yarn --version", "desc": "显示 Yarn 版本"},
                {"label": "安装包", "cmd": "yarn add <包名>", "desc": "添加依赖包"},
                {"label": "安装所有依赖", "cmd": "yarn install", "desc": "安装项目所有依赖"},
            ],
            registry_keys=[],
            fallback_paths=[],
        ),
        ToolDefinition(
            id="pnpm",
            display_name="pnpm",
            category="pkg",
            description="快速省磁盘空间的 Node.js 包管理器",
            commands=["pnpm --version"],
            docs_url="https://pnpm.io/",
            common_cmds=[
                {"label": "查看版本", "cmd": "pnpm --version", "desc": "显示 pnpm 版本"},
                {"label": "安装包", "cmd": "pnpm add <包名>", "desc": "添加依赖包"},
                {"label": "安装所有依赖", "cmd": "pnpm install", "desc": "安装项目所有依赖"},
            ],
            registry_keys=[],
            fallback_paths=[],
        ),
        ToolDefinition(
            id="maven",
            display_name="Maven",
            category="pkg",
            description="Java 项目的构建和依赖管理工具",
            commands=["mvn --version"],
            docs_url="https://maven.apache.org/guides/",
            common_cmds=[
                {"label": "查看版本", "cmd": "mvn --version", "desc": "显示 Maven 版本"},
                {"label": "编译项目", "cmd": "mvn compile", "desc": "编译 Java 项目"},
                {"label": "打包项目", "cmd": "mvn package", "desc": "将项目打包为 Jar"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Program Files\Apache\Maven\bin\mvn.cmd",
                r"C:\Tools\apache-maven-*\bin\mvn.cmd",
            ],
        ),
        ToolDefinition(
            id="gradle",
            display_name="Gradle",
            category="pkg",
            description="灵活的自动化构建工具,常用于 Java/Kotlin 项目",
            commands=["gradle --version"],
            docs_url="https://docs.gradle.org/",
            common_cmds=[
                {"label": "查看版本", "cmd": "gradle --version", "desc": "显示 Gradle 版本"},
                {"label": "编译项目", "cmd": "gradle build", "desc": "构建项目"},
                {"label": "运行测试", "cmd": "gradle test", "desc": "运行项目测试"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Program Files\Gradle\*\bin\gradle.bat",
                r"C:\Tools\gradle-*\bin\gradle.bat",
            ],
        ),
        ToolDefinition(
            id="cargo",
            display_name="Cargo",
            category="pkg",
            description="Rust 的包管理和构建工具",
            commands=["cargo --version"],
            docs_url="https://doc.rust-lang.org/cargo/",
            common_cmds=[
                {"label": "查看版本", "cmd": "cargo --version", "desc": "显示 Cargo 版本"},
                {"label": "创建新项目", "cmd": "cargo new <项目名>", "desc": "创建新的 Rust 项目"},
                {"label": "构建项目", "cmd": "cargo build", "desc": "编译 Rust 项目"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Users\%USERNAME%\.cargo\bin\cargo.exe",
            ],
        ),

        # ── 版本控制 ──────────────────────────────────────
        ToolDefinition(
            id="git",
            display_name="Git",
            category="vcs",
            description="代码版本管理工具,记录文件的修改历史",
            commands=["git --version"],
            docs_url="https://git-scm.com/doc",
            common_cmds=[
                {"label": "查看版本", "cmd": "git --version", "desc": "显示 Git 版本"},
                {"label": "克隆仓库", "cmd": "git clone <地址>", "desc": "从远程克隆代码仓库"},
                {"label": "提交更改", "cmd": "git commit -m '说明'", "desc": "提交已暂存的修改"},
            ],
            registry_keys=[
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Git_is1",
            ],
            fallback_paths=[
                r"C:\Program Files\Git\bin\git.exe",
                r"C:\Program Files (x86)\Git\bin\git.exe",
            ],
        ),
        ToolDefinition(
            id="gh",
            display_name="GitHub CLI",
            category="vcs",
            description="在命令行中管理 GitHub 仓库和项目",
            commands=["gh --version"],
            docs_url="https://cli.github.com/manual/",
            common_cmds=[
                {"label": "查看版本", "cmd": "gh --version", "desc": "显示 GitHub CLI 版本"},
                {"label": "登录 GitHub", "cmd": "gh auth login", "desc": "登录 GitHub 账号"},
                {"label": "查看仓库", "cmd": "gh repo view", "desc": "查看当前仓库信息"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Program Files\GitHub CLI\gh.exe",
                r"C:\Program Files (x86)\GitHub CLI\gh.exe",
            ],
        ),

        # ── 容器 ──────────────────────────────────────────
        ToolDefinition(
            id="docker",
            display_name="Docker",
            category="container",
            description="容器化工具,让程序在隔离环境中运行",
            commands=["docker --version"],
            extra_info_cmd="docker ps -q 2>nul | find /c /v \"\"",
            docs_url="https://docs.docker.com/",
            common_cmds=[
                {"label": "查看版本", "cmd": "docker --version", "desc": "显示 Docker 版本"},
                {"label": "查看运行中的容器", "cmd": "docker ps", "desc": "列出所有运行中的容器"},
                {"label": "查看所有镜像", "cmd": "docker images", "desc": "列出本地所有 Docker 镜像"},
            ],
            registry_keys=[
                r"SOFTWARE\Docker Inc.\Docker",
            ],
            fallback_paths=[
                r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
                r"C:\Program Files\Docker\Docker\resources\bin\com.docker.cli.exe",
            ],
        ),
        ToolDefinition(
            id="kubectl",
            display_name="kubectl",
            category="container",
            description="Kubernetes 的命令行工具,管理容器集群",
            commands=["kubectl version --client"],
            docs_url="https://kubernetes.io/docs/reference/kubectl/",
            common_cmds=[
                {"label": "查看版本", "cmd": "kubectl version --client", "desc": "显示 kubectl 客户端版本"},
                {"label": "查看节点", "cmd": "kubectl get nodes", "desc": "查看集群中的所有节点"},
                {"label": "查看 Pod", "cmd": "kubectl get pods", "desc": "查看所有 Pod 列表"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Program Files\Kubernetes\*\bin\kubectl.exe",
            ],
        ),

        # ── 数据库 ────────────────────────────────────────
        ToolDefinition(
            id="mysql",
            display_name="MySQL",
            category="db",
            description="最流行的开源关系型数据库",
            commands=["mysql --version"],
            docs_url="https://dev.mysql.com/doc/",
            common_cmds=[
                {"label": "查看版本", "cmd": "mysql --version", "desc": "显示 MySQL 客户端版本"},
                {"label": "登录数据库", "cmd": "mysql -u root -p", "desc": "以 root 登录 MySQL"},
                {"label": "显示数据库列表", "cmd": "SHOW DATABASES;", "desc": "在 MySQL 中查看所有数据库"},
            ],
            registry_keys=[
                r"SOFTWARE\MySQL AB",
                r"SOFTWARE\MySQL",
            ],
            fallback_paths=[
                r"C:\Program Files\MySQL\MySQL Server *\bin\mysql.exe",
                r"C:\Program Files (x86)\MySQL\MySQL Server *\bin\mysql.exe",
            ],
        ),
        ToolDefinition(
            id="postgresql",
            display_name="PostgreSQL",
            category="db",
            description="功能强大的开源关系型数据库",
            commands=["psql --version"],
            docs_url="https://www.postgresql.org/docs/",
            common_cmds=[
                {"label": "查看版本", "cmd": "psql --version", "desc": "显示 PostgreSQL 客户端版本"},
                {"label": "登录数据库", "cmd": "psql -U postgres", "desc": "以 postgres 用户登录"},
                {"label": "查看数据库列表", "cmd": "\\l", "desc": "在 psql 中列出所有数据库"},
            ],
            registry_keys=[
                r"SOFTWARE\PostgreSQL\Installations",
            ],
            fallback_paths=[
                r"C:\Program Files\PostgreSQL\*\bin\psql.exe",
            ],
        ),
        ToolDefinition(
            id="redis",
            display_name="Redis",
            category="db",
            description="高速内存数据库,常用于缓存和消息队列",
            commands=["redis-cli --version"],
            docs_url="https://redis.io/docs/",
            common_cmds=[
                {"label": "查看版本", "cmd": "redis-cli --version", "desc": "显示 Redis 客户端版本"},
                {"label": "连接服务器", "cmd": "redis-cli", "desc": "连接本地 Redis 服务器"},
                {"label": "测试连通", "cmd": "redis-cli ping", "desc": "测试 Redis 连接状态"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Program Files\Redis\redis-cli.exe",
                r"C:\Program Files\Redis\redis-server.exe",
            ],
        ),
        ToolDefinition(
            id="mongodb",
            display_name="MongoDB",
            category="db",
            description="流行的 NoSQL 文档数据库",
            commands=["mongod --version"],
            docs_url="https://www.mongodb.com/docs/",
            common_cmds=[
                {"label": "查看版本", "cmd": "mongod --version", "desc": "显示 MongoDB 服务器版本"},
                {"label": "连接数据库", "cmd": "mongosh", "desc": "使用 MongoDB Shell 连接数据库"},
                {"label": "导入数据", "cmd": "mongoimport --file 数据.json", "desc": "导入 JSON 数据到 MongoDB"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Program Files\MongoDB\Server\*\bin\mongod.exe",
                r"C:\Program Files\MongoDB\Server\*\bin\mongosh.exe",
            ],
        ),

        # ── 云工具 ────────────────────────────────────────
        ToolDefinition(
            id="awscli",
            display_name="AWS CLI",
            category="cloud",
            description="Amazon Web Services 的命令行管理工具",
            commands=["aws --version"],
            docs_url="https://docs.aws.amazon.com/cli/",
            common_cmds=[
                {"label": "查看版本", "cmd": "aws --version", "desc": "显示 AWS CLI 版本"},
                {"label": "配置账号", "cmd": "aws configure", "desc": "配置 AWS 访问密钥"},
                {"label": "列出 S3 桶", "cmd": "aws s3 ls", "desc": "列出所有 S3 存储桶"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Program Files\Amazon\AWSCLIV2\aws.exe",
                r"C:\Program Files (x86)\Amazon\AWSCLIV2\aws.exe",
            ],
        ),

        # ── 构建工具 ──────────────────────────────────────
        ToolDefinition(
            id="make",
            display_name="Make",
            category="build",
            description="经典的自动化构建工具,通过 Makefile 定义任务",
            commands=["make --version"],
            docs_url="https://www.gnu.org/software/make/manual/",
            common_cmds=[
                {"label": "查看版本", "cmd": "make --version", "desc": "显示 Make 版本"},
                {"label": "执行构建", "cmd": "make", "desc": "执行默认构建目标"},
                {"label": "清理构建", "cmd": "make clean", "desc": "清理构建产物"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Program Files\Git\usr\bin\make.exe",
                r"C:\Program Files (x86)\Git\usr\bin\make.exe",
                r"C:\msys64\usr\bin\make.exe",
            ],
        ),
        ToolDefinition(
            id="cmake",
            display_name="CMake",
            category="build",
            description="跨平台的编译配置工具,生成构建文件",
            commands=["cmake --version"],
            docs_url="https://cmake.org/documentation/",
            common_cmds=[
                {"label": "查看版本", "cmd": "cmake --version", "desc": "显示 CMake 版本"},
                {"label": "生成构建文件", "cmd": "cmake .", "desc": "在当前目录生成构建配置"},
                {"label": "编译项目", "cmd": "cmake --build .", "desc": "编译 CMake 配置的项目"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Program Files\CMake\bin\cmake.exe",
                r"C:\Program Files (x86)\CMake\bin\cmake.exe",
            ],
        ),

        # ── 运行时/其他 ──────────────────────────────────
        ToolDefinition(
            id="flutter",
            display_name="Flutter",
            category="runtime",
            description="Google 的跨平台 UI 开发框架,一套代码运行多端",
            commands=["flutter --version"],
            docs_url="https://docs.flutter.dev/",
            common_cmds=[
                {"label": "查看版本", "cmd": "flutter --version", "desc": "显示 Flutter 版本"},
                {"label": "检查环境", "cmd": "flutter doctor", "desc": "检查 Flutter 开发环境状态"},
                {"label": "运行应用", "cmd": "flutter run", "desc": "在设备上运行 Flutter 应用"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Program Files\Flutter\bin\flutter.exe",
                r"C:\Users\%USERNAME%\flutter\bin\flutter.exe",
            ],
        ),
        ToolDefinition(
            id="wsl",
            display_name="WSL",
            category="runtime",
            description="Windows 子系统 Linux,在 Windows 中运行 Linux",
            commands=["wsl --version"],
            docs_url="https://learn.microsoft.com/en-us/windows/wsl/",
            common_cmds=[
                {"label": "查看版本", "cmd": "wsl --version", "desc": "显示 WSL 版本信息"},
                {"label": "列出发行版", "cmd": "wsl -l -v", "desc": "查看已安装的 Linux 发行版"},
                {"label": "进入 Linux", "cmd": "wsl", "desc": "启动默认 Linux 发行版"},
            ],
            registry_keys=[],
            fallback_paths=[
                r"C:\Windows\System32\wsl.exe",
            ],
        ),
    ]


# ── 公开访问接口 ──────────────────────────────────────────

_TOOLS: list[ToolDefinition] | None = None
_TOOLS_MAP: dict[str, ToolDefinition] | None = None


def get_all_tools() -> list[ToolDefinition]:
    """返回所有工具定义列表(排序后)"""
    global _TOOLS
    if _TOOLS is None:
        _TOOLS = sorted(_build_tools(), key=lambda t: (CATEGORY_ORDER.get(t.category, 99), t.display_name))
    return list(_TOOLS)


def get_tool(tool_id: str) -> ToolDefinition | None:
    """按 ID 查找单个工具"""
    global _TOOLS_MAP
    if _TOOLS_MAP is None:
        _TOOLS_MAP = {t.id: t for t in get_all_tools()}
    return _TOOLS_MAP.get(tool_id)


def get_tools_by_category(category: str) -> list[ToolDefinition]:
    """获取指定分类下的所有工具"""
    return [t for t in get_all_tools() if t.category == category]


def get_category_tool_count(category: str) -> tuple[int, int]:
    """返回 (已安装数, 总数) 用于分类标题"""
    # 注意:此函数只返回总数,已安装数由外部传入
    tools = get_tools_by_category(category)
    return len([t for t in tools]), len(tools)