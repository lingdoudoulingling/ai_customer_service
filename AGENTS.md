# Project Rules

## Environment

- 当前项目 Python conda 环境为:
  `ai-assistant`
- 如需安装依赖，优先参考 `requirements.txt`
- 当前项目启动入口为:
  `python app.py`
- 当前系统 shell 为 PowerShell
- Git 路径为:
  `D:\Git\cmd\git.exe`
- GitHub 仓库地址为:
  `https://github.com/lingdoudoulingling/ai_customer_service.git`

## Output And Docs

- Markdown 文档在需要图示表达时，使用 Mermaid 语法
- Mermaid 适用于流程图、系统架构图、状态转换图、类关系图、数据分析图表等
- Python 代码中如需避免终端中文输出乱码，可使用:
  `sys.stdout.reconfigure(encoding='utf-8')`

## Coding Style

- 代码规范遵循 PEP 8

## Design Principles

- 单一职责:
  一个函数或类只做一件事
- 模块化:
  按功能拆分包，不写巨型文件
- 解耦:
  业务逻辑、工具、接口分层
- DRY:
  不要重复代码，重复逻辑抽成工具函数
- KISS:
  保持简单，不要过度设计
