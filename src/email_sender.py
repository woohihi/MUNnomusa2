"""
이메일 발송 모듈
신규 공고 발견 시 자동 알림
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
from datetime import datetime

from .config import get_config, EMAIL_HTML_TEMPLATE


class EmailSender:
    """SMTP 이메일 발송 클래스"""
    
    def __init__(self):
        """SMTP 설정 로드"""
        config = get_config()
        
        self.email_config = config.get('email', {})
        
        if not self.email_config:
            print("⚠️  이메일 설정 없음. 발송 스킵")
            self.enabled = False
        else:
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
    
    def send_new_jobs_alert(self, new_jobs: List[Dict[str, Any]]) -> bool:
        """
        신규 공고 발견 알림 이메일 발송
        
        Args:
            new_jobs: 신규 공고 리스트 [{'title': '...', 'organization': '...', 'url': '...', 'deadline': '...'}, ...]
        
        Returns:
            발송 성공 여부
        """
        if not self.enabled:
            print("📧 이메일 발송 비활성화 상태")
            return False
        
        if not new_jobs:
            print("📧 신규 공고 없음. 이메일 발송 스킵")
            return False
        
        try:
            # HTML 이메일 생성
            subject = f"🔔 신규 노무고문 공고 {len(new_jobs)}건 발견"
            html_body = self._build_html(new_jobs)
            
            # MIME 메시지 생성
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.sender_email
            message['To'] = self.recipient_email
            
            html_part = MIMEText(html_body, 'html', 'utf-8')
            message.attach(html_part)
            
            # SMTP 발송
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            print(f"✅ 이메일 발송 성공: {len(new_jobs)}건 공고")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 발송 실패: {e}")
            return False
    
    def _build_html(self, new_jobs: List[Dict[str, Any]]) -> str:
        """
        HTML 이메일 본문 생성
        
        Args:
            new_jobs: 신규 공고 리스트
        
        Returns:
            HTML 문자열
        """
        # 공고 항목 HTML
        items_html = ""
        
        for job in new_jobs:
            title = job.get('title', 'Unknown')
            organization = job.get('organization', 'Unknown')
            url = job.get('url', '#')
            deadline = job.get('deadline', 'N/A')
            summary = job.get('summary', '')
            
            items_html += f"""
<li style="margin-bottom: 20px;">
    <strong style="font-size: 16px;">{organization}</strong><br>
    <span style="color: #333;">{title}</span><br>
    <span style="color: #666;">마감: {deadline}</span><br>
    <span style="color: #999; font-size: 14px;">{summary}</span><br>
    <a href="{url}" style="color: #1a73e8; text-decoration: none;">🔗 공고 보기</a>
