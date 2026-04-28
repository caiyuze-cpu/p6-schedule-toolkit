# P6 Schedule Toolkit

**CSV → XER → P6** 施工进度计划生成工具包。从CSV格式的进度计划自动生成Primavera P6可导入的XER文件，适用于风电、光伏、基建等施工进度计划编制。

## 特点

- **AI驱动**：配合Claude Code / Cursor / GitHub Copilot等AI Agent使用，用自然语言描述工程信息，AI自动生成CSV进度计划
- **CPM网络校验**：自动检测循环依赖、断链、孤立节点
- **P6原生兼容**：生成的XER文件可直接导入Primavera P6，支持约束、里程碑、多种关系类型
- **只写工期不写日期**：由P6排程引擎计算所有日期和关键线路
- **结果读取**：从P6 SQLite数据库读取排程结果，无需P6客户端也可验证

## 快速开始

### 安装

```bash
pip install -e .
```

需要 Python 3.10+。

### 1. 编制CSV进度计划

用AI Agent（推荐）或手动编辑，按以下格式填写：

```csv
wbs_path,task_code,task_name,task_type,duration_days,predecessor_code,rel_type,lag_days,constraint_type,constraint_date
施工准备,1100,开工里程碑,Milestone,0,,,,CS_MSO,2026-06-01
施工准备,1110,项目部组建,Task,3,,,,
基础工程,2010,WT01风机基础,Task,35,1100,FS,0,,
```

详细格式说明见 [docs/csv-format.md](docs/csv-format.md)。

### 2. 转换为XER

```bash
p6-to-xer schedule.csv output.xer --project "My Project Schedule" --start 2026-06-01
```

或直接使用Python：

```bash
python -m p6_schedule.csv_to_xer schedule.csv output.xer --project "My Project Schedule" --start 2026-06-01
```

### 3. 导入P6

1. 打开 Primavera P6
2. **File → Import → XER** → 选择生成的 `.xer` 文件
3. 打开项目，按 **F9** 排程
4. P6自动计算所有日期、关键线路和浮时

### 4. 查看排程结果

```bash
# 列出所有项目
p6-results --db PPMDBSQLite.db

p6-results -p "MyProject" --milestones

# 关键路径分析
p6-results -p "MyProject" --path

# 文本甘特图
p6-results -p "MyProject" --gantt
```

## 与AI Agent配合使用（推荐）

本项目天然适合配合AI编程助手使用。工作流程：

```
用户描述工程信息 → AI Agent生成CSV → p6-to-xer转换 → P6导入排程 → p6-results验证
```

### Claude Code Skill

如果你使用Claude Code，项目自带2个skill文件，复制到 `~/.claude/skills/` 即可：

```bash
cp skills/p6-schedule-generator.md ~/.claude/skills/
cp skills/p6-results-reader.md ~/.claude/skills/
```

- **p6-schedule-generator**: AI根据工程信息生成CSV进度计划、CPM验证、生成XER
- **p6-results-reader**: AI读取P6数据库，分析里程碑和关键路径

只需告诉Claude Code你的工程信息（风机数量、合同里程碑日期、资源约束等），它会自动：
- 编制CSV进度计划
- 运行 `p6-deploy` CPM验证+生成XER
- 指导你导入P6并读取结果验证

### 其他AI工具

`docs/` 目录下的文档可以直接作为AI Agent的参考知识：
- `scheduling-guide.md` — 施工进度计划编制要点
- `xer-format.md` — XER格式关键要求
- `csv-format.md` — CSV格式详细说明
- `troubleshooting.md` — 常见问题排查

## 项目结构

```
p6-schedule-toolkit/
├── src/p6_schedule/        # Python包
│   ├── csv_to_xer.py       # CSV→XER转换器
│   ├── read_results.py     # P6结果读取器
│   ├── validate.py         # CPM网络校验
│   └── cli.py              # 命令行入口
├── docs/                   # 文档（也可作为AI知识库）
│   ├── csv-format.md       # CSV格式说明
│   ├── xer-format.md       # XER格式要求
│   ├── scheduling-guide.md # 编制要点
│   └── troubleshooting.md  # 问题排查
├── examples/               # 样例
│   └── wind_farm_12turbines.csv
├── skills/                 # Claude Code skills
│   ├── p6-schedule-generator.md
│   └── p6-results-reader.md
└── tests/                  # 测试
```

## 约束使用规则

| 约束类型 | 含义 | 使用场景 |
|---------|------|---------|
| `CS_MSO` | Must Start On（必须开始于） | 合同硬性里程碑节点 |

**关键限制**：P6通过XER只识别 `CS_MSO`，`CS_MFEO`/`CS_MFIN` 会被静默忽略。

**约束只加在里程碑上**，普通工序的日期由P6排程自然计算。

**不要设置plan_end_date**（PROJECT表字段30），否则P6从该日期做反向推算，所有工序都获得正浮时，不会出现关键线路。

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| P6导入后无项目 | %F/%R字段数不匹配 | 逐表核对字段数量 |
| 货币对话框阻止导入 | 包含CURRTYPE表 | 删除CURRTYPE相关行 |
| 无关键线路 | 设置了plan_end_date | PROJECT字段30设None |
| CS_MFEO约束无效 | P6 XER只认CS_MSO | 统一用CS_MSO |
| 里程碑浮时异常 | 里程碑有多前置但有约束 | 约束覆盖网络逻辑，正常 |

更多问题见 [docs/troubleshooting.md](docs/troubleshooting.md)。

## 贡献

欢迎提交Issue和PR！特别是：

- 新的行业模板（光伏、火电、输变电等）
- 不同P6版本的兼容性测试
- 文档翻译和改进
- Bug修复和新功能

## License

MIT
