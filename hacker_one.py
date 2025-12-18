import time
from datetime import datetime, timedelta
from pathlib import Path
import httpx
from typing import List, Dict, Any
from collections import defaultdict
import os
from feishu import send_feishu_alert
from dotenv import load_dotenv


load_dotenv()  # 仅本地生效，GitHub 上无影响

total_assets = []


class HackerOne:
    def __init__(self, username: str, token: str):
        self.username = username
        self.token = token
        self.headers = {"Accept": "application/json"}

    def create_client(self) -> httpx.Client:
        return httpx.Client(auth=(self.username, self.token), timeout=20)

    def _fetch_paginated_data(self, url: str) -> List[Dict[str, Any]]:
        client = self.create_client()
        all_data: List[Dict[str, Any]] = []

        while url:
            response = client.get(url, headers=self.headers)
            if response.status_code != 200:
                # 可选：记录错误或抛异常
                print(f"⚠️ 请求失败 {response.status_code}: {url}")
                break

            data = response.json()
            all_data.extend(data.get("data", []))

            # 获取下一页 URL
            url = data.get("links", {}).get("next")

            if url:  # 如果还有下一页，休息 1 秒
                time.sleep(1)

        client.close()  # 显式关闭 client（或用 with）
        return all_data

    def get_programs(self) -> List[Dict[str, Any]]:
        """获取所有项目列表"""
        programs_url = "https://api.hackerone.com/v1/hackers/programs?page[size]=100"
        return self._fetch_paginated_data(programs_url)

    def get_program_asset(self, handle: str) -> List[Dict[str, Any]]:
        """获取指定项目的资产清单"""
        asset_url = f"https://api.hackerone.com/v1/hackers/programs/{handle}/structured_scopes?page[size]=100"
        return self._fetch_paginated_data(asset_url)


if __name__ == "__main__":

    # 获取当前年月日时分秒
    now = datetime.now()
    formatted = now.strftime("%Y-%m-%d")

    # 昨天
    yesterday = now - timedelta(days=1)
    yesterday = yesterday.strftime("%Y-%m-%d")

    HACKERONE_API_TOKEN = os.getenv("HACKERONE_API_TOKEN")
    HACKERONE_USERNAME = os.getenv("HACKERONE_USERNAME")
    WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK")
    hackerone = HackerOne(HACKERONE_USERNAME, HACKERONE_API_TOKEN)

    # 项目获取，获取完所有的目标了
    programs = hackerone.get_programs()

    open_handles = []

    for program in programs:
        attributes = program.get("attributes")
        submission_state = attributes.get("submission_state")
        handle = attributes.get("handle")

        if attributes.get("submission_state") == "open":  # 项目暂停
            open_handles.append(handle)
            folder = Path("./assets/{}".format(handle))
            folder.mkdir(parents=True, exist_ok=True)

    # 开启的项目进行资产保存
    for handle in open_handles:
        open_program_asset = hackerone.get_program_asset(handle)

        # 赏金资产
        bonuses_assets = []

        # 处理
        for asset in open_program_asset:
            attributes = asset.get("attributes")  # 详细信息
            asset_type = attributes.get("asset_type")  # 资产类型
            asset_identifier = attributes.get("asset_identifier")  # 资产信息
            eligible_for_bounty = attributes.get(
                "eligible_for_bounty"
            )  # 是否有资格获取赏金
            eligible_for_submission = attributes.get(
                "eligible_for_submission"
            )  # 是否可提交漏洞

            if eligible_for_bounty == True and eligible_for_submission == True:
                # 说明可获得赏金
                bonuses_assets.append(
                    {
                        "handle": handle,  # 项目
                        "asset_type": asset_type,  # 资产类型
                        "asset_identifier": asset_identifier,  # 资产信息
                    }
                )
                total_assets.append(
                    {
                        "handle": handle,  # 项目
                        "asset_type": asset_type,  # 资产类型
                        "asset_identifier": asset_identifier,  # 资产信息
                    }
                )

        # 保存赏金资产，根据key的不同保存资产
        grouped = defaultdict(list)
        for item in bonuses_assets:
            asset_type = item["asset_type"]
            grouped[asset_type].append(item)

        # 步骤 2：为每组保存为独立的 JSON 文件
        for asset_type, items in grouped.items():

            today_assets = []

            for item in items:
                today_assets.append(item.get("asset_identifier"))

            # 新增资产
            yesterday_file_path = Path(f"./assets/{handle}/{asset_type.lower()}.txt")
            if yesterday_file_path.exists():  # 和过去的相比较
                with open(yesterday_file_path, "r", encoding="utf-8") as f:
                    yesterday_assets = [i.split("\n")[0] for i in f.readlines()]

                set_today = set(today_assets)
                set_yesterday = set(yesterday_assets)

                added = set_today - set_yesterday
                removed = set_yesterday - set_today

                if added:
                    send_feishu_alert(WEBHOOK_URL, handle, asset_type, added, "新增")

                if removed:
                    send_feishu_alert(WEBHOOK_URL, handle, asset_type, removed, "减少")
            # 如果路径不存在呢，说明是新的资产
            else:
                send_feishu_alert(WEBHOOK_URL, handle, asset_type, today_assets, "新增")

            filename = f"./assets/{handle}/{asset_type.lower()}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                for item in today_assets:
                    f.write(item + "\n")

    # 最后对总的资产进行分类保存
    total_grouped = defaultdict(list)

    for item in total_assets:
        asset_type = item["asset_type"]
        total_grouped[asset_type].append(item)

    for asset_type, items in total_grouped.items():

        today_total_file_path = f"./total_assets/{asset_type.lower()}.txt"

        with open(today_total_file_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(item.get("asset_identifier") + "\n")
