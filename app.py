from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os

# .envファイルから環境変数を読み込み
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenvがインストールされていない場合はスキップ
    pass

# セキュリティ設定：開発環境でのHTTP使用を環境変数で制御
# 本番環境では '0' または未設定にしてHTTPSを強制すること
if os.environ.get('OAUTHLIB_INSECURE_TRANSPORT', '0') == '1':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' 
import datetime
import csv
import re
import json
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from dateutil.relativedelta import relativedelta

# Google API libraries
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import googlemaps

app = Flask(__name__)
# セキュリティ強化：環境変数から秘密鍵を取得
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_change_this_in_production')

# DoS攻撃対策：イベント取得数の制限
MAX_EVENTS = 1000
MAX_DAYS_RANGE = 365  # 最大1年間の範囲制限

# OAuth設定
CLIENT_SECRETS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
API_SERVICE_NAME = 'calendar'
API_VERSION = 'v3'

@app.route('/')
def index():
    """メインページを表示"""
    # 認証状態を確認
    if 'credentials' in session:
        return render_template('index.html', authenticated=True)
    else:
        return render_template('index.html', authenticated=False)

@app.route('/authorize')
def authorize():
    """Google認証を開始"""
    # 認証フローを作成
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, 
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    
    # 認証URLを取得
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    # 状態をセッションに保存
    session['state'] = state
    
    # 認証URLにリダイレクト
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    """Google認証コールバック"""
    state = session['state']
    
    # 認証フローを作成
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, 
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    
    # 認証コードを取得してトークンと交換
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    
    # 認証情報をセッションに保存
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """ログアウト"""
    if 'credentials' in session:
        del session['credentials']
    return redirect(url_for('index'))

@app.route('/generate_report', methods=['POST'])
def generate_report():
    """レポート生成とブラウザ表示"""
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    
    # フォームからパラメータを取得
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    calendar_id = request.form.get('calendar_id', '').strip()
    maps_api_key = request.form.get('maps_api_key', '').strip()
    
    # 入力値検証
    if not maps_api_key:
        return render_template('index.html', 
                              authenticated=True, 
                              error="Google Maps APIキーが必要です")
    
    # セキュリティ：APIキーの長さをチェック
    if len(maps_api_key) < 10 or len(maps_api_key) > 100:
        return render_template('index.html', 
                              authenticated=True, 
                              error="Google Maps APIキーの形式が正しくありません")
    
    # 日付範囲の設定（UTCタイムゾーンを追加）
    if start_date and end_date:
        try:
            start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59)
            
            # DoS攻撃対策：日付範囲をチェック
            date_range = (end_date - start_date).days
            if date_range < 0:
                return render_template('index.html', 
                                      authenticated=True, 
                                      error="開始日は終了日より前の日付にしてください")
            if date_range > MAX_DAYS_RANGE:
                return render_template('index.html', 
                                      authenticated=True, 
                                      error=f"日付範囲は{MAX_DAYS_RANGE}日以内にしてください")
            
            # UTCタイムゾーンを追加
            start_date = start_date.replace(tzinfo=datetime.timezone.utc)
            end_date = end_date.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            return render_template('index.html', 
                                  authenticated=True, 
                                  error="日付の形式が正しくありません")
    else:
        # デフォルトは当月
        start_date, end_date = get_first_and_last_day_of_month()
        end_date = end_date.replace(hour=23, minute=59, second=59)
        # UTCタイムゾーンを追加
        start_date = start_date.replace(tzinfo=datetime.timezone.utc)
        end_date = end_date.replace(tzinfo=datetime.timezone.utc)
    
    # Google サービスの認証
    credentials = Credentials(**session['credentials'])
    calendar_service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
    gmaps_client = googlemaps.Client(key=maps_api_key)
    
    # 運転ログの取得
    driving_logs = get_driving_logs(start_date, end_date, calendar_service, gmaps_client, calendar_id or 'primary')
    
    # 日付の表示形式を整える
    for log in driving_logs:
        if log['start_time']:
            start_dt = datetime.datetime.fromisoformat(log['start_time'].replace('Z', '+00:00'))
            log['start_time_formatted'] = start_dt.strftime('%Y-%m-%d %H:%M')
        else:
            log['start_time_formatted'] = "不明"
            
        if log['end_time']:
            end_dt = datetime.datetime.fromisoformat(log['end_time'].replace('Z', '+00:00'))
            log['end_time_formatted'] = end_dt.strftime('%Y-%m-%d %H:%M')
        else:
            log['end_time_formatted'] = "不明"
    
    # 一時ファイルにCSVを出力（ダウンロード用）
    fd, path = tempfile.mkstemp(suffix='.csv')
    os.close(fd)  # fdを閉じる
    export_to_csv(driving_logs, path)  # パスを直接渡す
    
    # 一時ファイルのパスをセッションに保存
    session['temp_csv_path'] = path
    session['report_filename'] = f'driving_report_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.csv'
    
    return render_template('report.html', 
                          logs=driving_logs, 
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'),
                          calendar_id=calendar_id or 'primary')

