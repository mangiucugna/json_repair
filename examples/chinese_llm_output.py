"""Repair Chinese-language LLM output and preserve the original characters."""

from __future__ import annotations

import json
import sys

from json_repair import loads

LLM_OUTPUT = """
以下是整理后的结构化结果:

```json
{
  标题: "退款申请处理结果",
  "摘要": "客户确认已经收到退款",
  "标签": ["账单", "已解决",],
  "是否升级": false,
}
```

如果你需要, 我也可以补充英文摘要。
"""


def main() -> None:
    repaired = loads(LLM_OUTPUT)
    sys.stdout.write(json.dumps(repaired, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
