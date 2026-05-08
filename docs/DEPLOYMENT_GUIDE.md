# 部署指南与CI/CD使用说明

## 🚀 快速部署

### 本地开发部署
```bash
# 1. 克隆代码
git clone <repo-url>
cd coin-collect

# 2. 配置环境变量
cp .env.example .env
# 编辑.env文件，配置数据库等信息

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库
python init_db.py

# 5. 启动开发服务
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker本地部署
```bash
# 1. 构建镜像
docker build -t coin-collect-api .

# 2. 启动容器
docker run -d \
  --name coin-collect-api \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  coin-collect-api

# 或者使用docker-compose
docker-compose up -d
```

---

## 🤖 CI/CD 自动化流程说明

### 流程概览
```
代码提交 → PR到master → 代码检查 → 单元测试 → 核心功能测试 → 构建镜像 → 自动部署测试环境 → 人工审核 → 部署生产环境 → 结果通知
```

### 触发条件
1. **PR触发**：提交PR到master分支时，自动触发CI流程（代码检查+单元测试+核心功能测试）
2. **Push触发**：代码合并到master分支时，自动触发全流程（CI+构建+测试环境部署）
3. **手动触发**：在GitHub Actions页面可以手动触发，支持选择是否运行全量测试、是否部署到生产环境

### 各阶段说明
| 阶段 | 说明 | 阻断条件 |
|------|------|----------|
| 代码质量检查 | 代码格式检查（black/isort）、代码质量检查（flake8）、安全漏洞扫描（bandit）、敏感信息扫描 | 格式错误、发现敏感信息时阻断 |
| 单元测试 | 运行所有单元测试，生成覆盖率报告 | 单元测试不通过时阻断 |
| 核心功能测试 | 运行黄金用例回放测试、基础评估测试，验证核心催收逻辑 | 核心用例通过率低于阈值时阻断 |
| 构建Docker镜像 | 构建生产环境Docker镜像，推送到镜像仓库 | 构建失败时阻断 |
| 部署到测试环境 | 自动部署最新镜像到测试环境，自动健康检查 | 部署失败、健康检查不通过时阻断 |
| 部署到生产环境 | 需要人工审核通过后才会部署到生产环境 | 审核不通过、部署失败、健康检查不通过时阻断 |
| 结果通知 | 流程结束后通知相关人员结果（支持企业微信、飞书、邮件等） | - |

---

## 🔧 CI/CD 配置说明

### 1. 必要配置项（Secrets）
需要在GitHub仓库的Settings → Secrets and variables → Actions中添加以下secrets：

| Secret名称 | 说明 | 示例 |
|-----------|------|------|
| `DOCKER_REGISTRY_USER` | Docker镜像仓库用户名 | `your-username` |
| `DOCKER_REGISTRY_PASSWORD` | Docker镜像仓库密码 | `your-password` |
| `TEST_SERVER_HOST` | 测试服务器IP地址 | `192.168.1.100` |
| `TEST_SERVER_USER` | 测试服务器登录用户名 | `root` |
| `TEST_SERVER_SSH_KEY` | 测试服务器SSH私钥 | `-----BEGIN RSA PRIVATE KEY-----...` |
| `TEST_DB_URI` | 测试环境数据库连接地址 | `mysql+pymysql://user:pass@host:port/db` |
| `PROD_SERVER_HOST` | 生产服务器IP地址 | `192.168.1.200` |
| `PROD_SERVER_USER` | 生产服务器登录用户名 | `root` |
| `PROD_SERVER_SSH_KEY` | 生产服务器SSH私钥 | `-----BEGIN RSA PRIVATE KEY-----...` |
| `PROD_DB_URI` | 生产环境数据库连接地址 | `mysql+pymysql://user:pass@host:port/db` |
| `WECHAT_WEBHOOK` | 企业微信通知机器人webhook（可选） | `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx` |

### 2. 环境配置
如果使用GitLab CI/CD，只需要把.github/workflows/ci-cd.yml里的配置转换为.gitlab-ci.yml格式即可，逻辑完全一致。

---

## 📦 生产部署建议

### 服务器要求
- 配置：4核8G以上（语音处理需要较多CPU资源）
- 系统：Ubuntu 22.04 LTS / Debian 12
- 网络：需要能访问语音服务API、带宽10M以上
- 存储：至少100G可用空间，用于存储通话录音、日志等

### 部署架构建议
```
用户 → 负载均衡（Nginx/ALB） → API服务集群 → 数据库（主从）
                                    ↓
                             对象存储（录音存储）
```

### 生产环境检查清单
1. ✅ 数据库已配置主从复制，定期备份
2. ✅ 服务已配置监控告警（CPU、内存、磁盘、接口响应时间、错误率）
3. ✅ 日志已集中收集，可查询追溯
4. ✅ 敏感配置全部通过环境变量注入，没有硬编码
5. ✅ 已配置HTTPS证书，API启用HTTPS访问
6. ✅ 已配置防火墙，只开放必要端口（80/443/SSH端口）
7. ✅ 已配置服务自动重启和健康检查
8. ✅ 已准备回滚预案，出现问题可快速切回旧版本

### 回滚流程
如果上线后出现问题，按照以下步骤回滚：
```bash
# 1. 在服务器上查看可用的镜像版本
docker images | grep coin-collect-api

# 2. 停止当前服务
docker stop coin-collect-api

# 3. 启动上一个稳定版本（比如backup-20240501120000）
docker run -d \
  --name coin-collect-api \
  --restart always \
  -p 80:8000 \
  -e DB_URI=${PROD_DB_URI} \
  -e ENV=production \
  -v /opt/coin-collect/data:/app/data \
  -v /opt/coin-collect/logs:/app/logs \
  coin-collect-api:backup-20240501120000

# 4. 验证服务是否正常
curl -f http://localhost:80/health
```

---

## 📊 监控建议
建议配置以下监控指标：
### 业务指标
- 外呼成功率
- 承诺还款率
- 平均通话时长
- 用户抗拒率
- 合规违规次数

### 技术指标
- API响应时间
- 错误率
- CPU/内存/磁盘使用率
- ASR识别准确率
- TTS合成成功率
- 打断准确率

### 告警规则
- 错误率>1%告警
- 响应时间>1s告警
- CPU>80%持续5分钟告警
- 磁盘使用率>85%告警
- 服务宕机立刻告警
