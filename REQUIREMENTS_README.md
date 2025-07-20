# Requirements 文件使用说明

## 文件结构

```
requirements.txt          # 核心依赖
requirements-alpha.txt    # Alpha模块依赖
requirements-brisk.txt    # Brisk模块依赖
requirements-dev.txt      # 开发工具依赖
requirements-all.txt      # 所有依赖（包含引用）
```

## 使用方法

### 1. 安装核心依赖
```bash
# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 安装核心依赖
pip install -r requirements.txt
```

### 2. 安装特定模块依赖
```bash
# 安装Alpha模块依赖
pip install -r requirements-alpha.txt

# 安装Brisk模块依赖
pip install -r requirements-brisk.txt

# 安装开发工具依赖
pip install -r requirements-dev.txt
```

### 3. 安装所有依赖
```bash
# 安装所有依赖（推荐）
pip install -r requirements-all.txt
```

### 4. 开发环境完整安装
```bash
# 安装所有依赖包括开发工具
pip install -r requirements-all.txt
pip install -r requirements-dev.txt
```

## 依赖分类说明

### Core Dependencies (requirements.txt)
- **GUI框架**: PySide6 - Qt界面框架
- **数据处理**: numpy, pandas - 数值计算和数据分析
- **技术分析**: ta-lib - 技术指标库
- **图表**: pyqtgraph, plotly - 图表绘制
- **通信**: pyzmq - 消息队列
- **工具**: loguru, tqdm - 日志和进度条

### Alpha Dependencies (requirements-alpha.txt)
- **数据处理**: polars, pyarrow - 高性能数据处理
- **机器学习**: scikit-learn, lightgbm, torch - ML框架
- **科学计算**: scipy - 科学计算库
- **Alpha研究**: alphalens-reloaded - Alpha因子分析

### Brisk Dependencies (requirements-brisk.txt)
- **Web框架**: fastapi, uvicorn - 现代Web API框架
- **数据验证**: pydantic - 数据模型验证
- **日志**: loguru - 结构化日志

### Development Dependencies (requirements-dev.txt)
- **构建工具**: hatchling, babel - 包构建和国际化
- **类型检查**: pandas-stubs, mypy - 类型提示和检查
- **代码质量**: ruff - 代码格式化和检查
- **测试**: pytest, pytest-cov - 单元测试和覆盖率
- **文档**: sphinx - 文档生成

## 版本管理

### 固定版本 vs 最低版本
```bash
# 固定版本（推荐用于生产）
PySide6==6.8.2.1

# 最低版本（推荐用于开发）
numpy>=2.2.3
```

### 更新依赖
```bash
# 更新特定包
pip install --upgrade package_name

# 更新requirements文件中的版本
pip freeze > requirements-current.txt

# 比较版本差异
diff requirements.txt requirements-current.txt
```

## 环境重建

### 完整重建
```bash
# 删除虚拟环境
deactivate
Remove-Item -Recurse -Force venv

# 重新创建环境
& "C:\dev\Winpython64-3.12.10.1dot\WPy64-312101\python\python.exe" -m venv venv
.\venv\Scripts\Activate.ps1

# 安装所有依赖
pip install --upgrade pip wheel
pip install -r requirements-all.txt

# 可编辑安装vnpy
pip install -e .
```

### 增量更新
```bash
# 更新requirements文件
pip install -r requirements-all.txt --upgrade

# 重新安装vnpy（保持可编辑模式）
pip install -e . --force-reinstall
```

## 常见问题

### 1. 依赖冲突
```bash
# 查看依赖树
pip show package_name

# 解决冲突
pip install --upgrade package_name
```

### 2. 编译错误
```bash
# 安装编译工具
pip install wheel setuptools

# 使用预编译包
pip install --only-binary=all package_name
```

### 3. 网络问题
```bash
# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 或使用vnpy镜像
pip install -r requirements.txt --extra-index-url https://pypi.vnpy.com
```

## 最佳实践

1. **开发环境**: 使用 `requirements-all.txt` + `requirements-dev.txt`
2. **生产环境**: 使用固定版本号
3. **CI/CD**: 使用 `requirements-all.txt`
4. **定期更新**: 每月检查依赖更新
5. **版本锁定**: 重要项目使用 `pip freeze` 锁定版本

## 自动化脚本

### 快速安装脚本
```bash
# install_deps.bat
@echo off
call venv\Scripts\activate.bat
pip install -r requirements-all.txt
pip install -e .
echo Dependencies installed successfully!
pause
```

### PowerShell版本
```powershell
# install_deps.ps1
& ".\venv\Scripts\Activate.ps1"
pip install -r requirements-all.txt
pip install -e .
Write-Host "Dependencies installed successfully!" -ForegroundColor Green
``` 