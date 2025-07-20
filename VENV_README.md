# vnpy 虚拟环境使用说明

## 环境配置完成 ✅

你的vnpy项目已经成功配置了Python 3.12.10虚拟环境，完全满足项目要求（>=3.10）。

## 环境信息

- **Python版本**: 3.12.10
- **虚拟环境路径**: `./venv/`
- **Python安装路径**: `C:\dev\Winpython64-3.12.10.1dot\WPy64-312101\python\`
- **vnpy版本**: 4.1.0

## 使用方法

### 方法1: 使用批处理文件（推荐）
```bash
# 双击运行或在命令行中执行
activate_venv.bat
```

### 方法2: 使用PowerShell脚本
```powershell
# 在PowerShell中执行
.\activate_venv.ps1
```

### 方法3: 手动激活
```powershell
# PowerShell
.\venv\Scripts\Activate.ps1

# 或者使用cmd
venv\Scripts\activate.bat
```

## 验证安装

激活环境后，可以运行以下命令验证：

```python
# 检查Python版本
python --version

# 检查vnpy版本
python -c "import vnpy; print('vnpy version:', vnpy.__version__)"

# 测试核心模块
python -c "import vnpy.trader; import vnpy.chart; import vnpy.alpha; print('All modules OK!')"
```

## 已安装的依赖

### 核心依赖
- vnpy 4.1.0
- PySide6 6.8.2.1 (GUI框架)
- pandas 2.3.1
- numpy 2.3.1
- ta-lib 0.6.4 (技术分析库)
- plotly 6.2.0 (图表库)
- pyqtgraph 0.13.7 (实时图表)
- 等等...

### Brisk模块依赖
- fastapi 0.116.1 (Web框架)
- uvicorn 0.35.0 (ASGI服务器)
- pydantic 2.11.7 (数据验证)
- loguru 0.7.3 (日志库)

### Alpha模块依赖（可选）
- polars 1.31.0
- scikit-learn 1.7.1
- torch 2.7.1 (PyTorch)
- lightgbm 4.6.0
- matplotlib 3.10.3
- seaborn 0.13.2
- 等等...

## 运行示例

激活环境后，可以运行项目中的示例：

```bash
# 运行无UI示例
python examples/no_ui/run.py

# 运行客户端示例
python examples/client_server/run_client.py

# 运行数据记录器
python examples/data_recorder/data_recorder.py

# 运行Brisk服务
cd brisk
launch_tick_server_venv.bat
```

## 注意事项

1. **环境隔离**: 这个虚拟环境完全独立，不会影响你的系统Python 3.9
2. **激活提示**: 激活后命令行前面会显示 `(venv)`
3. **退出环境**: 使用 `deactivate` 命令退出虚拟环境
4. **IDE配置**: 在IDE中设置Python解释器为 `./venv/Scripts/python.exe`

## 故障排除

如果遇到问题：

1. **权限问题**: 以管理员身份运行PowerShell
2. **执行策略**: 如果PowerShell脚本无法执行，运行：
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
3. **路径问题**: 确保在项目根目录下执行激活命令

## 更新依赖

如果需要更新依赖：

```bash
# 激活环境后
pip install --upgrade package_name

# 或者重新安装项目
pip install -e .
``` 