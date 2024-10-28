import requests
import os
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta

# .envファイルから環境変数を読み込む
load_dotenv()

# .envファイルからトークンとDiscord Webhook、Device IDsを取得
TOKEN = os.getenv("TOKEN")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
NOTIFICATION_INTERVAL_HOURS = int(os.getenv("NOTIFICATION_INTERVAL_HOURS", 1))  # デフォルトは1時間

# .envファイルからデバイスIDを取得（カンマ区切りをリストに変換）
device_ids = os.getenv("DEVICE_IDS").split(",")

# APIエンドポイントのベースURL
base_url = "https://api.io.solutions/v1/io-explorer/devices/{device_id}/details"

# 最後に通知を送信した時刻を記録する辞書
last_notification_times = {}
token_error_notified = False  # トークンエラー通知のフラグ

# Discordに通知する関数
def send_discord_notification(message):
    data = {"content": message}
    response = requests.post(DISCORD_WEBHOOK_URL, json=data)
    if response.status_code == 204:
        print("Notification sent successfully.")
    else:
        print(f"Failed to send notification. Status Code: {response.status_code}")

# メイン処理
def check_devices():
    global token_error_notified
    for device_id in device_ids:
        # URLを生成
        url = base_url.format(device_id=device_id.strip())  # 余分なスペースを削除
        
        # リクエストヘッダー
        headers = {
            "accept": "application/json",
            "Token": TOKEN,
        }
        
        # APIリクエスト
        response = requests.get(url, headers=headers)
        
        # トークンのエラーチェック
        if response.status_code == 401:  # 401 Unauthorized
            if not token_error_notified:
                send_discord_notification("⚠️ API Token has expired or is invalid. Please update the TOKEN in .env file.")
                token_error_notified = True  # トークンエラー通知済み
            return  # 他のデバイスチェックをスキップ

        # トークンが有効であればエラーフラグをリセット
        token_error_notified = False

        if response.status_code == 200:
            # レスポンスのJSONを取得
            response_data = response.json()
            device_status = response_data["data"]["status"]
            readiness = response_data["data"]["readiness_info"]["readiness"]
            last_challenge_successful = response_data["data"]["last_challenge_successful"]

            # 通知のメッセージ内容
            message = (f"Device ID: {device_id.strip()}\n"
                       f"  Device Status: {device_status}\n"
                       f"  Readiness: {readiness}\n"
                       f"  Last Challenge Successful: {last_challenge_successful}\n")

            # 条件に基づきDiscord通知を送信
            if (device_status != "up" or readiness != "Cluster Ready" or not last_challenge_successful):
                current_time = datetime.now()
                last_notified = last_notification_times.get(device_id)

                # 最初の通知か、前回の通知から1時間経過しているかを確認
                if last_notified is None or (current_time - last_notified >= timedelta(hours=1)):
                    send_discord_notification(message)
                    # 通知時刻を更新
                    last_notification_times[device_id] = current_time
        else:
            print(f"Failed to retrieve data for device ID: {device_id.strip()}. Status Code: {response.status_code}")

# 定期的に動作させる仕組み
def main():
    last_full_notification = None
    while True:
        current_time = datetime.now()

        # NOTIFICATION_INTERVAL_HOURSが0でない場合に、指定の時間間隔ごとに全ての内容を通知
        if NOTIFICATION_INTERVAL_HOURS != 0:
            if last_full_notification is None or (current_time - last_full_notification).total_seconds() >= NOTIFICATION_INTERVAL_HOURS * 3600:
                for device_id in device_ids:
                    # 各デバイスの最新のステータス情報を取得してメッセージを構成
                    url = base_url.format(device_id=device_id.strip())
                    headers = {
                        "accept": "application/json",
                        "Token": TOKEN,
                    }
                    response = requests.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        device_status = response_data["data"]["status"]
                        readiness = response_data["data"]["readiness_info"]["readiness"]
                        last_challenge_successful = response_data["data"]["last_challenge_successful"]

                        message = (f"Device ID: {device_id.strip()}\n"
                                   f"  Device Status: {device_status}\n"
                                   f"  Readiness: {readiness}\n"
                                   f"  Last Challenge Successful: {last_challenge_successful}\n")
                        send_discord_notification(message)
                last_full_notification = current_time
        
        # 各デバイスの状態を1分ごとにチェック
        check_devices()

        # 1分待機
        time.sleep(60)

if __name__ == "__main__":
    main()
