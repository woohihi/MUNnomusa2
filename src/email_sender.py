"""
이메일 발송 모듈
신규 공고 발견 시 자동 알림
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
from datetime import datetime, date

from .config import get_config


class EmailSender:
    """SMTP 이메일 발송 클래스"""

    def __init__(self):
        config = get_config()
        self.email_config = config.get('email', {})

        if not self.email_config:
            print("⚠️  이메일 설정 없음. 발송 스킵")
            self.enabled = False
            return

        self.smtp_server = self.email_config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = int(self.email_config.get('smtp_port', 587))
        self.sender_email = self.email_config.get('sender_email', '')
        self.sender_password = self.email_config.get('sender_password', '')
        self.recipient_email = self.email_config.get('recipient_email', '')

        self.enabled = bool(self.sender_email and self.sender_password and self.recipient_email)

        if self.enabled:
            print(f"✅ 이메일 설정 로드 완료: {self.sender_email} → {self.recipient_email}")
        else:
            print("⚠️  이메일 설정 불완전. 발송 비활성화")

    # ===========================
    # 공개 메서드
    # ===========================

    def send_search_summary(
        self,
        stats: Dict,
        filtered_items: List[Dict],
        rejected_items: List[Dict],
        results: List[Dict],
        archives: List[Dict],
        pending_items: List[Dict] = None,
    ) -> bool:
        """
        검색 결과 요약 이메일 발송.

        Args:
            stats: 전처리 통계 dict
            filtered_items: 전처리에서 필터링된 항목
            rejected_items: AI가 거부한 항목
            results: Results 시트 데이터
            archives: Archive 시트 데이터
            pending_items: Pending에 저장된 신규 적합 공고 (result_processor 출력)
        """
        if not self.enabled:
            print("📧 이메일 발송 비활성화 상태")
            return False

        try:
            today = datetime.now().strftime('%Y-%m-%d')
            subject = f"📋 노무고문 공고 검색 결과 보고 ({today})"
            html_body = self._build_html(
                stats, filtered_items, rejected_items,
                results, archives, pending_items or []
            )

            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.sender_email
            message['To'] = self.recipient_email
            message.attach(MIMEText(html_body, 'html', 'utf-8'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)

            print("✅ 검색 결과 요약 발송 성공")
            return True

        except Exception as e:
            print(f"❌ 이메일 발송 실패: {e}")
            return False

    # ===========================
    # HTML 빌더
    # ===========================

    def _build_html(
        self,
        stats: Dict,
        filtered_items: List[Dict],
        rejected_items: List[Dict],
        results: List[Dict],
        archives: List[Dict],
        pending_items: List[Dict],
    ) -> str:
        today_str = datetime.now().strftime('%Y년 %m월 %d일')
        now_str = datetime.now().strftime('%H:%M')

        total = stats.get('total', 0)
        duplicates = stats.get('duplicates', 0)
        keyword_failed = stats.get('keyword_failed', 0)
        negative_filtered = stats.get('negative_filtered', 0)
        passed = stats.get('passed', 0)
        ai_rejected = len(rejected_items)
        final_count = len(pending_items)

        # 신규 공고 카드 HTML
        cards_html = self._build_pending_cards(pending_items)

        # 필터링 상세 HTML
        filter_html = self._build_filter_detail(filtered_items, rejected_items)

        # 결과 상태 메시지
        if final_count == 0:
            status_color = '#6c757d'
            status_msg = '오늘 검색에서 적합한 신규 공고가 발견되지 않았습니다.'
        elif final_count <= 3:
            status_color = '#f39c12'
            status_msg = f'{final_count}건의 신규 공고가 발견되었습니다. Pending 시트에서 검토해 주세요.'
        else:
            status_color = '#27ae60'
            status_msg = f'{final_count}건의 신규 공고가 발견되었습니다. Pending 시트에서 검토해 주세요.'

        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
          background: #f4f6f9; color: #333; line-height: 1.6; }}
  .wrap {{ max-width: 680px; margin: 0 auto; padding: 24px 16px; }}

  /* 헤더 */
  .header {{ background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
             color: white; padding: 28px 32px; border-radius: 12px 12px 0 0; }}
  .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
  .header p  {{ font-size: 13px; opacity: 0.85; }}

  /* 본문 */
  .body {{ background: white; padding: 28px 32px;
           border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0; }}

  /* 통계 퍼널 */
  .funnel {{ background: #f8f9fa; border-radius: 10px; padding: 20px 24px; margin-bottom: 24px; }}
  .funnel-row {{ display: flex; justify-content: space-between;
                 padding: 5px 0; font-size: 14px; }}
  .funnel-row.total {{ font-weight: 700; font-size: 15px;
                       border-bottom: 1px solid #dee2e6; padding-bottom: 10px; margin-bottom: 6px; }}
  .funnel-row.result {{ border-top: 1px solid #dee2e6; padding-top: 10px;
                        margin-top: 6px; font-weight: 700; font-size: 16px; }}
  .muted {{ color: #868e96; }}
  .green {{ color: #28a745; }}
  .red   {{ color: #dc3545; }}

  /* 상태 배너 */
  .status-banner {{ border-left: 4px solid {status_color}; background: #f8f9fa;
                    padding: 12px 16px; border-radius: 0 8px 8px 0;
                    font-size: 14px; margin-bottom: 28px; color: #333; }}

  /* 섹션 제목 */
  .section-title {{ font-size: 15px; font-weight: 700; color: #1a73e8;
                    border-bottom: 2px solid #1a73e8; padding-bottom: 6px;
                    margin-bottom: 16px; }}

  /* 공고 카드 */
  .card {{ border: 1px solid #e0e0e0; border-radius: 10px; padding: 16px 18px;
           margin-bottom: 14px; background: white;
           border-left: 5px solid #dee2e6; }}
  .card.urgent  {{ border-left-color: #dc3545; }}
  .card.warning {{ border-left-color: #fd7e14; }}
  .card.normal  {{ border-left-color: #28a745; }}
  .card.expired {{ border-left-color: #868e96; }}

  .card-badges {{ margin-bottom: 8px; }}
  .badge {{ display: inline-block; font-size: 11px; font-weight: 600;
            padding: 2px 9px; border-radius: 20px; margin-right: 5px; }}
  .badge-dday-urgent  {{ background: #fde8e8; color: #dc3545; }}
  .badge-dday-warning {{ background: #fff3cd; color: #856404; }}
  .badge-dday-normal  {{ background: #d1e7dd; color: #155724; }}
  .badge-dday-expired {{ background: #e9ecef; color: #6c757d; }}
  .badge-source-a {{ background: #e8f0fe; color: #1a73e8; }}
  .badge-source-b {{ background: #e8f5e9; color: #2e7d32; }}
  .badge-source-c {{ background: #fce4ec; color: #b71c1c; }}
  .badge-archive  {{ background: #e9ecef; color: #495057; }}

  .card-title {{ font-size: 15px; font-weight: 700; color: #212529;
                 margin-bottom: 3px; line-height: 1.4; }}
  .card-org   {{ font-size: 13px; color: #495057; margin-bottom: 2px; }}
  .card-deadline {{ font-size: 12px; color: #868e96; margin-bottom: 8px; }}
  .card-summary {{ font-size: 13px; color: #555; line-height: 1.55;
                   margin-bottom: 12px; }}
  .btn {{ display: inline-block; background: #1a73e8; color: white !important;
          text-decoration: none; font-size: 13px; font-weight: 600;
          padding: 7px 18px; border-radius: 6px; }}

  /* 현황 박스 */
  .status-grid {{ display: flex; gap: 12px; margin-bottom: 24px; }}
  .status-box  {{ flex: 1; background: #f8f9fa; border-radius: 8px;
                  padding: 14px; text-align: center; }}
  .status-num  {{ font-size: 26px; font-weight: 700; color: #1a73e8; }}
  .status-lbl  {{ font-size: 12px; color: #868e96; margin-top: 2px; }}

  /* 상세 필터 토글 */
  .detail-section {{ margin-top: 24px; }}
  .detail-title {{ font-size: 14px; font-weight: 600; color: #666;
                   margin-bottom: 10px; }}
  .detail-row {{ font-size: 13px; padding: 4px 0; color: #555;
                 border-bottom: 1px solid #f0f0f0; }}

  /* 푸터 */
  .footer {{ background: #f8f9fa; padding: 18px 32px; border-radius: 0 0 12px 12px;
             border: 1px solid #e0e0e0; border-top: none;
             text-align: center; font-size: 12px; color: #aaa; }}
</style>
</head>
<body>
<div class="wrap">

  <!-- 헤더 -->
  <div class="header">
    <h1>📋 노무고문 공고 모니터링</h1>
    <p>{today_str} {now_str} 기준 &nbsp;|&nbsp; 자동 검색 결과 보고</p>
  </div>

  <div class="body">

    <!-- 통계 퍼널 -->
    <div class="funnel">
      <div class="funnel-row total">
        <span>총 수집</span><span>{total}건</span>
      </div>
      <div class="funnel-row">
        <span class="muted">├ 중복 제외</span>
        <span class="muted">−{duplicates}건</span>
      </div>
      <div class="funnel-row">
        <span class="muted">├ 키워드 미충족</span>
        <span class="muted">−{keyword_failed}건</span>
      </div>
      <div class="funnel-row">
        <span class="muted">├ 네거티브 필터</span>
        <span class="muted">−{negative_filtered}건</span>
      </div>
      <div class="funnel-row">
        <span class="muted">├ AI 부적합 판정</span>
        <span class="red">−{ai_rejected}건</span>
      </div>
      <div class="funnel-row result">
        <span>✅ 신규 적합 공고</span>
        <span class="green">{final_count}건</span>
      </div>
    </div>

    <!-- 상태 배너 -->
    <div class="status-banner">{status_msg}</div>

    <!-- 신규 공고 카드 -->
    {'<div style="margin-bottom:28px"><div class="section-title">🔔 신규 적합 공고</div>' + cards_html + '</div>'
      if cards_html else ''}

    <!-- 현재 현황 -->
    <div class="section-title">📊 현재 현황</div>
    <div class="status-grid">
      <div class="status-box">
        <div class="status-num">{len(results)}</div>
        <div class="status-lbl">진행중 공고</div>
      </div>
      <div class="status-box">
        <div class="status-num">{len(archives)}</div>
        <div class="status-lbl">마감 (아카이브)</div>
      </div>
      <div class="status-box">
        <div class="status-num">{passed}</div>
        <div class="status-lbl">오늘 1차 통과</div>
      </div>
    </div>

    <!-- 필터링 상세 (접기식) -->
    {filter_html}

  </div><!-- /body -->

  <!-- 푸터 -->
  <div class="footer">
    AI 노무고문 공고 모니터링 시스템 &nbsp;|&nbsp;
    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 자동 발송
  </div>

</div>
</body>
</html>"""

    def _build_pending_cards(self, pending_items: List[Dict]) -> str:
        if not pending_items:
            return ''
        html = ''
        for item in pending_items:
            dday_label, card_cls, badge_cls = self._dday_info(item.get('deadline', ''))
            source_badge = self._source_badge(item.get('source', ''))
            archive_badge = (
                '<span class="badge badge-archive">Archive 예정</span>'
                if item.get('suggested_target') == 'Archive' else ''
            )
            title = item.get('title', '제목 없음')
            org = item.get('organization', '')
            deadline = item.get('deadline') or '마감일 미상'
            summary = item.get('summary', '')
            url = item.get('url', '#')

            html += f"""
<div class="card {card_cls}">
  <div class="card-badges">
    {source_badge}
    <span class="badge {badge_cls}">{dday_label}</span>
    {archive_badge}
  </div>
  <div class="card-title">{title}</div>
  <div class="card-org">🏢 {org}</div>
  <div class="card-deadline">📅 마감: {deadline}</div>
  <div class="card-summary">{summary}</div>
  <a href="{url}" class="btn">공고 바로가기 →</a>
</div>"""
        return html

    def _dday_info(self, deadline_str: str):
        """마감일 → (label, card_css_class, badge_css_class)"""
        if not deadline_str:
            return '날짜미상', '', 'badge-dday-expired'
        try:
            deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
            diff = (deadline - date.today()).days
            if diff < 0:
                return f'D+{abs(diff)} 마감', 'expired', 'badge-dday-expired'
            if diff == 0:
                return 'D-Day', 'urgent', 'badge-dday-urgent'
            if diff <= 7:
                return f'D-{diff}', 'urgent', 'badge-dday-urgent'
            if diff <= 30:
                return f'D-{diff}', 'warning', 'badge-dday-warning'
            return f'D-{diff}', 'normal', 'badge-dday-normal'
        except (ValueError, TypeError):
            return '날짜미상', '', 'badge-dday-expired'

    def _source_badge(self, source: str) -> str:
        labels = {
            'track_a': ('Track A', 'badge-source-a'),
            'track_b': ('Track B', 'badge-source-b'),
            'track_c': ('나라장터', 'badge-source-c'),
        }
        label, cls = labels.get(source, ('기타', 'badge-dday-expired'))
        return f'<span class="badge {cls}">{label}</span>'

    def _build_filter_detail(self, filtered_items: List[Dict], rejected_items: List[Dict]) -> str:
        if not filtered_items and not rejected_items:
            return ''

        rows = ''
        # 필터링 사유 집계
        reasons: Dict[str, int] = {}
        for item in filtered_items:
            r = item.get('filter_reason', '기타')
            reasons[r] = reasons.get(r, 0) + 1
        for r, cnt in reasons.items():
            rows += f'<div class="detail-row">🚫 {r} &nbsp;<b>{cnt}건</b></div>'

        # AI 거부 집계
        ai_reasons: Dict[str, int] = {}
        for item in rejected_items:
            r = item.get('rejection_reason', '기타')
            ai_reasons[r] = ai_reasons.get(r, 0) + 1
        for r, cnt in ai_reasons.items():
            rows += f'<div class="detail-row">🤖 {r} &nbsp;<b>{cnt}건</b></div>'

        return f"""
<div class="detail-section">
  <div class="detail-title">📋 필터링 상세 내역</div>
  {rows}
</div>"""


