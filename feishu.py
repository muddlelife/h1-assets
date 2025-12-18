import json
import os

import requests
from datetime import datetime


def send_feishu_alert(webhook_url, handle, asset_type, added, status):
    if not added:
        return False

    # 构建内容
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    asset_list = "\n".join(f"{item}" for item in added)

    card_content = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"content": "🚨 HackerOne 资产变更提醒", "tag": "plain_text"},
                "template": "blue",  # 使用蓝色表示“重要”
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": f"**项目**: {handle}\n**类型**: {asset_type}",
                        "tag": "lark_md",
                    },
                },
                {"tag": "hr"},  # 水平线
                {
                    "tag": "div",
                    "text": {
                        "content": f"✅ **{status}资产** ({len(added)}):\n{asset_list}",
                        "tag": "lark_md",
                    },
                },
                {
                    "tag": "div",
                    "text": {"content": f"⏰ **发送时间**: {now}", "tag": "lark_md"},
                },
            ],
        },
    }

    try:
        resp = requests.post(
            webhook_url,
            data=json.dumps(card_content),
            headers={"Content-Type": "application/json"},
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"❌ 发送飞书失败: {e}")
        return False
