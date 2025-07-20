# vnpy 开发模式说明

## 当前开发环境配置 ✅

你的vnpy项目已经配置为**可编辑开发模式**，这是进行框架开发的最佳实践。

## 开发模式 vs 安装模式

### ❌ 普通安装模式（不推荐用于开发）
```bash
pip install .
```
**问题：**
- 修改源代码后需要重新安装
- 代码修改不会立即生效
- 版本管理复杂

### ✅ 可编辑安装模式（推荐用于开发）
```bash
pip install -e .
```
**优势：**
- 直接链接到源代码目录
- 修改代码立即生效
- 无需重新安装
- 便于调试和开发

## 验证开发模式

### 检查安装状态
```bash
# 查看vnpy模块路径
python -c "import vnpy; print('vnpy path:', vnpy.__file__)"
# 输出: D:\dev\github\vnpy\vnpy\__init__.py
```

### 测试代码修改
1. 修改 `vnpy/__init__.py` 中的版本号
2. 立即测试修改是否生效：
   ```python
   import vnpy
   print(vnpy.__version__)  # 应该显示修改后的版本
   ```

## 开发工作流程

### 1. 修改源代码
直接在 `vnpy/` 目录下修改文件：
```
vnpy/
├── trader/          # 交易引擎
├── chart/           # 图表模块
├── alpha/           # Alpha策略
├── event/           # 事件系统
└── ...
```

### 2. 立即测试
修改后无需重新安装，直接运行测试：
```bash
# 测试核心模块
python -c "import vnpy.trader; print('trader module OK')"

# 运行示例
python examples/no_ui/run.py

# 运行你的代码
python your_script.py
```

### 3. 版本管理
```bash
# 查看当前安装的包
pip list | grep vnpy

# 如果需要重新安装依赖
pip install -e . --force-reinstall
```

## 开发最佳实践

### 1. 代码组织
```
your_project/
├── vnpy/              # vnpy框架源码（可编辑安装）
├── your_strategies/   # 你的策略代码
├── your_scripts/      # 你的脚本
└── examples/          # 示例代码
```

### 2. 导入方式
```python
# 推荐：直接导入vnpy模块
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import TickData
from vnpy.chart.widget import ChartWidget

# 不推荐：使用相对导入（除非在vnpy包内部）
# from ..trader.engine import MainEngine
```

### 3. 调试技巧
```python
# 在代码中添加调试信息
import vnpy
print(f"vnpy path: {vnpy.__file__}")
print(f"vnpy version: {vnpy.__version__}")

# 使用IDE调试
# 在PyCharm/VSCode中设置断点
# 直接调试你的代码
```

## 常见问题解决

### 1. 修改不生效
```bash
# 检查是否为可编辑安装
pip show vnpy
# 应该显示: Location: D:\dev\github\vnpy

# 如果不是，重新安装
pip uninstall vnpy -y
pip install -e .
```

### 2. 依赖问题
```bash
# 重新安装所有依赖
pip install -e . --force-reinstall

# 安装额外依赖
pip install -e ".[alpha]"
```

### 3. 版本冲突
```bash
# 清理环境
pip uninstall vnpy -y
pip cache purge

# 重新安装
pip install -e .
```

## 生产环境部署

当开发完成后，如果要部署到生产环境：

### 1. 打包发布
```bash
# 构建分发包
python -m build

# 或使用hatchling
hatch build
```

### 2. 生产安装
```bash
# 在生产环境中安装
pip install vnpy-4.1.0.tar.gz
```

## 总结

✅ **当前状态**: 可编辑开发模式
✅ **优势**: 修改立即生效，便于开发
✅ **推荐**: 继续使用此模式进行开发

现在你可以：
- 直接修改 `vnpy/` 目录下的任何文件
- 修改后立即测试，无需重新安装
- 使用IDE进行调试和开发
- 享受完整的开发体验 