# ===========================
# 독립 실행 (테스트용)
# ===========================

if __name__ == '__main__':
    print("이메일 발송기 테스트")
    sender = EmailSender()
    if sender.enabled:
        test_pending = [
            {
                'title': '2026년 노무자문위원 위촉 공고',
                'organization': '한국환경공단',
                'url': 'https://www.keco.or.kr/notice/1',
                'deadline': '2026-03-12',
                'summary': '2년 임기 노무자문위원 1명 모집. 서류 및 면접 전형.',
                'suggested_target': 'Results',
                'source': 'track_a',
            },
            {
                'title': '고문노무사 선정 공고',
                'organization': '인천항만공사',
                'url': 'https://www.icpa.or.kr/notice/2',
                'deadline': '2026-04-10',
                'summary': '상시 자문을 위한 고문노무사 위촉. 마감일 내 이메일 접수.',
                'suggested_target': 'Results',
                'source': 'track_b',
            },
        ]
        sender.send_search_summary(
            stats={'total': 120, 'duplicates': 60, 'keyword_failed': 30,
                   'negative_filtered': 10, 'passed': 5},
            filtered_items=[],
            rejected_items=[{'rejection_reason': 'AI 분석: 관련 없음', 'title': '테스트'}],
            results=[],
            archives=[],
            pending_items=test_pending,
        )
    else:
        print("이메일 설정이 비활성화되어 테스트 스킵")
