# 批量评估工具使用指南

## 📁 工具概览

批量评估工具包含两个脚本，用于快速评估多个Agent执行场景：

1. **batch_download_replays.py** - 批量下载replay文件
2. **batch_evaluate.py** - 批量评估并生成报告

## 🚀 快速开始

### 前置要求

```bash
# 安装依赖
pip install requests openpyxl
```

### 完整工作流

```bash
# Step 1: 准备replay链接列表
# 创建 replay_links.txt，每行一个链接
cat > replay_links.txt << EOF
https://example.com/replay/M3/...
https://example.com/replay/M4/...
https://example.com/replay/M5/...
EOF

# Step 2: 批量下载replay（5分钟）
python tests/agent_contract/batch_download_replays.py \
    replay_links.txt \
    -o tests/agent_contract/replays/

# Step 3: 批量评估（1分钟，并行处理）
python tests/agent_contract/batch_evaluate.py \
    tests/agent_contract/replays/ \
    --auto-discover \
    --parallel 4 \
    -o results/evaluation.xlsx
```

## 📖 详细用法

### 1. 批量下载replay

#### 从文件读取链接
```bash
python tests/agent_contract/batch_download_replays.py \
    replay_links.txt \
    -o replays/
```

#### 直接传递链接
```bash
python tests/agent_contract/batch_download_replays.py \
    https://example.com/replay1 \
    https://example.com/replay2 \
    -o replays/
```

#### 设置超时
```bash
python tests/agent_contract/batch_download_replays.py \
    replay_links.txt \
    -o replays/ \
    --timeout 60
```

#### 输出结构
```
replays/
├── M3/
│   └── replay.json
├── M4/
│   └── replay.json
├── M5/
│   └── replay.json
└── download_report.json  # 下载报告
```

---

### 2. 批量评估

#### 自动发现并评估所有场景
```bash
python tests/agent_contract/batch_evaluate.py \
    replays/ \
    --auto-discover
```

#### 指定特定场景
```bash
python tests/agent_contract/batch_evaluate.py \
    replays/M3/ \
    replays/M4/ \
    replays/M5/
```

#### 并行处理（加速4倍）
```bash
python tests/agent_contract/batch_evaluate.py \
    replays/ \
    --auto-discover \
    --parallel 4
```

#### 生成Excel报告
```bash
python tests/agent_contract/batch_evaluate.py \
    replays/ \
    --auto-discover \
    -o results/scores.xlsx
```

#### 生成JSON报告
```bash
python tests/agent_contract/batch_evaluate.py \
    replays/ \
    --auto-discover \
    -o results/summary.json
```

---

## 📊 输出示例

### 终端输出
```
Found 6 scenarios to evaluate
Processing with 4 worker(s)...

Processing M3... ✓ PASS  score=85
Processing M4... ✓ PASS  score=90
Processing M5... ✗ FAIL  score=65
Processing M6... ✓ PASS  score=88
Processing M7... ✓ PASS  score=92
Processing M8... ✓ PASS  score=87

============================================================
Evaluation Summary:
  Total:   6
  PASS:    5
  FAIL:    1
  ERROR:   0
  Rate:    83.3%
============================================================

Detailed Results:
✓ M3        score=85
✓ M4        score=90
✗ M5        score=65
✓ M6        score=88
✓ M7        score=92
✓ M8        score=87

✓ JSON report saved to: evaluation_summary.json
```

### JSON报告格式
```json
{
  "evaluated_at": "2024-08-25T10:30:00Z",
  "total": 6,
  "passed": 5,
  "failed": 1,
  "errors": 0,
  "pass_rate": "83.3%",
  "results": [
    {
      "scenario_id": "M3",
      "task_result": "PASS",
      "quality_score": 85,
      "oracle_pass": true,
      "critical_violations": {},
      "pass": true
    },
    ...
  ]
}
```

### Excel报告
包含以下列：
- 场景ID
- 任务结果
- 质量分数
- 诊断分数
- Oracle通过
- 关键违规
- 通过状态

失败的行会高亮显示。

---

## ⚡ 性能对比

### 原有流程（Codex串行）
```
31个场景 × 40秒/场景 = 20分钟（review + score）
```