@app.route('/download_csv')
def download_csv():
    """CSVファイルのダウンロード（Shift_JIS形式）"""
    if 'temp_csv_path' not in session or 'report_filename' not in session:
        return redirect(url_for('index'))
    
    path = session['temp_csv_path']
    filename = session['report_filename']
    
    # Excelで開きやすくするためのヘッダー設定
    response = send_file(
        path,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv;charset=shift_jis'
    )
    
    # Content-Typeヘッダーを追加
    response.headers['Content-Type'] = 'text/csv;charset=shift_jis'
    
    return response

def get_first_and_last_day_of_month():
    """Get the first and last day of the current month with UTC timezone."""
    today = datetime.datetime.now(datetime.timezone.utc)
    first_day = datetime.datetime(today.year, today.month, 1, tzinfo=datetime.timezone.utc)
    if today.month == 12:
        last_day = datetime.datetime(today.year + 1, 1, 1, tzinfo=datetime.timezone.utc) - datetime.timedelta(days=1)
    else:
        last_day = datetime.datetime(today.year, today.month + 1, 1, tzinfo=datetime.timezone.utc) - datetime.timedelta(days=1)
    return first_day, last_day

def parse_event_title(title: str) -> Tuple[Optional[float], Optional[float]]:
    """Parse distance and fuel efficiency from event title."""
    # 修正した正規表現パターン - 整数部分が0の場合も対応し、km/lを含む
    match = re.search(r'距離(\d*\.\d+|\d+)km\s*\((\d*\.\d+|\d+)km/l\)', title)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None

def get_address_from_location(gmaps_client: Any, location: str) -> str:
    """Convert coordinates to address using Google Maps reverse geocoding."""
    if not location:
        return "不明"  # Unknown
    
    try:
        # Extract coordinates from location string
        coord_match = re.search(r'(-?\d+\.\d+),\s*(-?\d+\.\d+)', location)
        if not coord_match:
            return "不明"  # Unknown
        
        lat, lng = float(coord_match.group(1)), float(coord_match.group(2))
        
        # Reverse geocode coordinates to address with language parameter
        reverse_geocode_result = gmaps_client.reverse_geocode(
            (lat, lng),
            language="ja"
        )
        
        if reverse_geocode_result:
            # フォーマット済み住所を取得
            formatted_address = reverse_geocode_result[0]['formatted_address']
            
            # 「日本、〒XXX-XXXX 」の部分を削除
            formatted_address = re.sub(r'^日本、\s*', '', formatted_address)
            formatted_address = re.sub(r'〒\d{3}-\d{4}\s*', '', formatted_address)
            
            return formatted_address
            
        return "不明"  # Unknown
    except Exception as e:
        print(f"Error in reverse geocoding: {e}")
        return "不明"  # Unknown

