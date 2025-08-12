import apprise

ap = apprise.Apprise()
ap.add("windows://?duration=5")  # Windows Toast
# 邮件（示例，替换你的 SMTP）
# ap.add("mailto://smtp_user:smtp_pass@smtp.example.com:587?to=you@example.com")

def notify(title, body, level="INFO"):
    ap.notify(title=f"[{level}] {title}", body=body)

# 用法
notify("行情延迟告警", "无新 tick 已超过 60s。", "CRIT")

# import asyncio, apprise
# ap = apprise.Apprise()
# ap.add("windows://")

# def main():
#     ap.async_notify(title="[WARN] 延迟", body="无新 tick 超过 15s。")

# asyncio.run(main())