### 优化后流程（批量处理）
```
下载replay:     5分钟  （一次性下载31个）
批量评估:       1分钟  （并行处理，纯Python计算）
─────────────────────────
总计:           6分钟  （节省14分钟，70%提速）
```

### 进一步优化（增量测试）
```
只测试变更的场景（如M3-M5）:
下载:  30秒
评估:  15秒
─────────
总计:  45秒
```

---

## 🔧 高级用法

### 集成到CI/CD
```yaml
# .github/workflows/test.yml
- name: Download replays
  run: |
    python tests/agent_contract/batch_download_replays.py \
      ${{ secrets.REPLAY_LINKS }} \
      -o replays/

- name: Evaluate
  run: |
    python tests/agent_contract/batch_evaluate.py \
      replays/ \
      --auto-discover \
      --parallel 4 \
      -o results/scores.xlsx

- name: Upload results
  uses: actions/upload-artifact@v3
  with:
    name: evaluation-results
    path: results/
```

### 增量测试（只测新场景）
```bash
# 只下载M3-M8的replay
python tests/agent_contract/batch_download_replays.py \
    $(cat new_scenarios.txt) \
    -o replays/

# 只评估这些新场景
python tests/agent_contract/batch_evaluate.py \
    replays/M3/ replays/M4/ replays/M5/ \
    replays/M6/ replays/M7/ replays/M8/ \
    --parallel 4
```

### 对比不同版本
```bash
# 评估v1版本
python tests/agent_contract/batch_evaluate.py \
    replays/v1/ --auto-discover -o results/v1.json

# 评估v2版本
python tests/agent_contract/batch_evaluate.py \
    replays/v2/ --auto-discover -o results/v2.json

# 对比结果
python scripts/compare_results.py results/v1.json results/v2.json
```

---

## 🐛 故障排除

### 问题1: 下载失败
```
Error: Download failed: Connection timeout
```
**解决**: 增加超时时间
```bash
python batch_download_replays.py links.txt -o replays/ --timeout 120
```

### 问题2: 找不到replay.json
```
Warning: replays/M3/ does not contain replay.json
```
**解决**: 检查目录结构，确保replay.json在正确位置
```bash
ls replays/M3/replay.json  # 应该存在
```

### 问题3: 导入错误
```
Error: Cannot import required modules
```
**解决**: 从SheetPilot仓库根目录运行
```bash
cd D:/bitexcel/SheetPilot
python tests/agent_contract/batch_evaluate.py replays/ --auto-discover
```

### 问题4: 场景ID识别错误
```
Saved to replays/unknown/replay.json
```
**解决**: 手动重命名目录或在replay中添加scenario字段
```bash
mv replays/unknown replays/M3
```

---

## 📝 文件结构

### 下载后的目录结构
```
tests/agent_contract/
├── batch_download_replays.py  # 下载工具
├── batch_evaluate.py           # 评估工具
├── replays/                    # replay存储目录
│   ├── M3/
│   │   ├── replay.json         # Agent执行记录
│   │   └── output.xlsx         # （可选）输出文件
│   ├── M4/
│   │   └── replay.json
│   └── download_report.json    # 下载报告
├── results/                    # 评估结果
│   ├── evaluation.xlsx         # Excel报告
│   └── summary.json            # JSON报告
└── BATCH_EVALUATION_GUIDE.md  # 本文档
```

---

## 🎯 最佳实践

### 1. 日常开发（快速验证）
```bash
# 只测试修改的1-2个场景
python batch_evaluate.py replays/M3/ replays/M4/
```

### 2. 提交前（系列测试）
```bash
# 测试M系列全部8个场景
python batch_evaluate.py replays/M* --parallel 4
```

### 3. 发布前（全量测试）
```bash
# 测试所有31个场景并生成正式报告
python batch_evaluate.py replays/ \
    --auto-discover \
    --parallel 4 \
    -o releases/v1.0/evaluation.xlsx
```

---

## 📞 技术支持

如有问题，请查看：
- `tests/agent_contract/evaluation/README.md` - 评估框架说明
- `skills/sheetpilot-run-review/skill.md` - Review skill文档
- `skills/sheetpilot-run-scorer/skill.md` - Scorer skill文档

---

**最后更新**: 2024-08-25  
**维护者**: SheetPilot Team