def get_driving_logs(start_date: datetime.datetime, end_date: datetime.datetime, 
                     calendar_service: Any, gmaps_client: Any, calendar_id: str = 'primary') -> List[Dict[str, Any]]:
    """Retrieve driving logs from Google Calendar."""
    logs = []
    
    # 指定期間より前の最後のイベントを取得するため、より広い範囲でイベントを取得
    # 7日前から取得して、期間外の直前のイベントを見つける
    extended_start_date = start_date - datetime.timedelta(days=7)
    
    # 日付を正しいUTCフォーマットに変換（タイムゾーン情報を除いてZを追加）
    extended_start_str = extended_start_date.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
    end_date_str = end_date.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
    
    try:
        # カレンダーIDを指定してイベントを取得（拡張期間）
        # DoS攻撃対策：取得イベント数を制限
        events_result = calendar_service.events().list(
            calendarId=calendar_id,
            timeMin=extended_start_str,
            timeMax=end_date_str,
            singleEvents=True,
            orderBy='startTime',
            maxResults=MAX_EVENTS
        ).execute()
    except Exception as e:
        print(f"Error fetching calendar events: {e}")
        return []
    
    events = events_result.get('items', [])
    
    # 指定期間外の直前のイベントを見つける
    previous_event = None
    for event in events:
        event_start = event['start'].get('dateTime')
        if event_start and '距離' in event.get('summary', ''):
            event_start_dt = datetime.datetime.fromisoformat(event_start.replace('Z', '+00:00'))
            if event_start_dt < start_date:
                previous_event = event  # 期間前の最後の運転イベント
            else:
                break  # 指定期間に入ったので終了
    
    # 指定期間内のイベントのみを処理
    for event in events:
        event_start = event['start'].get('dateTime')
        if not event_start:
            continue
            
        event_start_dt = datetime.datetime.fromisoformat(event_start.replace('Z', '+00:00'))
        
        # 指定期間内のイベントのみを処理
        if event_start_dt < start_date or event_start_dt > end_date:
            continue
            
        # Check if event title matches the driving log pattern
        if '距離' in event.get('summary', ''):
            distance, fuel_efficiency = parse_event_title(event.get('summary', ''))
            
            if distance is not None:
                start_time = event['start'].get('dateTime')
                end_time = event['end'].get('dateTime')
                destination = get_address_from_location(gmaps_client, event.get('location', ''))
                
                # 所要時間を計算（分単位）
                duration_minutes = 0
                if start_time and end_time:
                    start_dt = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    end_dt = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    duration = end_dt - start_dt
                    duration_minutes = int(duration.total_seconds() / 60)
                
                # 元の位置情報を保存（Google Mapsリンク用）
                raw_location = event.get('location', '')
                
                # If we have a previous event, use its location as the origin
                origin = "不明"  # Default to unknown
                origin_location = ""  # 元の位置情報（Google Mapsリンク用）
                if previous_event:
                    origin = get_address_from_location(gmaps_client, previous_event.get('location', ''))
                    origin_location = previous_event.get('location', '')
                
                logs.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'origin': origin,
                    'destination': destination,
                    'distance': distance,
                    'fuel_efficiency': fuel_efficiency,
                    'duration_minutes': duration_minutes,  # 所要時間（分）を追加
                    'origin_location': origin_location,    # 元の位置情報を追加
                    'destination_location': raw_location   # 元の位置情報を追加
                })
                
                # Update previous event for next iteration
                previous_event = event
    
    return logs

def export_to_csv(logs: List[Dict[str, Any]], file) -> None:
    """Export driving logs to CSV with Shift_JIS encoding."""
    # CSVに所要時間カラムを追加
    fieldnames = ['出発時刻', '到着時刻','所要時間(分)', '出発地', '到着地', '移動距離', '燃費']
    
    # UTF-8で一時文字列バッファに書き込み
    import io
    temp_buffer = io.StringIO()
    writer = csv.DictWriter(temp_buffer, fieldnames=fieldnames)
    writer.writeheader()
    
    for log in logs:
        writer.writerow({
            '出発時刻': log['start_time'],
            '到着時刻': log['end_time'],
            '所要時間(分)': log['duration_minutes'],
            '出発地': log['origin'],
            '到着地': log['destination'],
            '移動距離': log['distance'],
            '燃費': log['fuel_efficiency']
        })
    
    # UTF-8からShift_JISに変換
    utf8_content = temp_buffer.getvalue()
    shift_jis_content = utf8_content.encode('shift_jisx0213', errors='replace')
    
    # バイナリモードで書き込み
    if hasattr(file, 'write'):
        # すでに開いているファイルオブジェクトの場合
        if hasattr(file, 'mode') and 'b' in file.mode:
            # バイナリモードで開かれている場合
            file.write(shift_jis_content)
        else:
            # テキストモードで開かれている場合
            file.write(shift_jis_content.decode('shift_jisx0213'))
    else:
        # ファイルパスの場合
        with open(file, 'wb') as f:
            f.write(shift_jis_content)

if __name__ == '__main__':
    # セキュリティ：本番環境では環境変数でデバッグモードを制御
    debug_mode = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # セキュリティ警告
    if debug_mode and app.secret_key == 'your_secret_key_change_this_in_production':
        print("⚠️  警告: デフォルトのシークレットキーを使用しています。本番環境では必ず変更してください。")
    
    if debug_mode:
        print("🔧 開発モードで実行中 - 本番環境では DEBUG=False を設定してください")
    
    app.run(debug=debug_mode, host='127.0.0.1', port=5000)