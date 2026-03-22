"""
텔레그램 알림 모듈
NomuBlog와 동일한 봇 토큰을 재사용해 신규 공고 결과를 전송
"""

import os
import urllib.request
import urllib.parse
import json
from typing import List, Dict


def _get_credentials() -> tuple[str, str]:
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    return token, chat_id


def _send(token: str, chat_id: str, text: str) -> bool:
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = json.dumps({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())
            return data.get('ok', False)
    except Exception as e:
        print(f'[Telegram] 전송 실패: {e}')
        return False


def send_search_summary(
    stats: Dict,
    pending_count: int,
    archive_count: int,
    pending_items: List[Dict],
) -> bool:
    """
    검색 완료 후 결과 요약을 텔레그램으로 전송

    Args:
        stats: 전처리 통계 (total, passed 등)
        pending_count: Pending 시트 저장 건수
        archive_count: Archive 직접 저장 건수
        pending_items: 적합 판정 공고 목록 (title, organization, deadline, url)
    """
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        print('[Telegram] TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 없음. 스킵.')
        return False

    total = stats.get('total', 0)
    passed = stats.get('passed', 0)
    new_total = pending_count + archive_count

    if new_total == 0:
        msg = (
            '📋 <b>[노무고문 공고 모니터링]</b>\n\n'
            f'수집 {total}건 검색 완료\n'
            '신규 적합 공고 없음'
        )
        return _send(token, chat_id, msg)

    # 헤더
    lines = [
        '📋 <b>[노무고문 공고] 신규 공고 발견!</b>\n',
        f'수집 {total}건 → 1차 필터 {passed}건 → <b>적합 {new_total}건</b>\n',
    ]

    # 공고 목록 (최대 5개)
    for i, item in enumerate(pending_items[:5], 1):
        title = item.get('title', '제목 없음')
        org = item.get('organization', '')
        deadline = item.get('deadline') or '마감일 미상'
        url = item.get('url', '')

        lines.append(f'{i}. <b>{title}</b>')
        if org:
            lines.append(f'   🏢 {org}')
        lines.append(f'   📅 마감: {deadline}')
        if url:
            lines.append(f'   <a href="{url}">공고 보기</a>')
        lines.append('')

    if new_total > 5:
        lines.append(f'...외 {new_total - 5}건 더 있음')

    lines.append('Google Sheets Pending 시트에서 검토하세요.')

    return _send(token, chat_id, '\n'.join(lines))


def send_error_alert(error_msg: str) -> bool:
    """파이프라인 치명적 오류 시 텔레그램 경고 전송"""
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        return False

    msg = f'⚠️ <b>[노무고문 모니터링 오류]</b>\n\n{error_msg[:500]}'
    return _send(token, chat_id, msg)
