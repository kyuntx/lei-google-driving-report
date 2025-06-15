from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
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
app.secret_key = 'your_secret_key'  # セッション管理用の秘密鍵

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
    calendar_id = request.form.get('calendar_id')
    maps_api_key = request.form.get('maps_api_key')
    
    if not maps_api_key:
        return render_template('index.html', 
                              authenticated=True, 
                              error="Google Maps APIキーが必要です")
    
    # 日付範囲の設定
    if start_date and end_date:
        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        end_date = end_date.replace(hour=23, minute=59, second=59)
    else:
        # デフォルトは当月
        start_date, end_date = get_first_and_last_day_of_month()
        end_date = end_date.replace(hour=23, minute=59, second=59)
    
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
    """Get the first and last day of the current month."""
    today = datetime.datetime.now()
    first_day = datetime.datetime(today.year, today.month, 1)
    if today.month == 12:
        last_day = datetime.datetime(today.year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.datetime(today.year, today.month + 1, 1) - datetime.timedelta(days=1)
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
    
    # カレンダーIDを指定してイベントを取得
    events_result = calendar_service.events().list(
        calendarId=calendar_id,
        timeMin=start_date.isoformat() + 'Z',  # 'Z' indicates UTC time
        timeMax=end_date.isoformat() + 'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    
    previous_event = None
    
    for event in events:
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
            
        # Update previous event
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
    # デバッグモードで実行（本番環境ではFalseにする）
    app.run(debug=True)