</li>
"""
        
        # 템플릿에 삽입
        html = f"""
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Arial', 'Malgun Gothic', sans-serif; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        h2 {{ color: #1a73e8; }}
        ul {{ list-style: none; padding: 0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>🔔 신규 노무고문 공고 알림</h2>
        <p>총 <strong>{len(new_jobs)}</strong>건의 새로운 공고가 발견되었습니다.</p>
        
        <ul>
            {items_html}
        </ul>
        
        <div class="footer">
            <p>발송 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>이 메일은 AI 노무고문 공고 모니터링 시스템에서 자동 발송되었습니다.</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def send_daily_report(self, search_logs: List[Dict], results: List[Dict], archives: List[Dict]) -> bool:
        """
        일일 검색 리포트 이메일 발송 (비서 스타일)
        
        Args:
            search_logs: 오늘 검색된 로그 리스트
            results: Results 시트 데이터
            archives: Archive 시트 데이터
        
        Returns:
            발송 성공 여부
        """
        if not self.enabled:
            print("📧 이메일 발송 비활성화 상태")
            return False
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            subject = f"📋 노무고문 공고 모니터링 일일 리포트 ({today})"
            html_body = self._build_daily_report_html(search_logs, results, archives)
            
            # MIME 메시지 생성
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.sender_email
            message['To'] = self.recipient_email
            
            html_part = MIMEText(html_body, 'html', 'utf-8')
            message.attach(html_part)
            
            # SMTP 발송
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            print(f"✅ 일일 리포트 발송 성공")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 발송 실패: {e}")
            return False
    
    def _build_daily_report_html(self, search_logs: List[Dict], results: List[Dict], archives: List[Dict]) -> str:
        """
        비서 스타일 일일 리포트 HTML 생성
        """
        today = datetime.now().strftime('%Y년 %m월 %d일')
        now = datetime.now().strftime('%H:%M')
        
        # 오늘 추가된 검색 로그
        today_date = datetime.now().strftime('%Y-%m-%d')
        today_logs = [log for log in search_logs if log.get('timestamp', '').startswith(today_date)]
        
        # 검색 로그 테이블
        log_rows = ""
        for log in today_logs[:20]:  # 최대 20개
            log_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{log.get('title', '')[:50]}...</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{log.get('stage', '')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{log.get('reason', '')[:30]}</td>
            </tr>
            """
        
        # 진행중 공고 (Results)
        results_rows = ""
        for r in results[:10]:  # 최대 10개
            results_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{r.get('organization', '')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">
                    <a href="{r.get('url', '#')}" style="color: #1a73e8;">{r.get('title', '')[:40]}...</a>
                </td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{r.get('deadline', 'N/A')}</td>
            </tr>
            """
        
        # 아카이브 (Archive)
        archive_rows = ""
        for a in archives[:10]:  # 최대 10개
            archive_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{a.get('organization', '')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{a.get('title', '')[:40]}...</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{a.get('deadline', 'N/A')}</td>
            </tr>
            """
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; line-height: 1.8; color: #333; }}
        .container {{ max-width: 700px; margin: 0 auto; padding: 30px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
        .content {{ background: #fff; padding: 30px; border: 1px solid #eee; }}
        .section {{ margin-bottom: 30px; }}
        .section-title {{ font-size: 18px; font-weight: bold; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; margin-bottom: 15px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th {{ background: #f8f9fa; padding: 10px; text-align: left; font-weight: bold; }}
        .summary-box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .summary-item {{ display: inline-block; margin-right: 30px; }}
        .summary-number {{ font-size: 24px; font-weight: bold; color: #667eea; }}
        .footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">📋 일일 모니터링 리포트</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">{today} {now} 기준</p>
        </div>
        
        <div class="content">
            <p style="font-size: 16px;">안녕하세요,</p>
            <p>오늘 하루 노무고문 공고 모니터링 결과를 보고드립니다.</p>
            
            <div class="summary-box">
                <div class="summary-item">
                    <div class="summary-number">{len(today_logs)}</div>
                    <div>오늘 수집</div>
                </div>
                <div class="summary-item">
                    <div class="summary-number">{len(results)}</div>
                    <div>진행중 공고</div>
                </div>
                <div class="summary-item">
                    <div class="summary-number">{len(archives)}</div>
                    <div>마감 공고</div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">📌 진행중 공고 (Results)</div>
                {"<p style='color: #999;'>진행중인 공고가 없습니다.</p>" if not results else f'''
                <table>
                    <tr>
                        <th>기관</th>
                        <th>제목</th>
                        <th>마감일</th>
                    </tr>
                    {results_rows}
                </table>
                {"<p style='color: #999; font-size: 12px;'>* 상위 10건만 표시</p>" if len(results) > 10 else ""}
                '''}
            </div>
            
            <div class="section">
                <div class="section-title">📦 마감 공고 (Archive)</div>
                {"<p style='color: #999;'>아카이브된 공고가 없습니다.</p>" if not archives else f'''
                <table>
                    <tr>
                        <th>기관</th>
                        <th>제목</th>
                        <th>마감일</th>
                    </tr>
                    {archive_rows}
                </table>
                {"<p style='color: #999; font-size: 12px;'>* 상위 10건만 표시</p>" if len(archives) > 10 else ""}
                '''}
            </div>
            
            <div class="section">
                <div class="section-title">🔍 오늘 검색 로그</div>
                {"<p style='color: #999;'>오늘 수집된 로그가 없습니다.</p>" if not today_logs else f'''
                <table>
                    <tr>
                        <th>제목</th>
                        <th>상태</th>
                        <th>사유</th>
                    </tr>
                    {log_rows}
                </table>
                {"<p style='color: #999; font-size: 12px;'>* 상위 20건만 표시</p>" if len(today_logs) > 20 else ""}
                '''}
            </div>
            
            <p style="margin-top: 30px;">추가 문의사항이 있으시면 말씀해 주세요.</p>
            <p>감사합니다.</p>
        </div>
        
        <div class="footer">
            <p>이 메일은 AI 노무고문 공고 모니터링 시스템에서 자동 발송되었습니다.</p>
            <p>발송 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def send_search_summary(self, stats: Dict, filtered_items: List[Dict], rejected_items: List[Dict], results: List[Dict], archives: List[Dict]) -> bool:
        """
        검색 결과 요약 이메일 발송 (신규 공고 없을 때도 사용 가능)
        
        Args:
            stats: 전처리 통계 {'total': ..., 'duplicates': ..., 'passed': ...}
            filtered_items: 전처리에서 필터링된 항목
            rejected_items: AI가 거부한 항목
            results: Results 시트 데이터 (현재 진행중)
            archives: Archive 시트 데이터 (마감됨)
        
        Returns:
            발송 성공 여부
        """
        if not self.enabled:
            print("📧 이메일 발송 비활성화 상태")
            return False
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            subject = f"📋 노무고문 공고 검색 결과 보고 ({today})"
            html_body = self._build_search_summary_html(stats, filtered_items, rejected_items, results, archives)
            
            # MIME 메시지 생성
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.sender_email
            message['To'] = self.recipient_email
            
            html_part = MIMEText(html_body, 'html', 'utf-8')
            message.attach(html_part)
            
            # SMTP 발송
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            print(f"✅ 검색 결과 요약 발송 성공")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 발송 실패: {e}")
            return False
    
    def _build_search_summary_html(self, stats: Dict, filtered_items: List[Dict], rejected_items: List[Dict], results: List[Dict], archives: List[Dict]) -> str:
        """
        비서 스타일 검색 결과 요약 HTML 생성
        """
        today = datetime.now().strftime('%Y년 %m월 %d일')
        now = datetime.now().strftime('%H:%M')
        
        total = stats.get('total', 0)
        duplicates = stats.get('duplicates', 0)
        keyword_failed = stats.get('keyword_failed', 0)
        negative_filtered = stats.get('negative_filtered', 0)
        passed = stats.get('passed', 0)
        
        # 필터링 사유별 그룹화
        filter_reasons = {}
        for item in filtered_items:
            reason = item.get('filter_reason', '기타')
            if reason not in filter_reasons:
                filter_reasons[reason] = []
            filter_reasons[reason].append(item.get('title', '')[:40])
        
        # AI 거부 사유별 그룹화
        reject_reasons = {}
        for item in rejected_items:
            reason = item.get('reason', '기타')
            if reason not in reject_reasons:
                reject_reasons[reason] = []
            reject_reasons[reason].append(item.get('title', '')[:40])
        
        # 필터링 사유 HTML
        filter_html = ""
        for reason, titles in filter_reasons.items():
            filter_html += f"""
            <div style="margin-bottom: 15px;">
                <strong style="color: #e74c3c;">📌 {reason}</strong> ({len(titles)}건)
                <ul style="margin: 5px 0; padding-left: 20px; color: #666;">
                    {''.join([f'<li>{t}...</li>' for t in titles[:3]])}
                    {f'<li style="color: #999;">외 {len(titles)-3}건...</li>' if len(titles) > 3 else ''}
                </ul>
            </div>
            """
        
        # AI 거부 사유 HTML
        reject_html = ""
        for reason, titles in reject_reasons.items():
            reject_html += f"""
            <div style="margin-bottom: 15px;">
                <strong style="color: #f39c12;">🤖 {reason}</strong> ({len(titles)}건)
                <ul style="margin: 5px 0; padding-left: 20px; color: #666;">
                    {''.join([f'<li>{t}...</li>' for t in titles[:3]])}
                    {f'<li style="color: #999;">외 {len(titles)-3}건...</li>' if len(titles) > 3 else ''}
                </ul>
            </div>
            """
        
        # 결론 메시지
        if passed == 0 and len(rejected_items) == 0:
            conclusion = "오늘 검색에서 신규 공고가 발견되지 않았습니다. 대부분 기존에 수집된 공고이거나 관련 없는 내용이었습니다."
        elif passed == 0:
            conclusion = "오늘 검색에서 적합한 신규 공고가 발견되지 않았습니다. AI 분석 결과 모두 노무고문 관련 공고가 아닌 것으로 판단되었습니다."
        else:
            conclusion = f"오늘 검색에서 {passed}건의 적합한 공고가 발견되어 분류 대기 중입니다."
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; line-height: 1.8; color: #333; }}
        .container {{ max-width: 700px; margin: 0 auto; padding: 30px; }}
        .header {{ background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
        .content {{ background: #fff; padding: 30px; border: 1px solid #eee; }}
        .section {{ margin-bottom: 25px; }}
        .section-title {{ font-size: 16px; font-weight: bold; color: #333; border-left: 4px solid #3498db; padding-left: 10px; margin-bottom: 10px; }}
        .summary-box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .stat-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
        .stat-label {{ color: #666; }}
        .stat-value {{ font-weight: bold; }}
        .conclusion {{ background: #e8f4fd; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db; }}
        .footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">📋 검색 결과 보고</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">{today} {now} 기준</p>
        </div>
        
        <div class="content">
            <p style="font-size: 16px;">안녕하세요,</p>
            <p>오늘 노무고문 공고 검색 결과를 보고드립니다.</p>
            
            <div class="summary-box">
                <div class="stat-row">
                    <span class="stat-label">총 검색 결과</span>
                    <span class="stat-value">{total}건</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">├ 중복 제외</span>
                    <span class="stat-value" style="color: #95a5a6;">{duplicates}건</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">├ 키워드 미충족</span>
                    <span class="stat-value" style="color: #95a5a6;">{keyword_failed}건</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">├ 네거티브 필터</span>
                    <span class="stat-value" style="color: #95a5a6;">{negative_filtered}건</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">├ AI 부적합 판정</span>
                    <span class="stat-value" style="color: #e74c3c;">{len(rejected_items)}건</span>
                </div>
                <div class="stat-row" style="border-top: 1px solid #ddd; padding-top: 8px; margin-top: 8px;">
                    <span class="stat-label"><strong>→ 적합 공고</strong></span>
                    <span class="stat-value" style="color: #27ae60; font-size: 18px;">{passed - len(rejected_items)}건</span>
                </div>
            </div>
            
            <div class="conclusion">
                <p style="margin: 0;">{conclusion}</p>
            </div>
            
            {"" if not filter_html else f'''
            <div class="section" style="margin-top: 25px;">
                <div class="section-title">🚫 전처리 필터링 상세</div>
                {filter_html}
            </div>
            '''}
            
            {"" if not reject_html else f'''
            <div class="section">
                <div class="section-title">🤖 AI 분석 결과 (부적합)</div>
                {reject_html}
            </div>
            '''}
            
            <div class="section" style="margin-top: 25px;">
                <div class="section-title">📊 현재 현황</div>
                <p>• 진행중 공고: <strong>{len(results)}건</strong></p>
                <p>• 마감 공고 (아카이브): <strong>{len(archives)}건</strong></p>
            </div>
            
            <p style="margin-top: 30px;">추가 문의사항이 있으시면 말씀해 주세요.</p>
            <p>감사합니다.</p>
        </div>
        
        <div class="footer">
            <p>이 메일은 AI 노무고문 공고 모니터링 시스템에서 자동 발송되었습니다.</p>
            <p>발송 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""
        return html


# ===========================
# 독립 실행 (테스트용)
# ===========================

if __name__ == '__main__':
    print("이메일 발송기 테스트")
    print("-" * 50)
    
    sender = EmailSender()
    
    if sender.enabled:
        # 더미 데이터
        test_jobs = [
            {
                'title': '노무자문위원 위촉',
                'organization': '한국환경공단',
                'url': 'http://example.com/1',
                'deadline': '2026-02-20',
                'summary': '2년 임기 자문위원 모집'
            }
        ]
        
        sender.send_new_jobs_alert(test_jobs)
    else:
        print("이메일 설정이 비활성화되어 테스트 스킵")
