#!/usr/bin/env python3
"""Phase 1 verification script: Test Garmin account data accessibility"""
import sys
from garmin.client import GarminClient
from garmin.sync import (
    fetch_yesterday_sleep,
    fetch_yesterday_activities,
    parse_sleep,
    parse_activity,
)


def main():
    print("正在连接 Garmin Connect...")
    client = GarminClient()
    try:
        client.connect()
    except Exception as e:
        print(f"登录失败：{e}")
        sys.exit(1)
    print("登录成功 ✓\n")

    # 睡眠数据
    print("=" * 50)
    print("【昨日睡眠数据】")
    print("=" * 50)
    try:
        raw_sleep = fetch_yesterday_sleep(client.garmin)
        sleep = parse_sleep(raw_sleep)
        for key, val in sleep.items():
            print(f"  {key}: {val}")
    except Exception as e:
        print(f"睡眠数据获取失败：{e}")

    print()

    # 活动数据
    print("=" * 50)
    print("【昨日活动数据】")
    print("=" * 50)
    try:
        raw_activities = fetch_yesterday_activities(client.garmin)
        if not raw_activities:
            print("  昨日无活动记录")
        else:
            for raw in raw_activities:
                act = parse_activity(raw)
                print(f"\n  活动类型: {act['activity_type']}")
                for key, val in act.items():
                    if key != "activity_type":
                        print(f"    {key}: {val}")
    except Exception as e:
        print(f"活动数据获取失败：{e}")


if __name__ == "__main__":
    main()
