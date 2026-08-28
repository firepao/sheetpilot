# B5：营销漏斗与 ROI

## 输入文件

- 文件路径：`tests/agent_contract/data/B5_marketing_funnel.xlsx`
- 工作表：`投放明细`、`渠道目标`
- 表头行：1

## 用户需求（Prompt）

```text
请排除状态为“暂停”的广告组，按渠道汇总投放金额、曝光量、点击量、转化量和归因销售额，计算 CTR、转化率和 ROI，并关联渠道目标标记低于目标 ROI 的渠道。请按 ROI 升序输出优化清单，并设置金额和比例的合适格式。

输入文件：tests/agent_contract/data/B5_marketing_funnel.xlsx
输出文件：<自动生成>
```

## 验收重点

- 暂停广告组不能进入汇总。
- CTR=点击量/曝光量，转化率=转化量/点击量，ROI=归因销售额/投放金额。
- 目标 ROI 来自渠道目标表，不在 Prompt 中硬编码。
