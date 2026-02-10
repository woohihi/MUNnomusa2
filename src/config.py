"""
설정 관리 모듈
환경 변수 및 전역 상수 정의
"""

import os
import streamlit as st
from typing import Dict, Any

# ===========================
# API 키 및 인증 정보
# ===========================

def get_config() -> Dict[str, Any]:
    """
    Streamlit Secrets 또는 환경 변수에서 설정 로드
    
    Returns:
        설정 딕셔너리
    """
    config = {}
    
    # Streamlit Secrets에서 로드 시도 (Streamlit Cloud용)
    if hasattr(st, 'secrets'):
        try:
            config['naver_client_id'] = st.secrets.get('NAVER_CLIENT_ID', '')
            config['naver_client_secret'] = st.secrets.get('NAVER_CLIENT_SECRET', '')
            config['gemini_api_key'] = st.secrets.get('GEMINI_API_KEY', '')
            config['google_sheets_id'] = st.secrets.get('GOOGLE_SHEETS_ID', '')
            
            # Google Service Account (딕셔너리로 저장됨)
            if 'gcp_service_account' in st.secrets:
                config['gcp_service_account'] = dict(st.secrets['gcp_service_account'])
            
            # 이메일 설정
            if 'email' in st.secrets:
                config['email'] = dict(st.secrets['email'])
                
        except Exception:
            # Secrets 없을 때 환경 변수로 폴백
            pass
    
    # 환경 변수에서 로드 (GitHub Actions, 로컬 개발용)
    if not config.get('naver_client_id'):
        config['naver_client_id'] = os.getenv('NAVER_CLIENT_ID', '')
    if not config.get('naver_client_secret'):
        config['naver_client_secret'] = os.getenv('NAVER_CLIENT_SECRET', '')
    if not config.get('gemini_api_key'):
        config['gemini_api_key'] = os.getenv('GEMINI_API_KEY', '')
    if not config.get('google_sheets_id'):
        config['google_sheets_id'] = os.getenv('GOOGLE_SHEETS_ID', '')
    
    # GCP Service Account JSON (환경 변수의 경우 JSON 문자열로 전달)
    if not config.get('gcp_service_account') and os.getenv('GOOGLE_SHEETS_CREDS'):
        import json
        config['gcp_service_account'] = json.loads(os.getenv('GOOGLE_SHEETS_CREDS'))

    # 이메일 설정 (환경 변수)
    if not config.get('email') and os.getenv('SENDER_EMAIL'):
        config['email'] = {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', 587)),
            'sender_email': os.getenv('SENDER_EMAIL', ''),
            'sender_password': os.getenv('SENDER_PASSWORD', ''),
            'recipient_email': os.getenv('RECIPIENT_EMAIL', '')
        }
    
    return config


# ===========================
# Google Sheets 설정
# ===========================

SHEET_NAMES = {
    'config': 'Config',
    'results': 'Results',
    'archive': 'Archive',
    'search_log': 'SearchLog',
    'keywords': 'Keywords',
    'excluded': 'Excluded',  # 제외 목록
    'pending': 'Pending'  # 검토 대기 (자동 검색 결과)
}

# Config Sheet 컬럼
CONFIG_COLUMNS = ['organization', 'keywords', 'active']

# Results Sheet 컬럼
RESULTS_COLUMNS = [
    'url', 'title', 'organization', 'deadline', 
    'summary', 'collected_date'
]

# Archive Sheet 컬럼 (Results + CRM 데이터)
ARCHIVE_COLUMNS = RESULTS_COLUMNS + [
    'term_months', 'start_date', 'next_expected_date'
]

# SearchLog Sheet 컬럼
SEARCHLOG_COLUMNS = [
    'timestamp', 'url', 'title', 'search_keyword', 
    'search_query', 'source', 'stage', 'reason'
]

# Keywords Sheet 컬럼
KEYWORDS_COLUMNS = ['keyword', 'active']

# Excluded Sheet 컬럼 (제외된 URL 목록)
EXCLUDED_COLUMNS = ['url', 'title', 'reason', 'excluded_date']

# Pending Sheet 컬럼 (검토 대기 공고)
PENDING_COLUMNS = [
    'url', 'title', 'organization', 'deadline', 
    'summary', 'suggested_target', 'collected_date'
]


# ===========================
# 초기 데이터 (10개 기관)
# ===========================

INITIAL_ORGANIZATIONS = [
    {'organization': '한국환경공단', 'keywords': '노무고문,노무자문', 'active': True},
    {'organization': '한국사학진흥재단', 'keywords': '노무고문,노무자문', 'active': True},
    {'organization': '인천항만공사', 'keywords': '노무고문,노무자문', 'active': True},
    {'organization': '광주광역시 서구시설관리공단', 'keywords': '노무고문,노무자문', 'active': True},
    {'organization': '전국공공산업노동조합연맹', 'keywords': '노무고문,노무자문', 'active': True},
    {'organization': '한국인공지능소프트웨어산업협회', 'keywords': '노무고문,노무자문', 'active': True},
    {'organization': '유네스코한국위원회', 'keywords': '노무고문,노무자문', 'active': True},
    {'organization': '한국토지주택공사', 'keywords': '노무고문,노무자문', 'active': True},
    {'organization': '한국원자력연구원', 'keywords': '노무고문,노무자문', 'active': True},
    {'organization': '한국항로표지기술원', 'keywords': '노무고문,노무자문', 'active': True},
]

# 기본 직무 키워드 (Track B 검색용)
DEFAULT_JOB_KEYWORDS = [
    '노무고문', '고문노무사', '자문노무사', '노무자문', 
    '자문위원', '인사위원', '전문가 모집'
]


# ===========================
# 검색 파이프라인 설정
# ===========================

# 14일 (2주) 제한
SEARCH_DAYS_LIMIT = 14

# 네이버 검색 결과 수 (최대 100)
NAVER_DISPLAY_COUNT = 20

# Gemini Rate Limiting (초 단위)
GEMINI_RATE_LIMIT_DELAY = 0.5  # 분당 15 RPM 준수


# ===========================
# 전처리 필터 키워드
# ===========================

# 유효 키워드 (Track A 결과 검증용)
VALID_KEYWORDS = [
    '노무', '법률', '고문', '자문', '위원', 
    '평가', '인사', '심의'
]

# 네거티브 키워드 (제외 필터)
# 주의: '공사', '용역'은 기관명에 자주 포함되므로 제외
NEGATIVE_KEYWORDS = [
    '입찰', '구매', '청소', 
    '경비', '아파트', '시스템 구축', '건설', 
    '시공', '납품', '물품', '설비',
    # 노이즈 필터 (자소서, 뉴스, 광고 등)
    '자기소개서', '자소서', '합격후기', '면접후기', 
    '수강', '강의', '설명회', '이벤트',
    '기자', '보도자료', '뉴스', '신문',
    '홍보', '광고', '무료상담'
]


# ===========================
# 예측 시스템 설정
# ===========================

# 예측 알림 D-day 기준 (일 단위)
PREDICTION_ALERT_DAYS = 30


# ===========================
# 출력 포맷
# ===========================

# Obsidian 마크다운 템플릿
OBSIDIAN_TEMPLATE = """
# 노무고문 공고 목록

생성일: {date}

{content}
"""

# 이메일 HTML 템플릿
EMAIL_HTML_TEMPLATE = """
<html>
<body>
<h2>🔔 신규 노무고문 공고 알림</h2>
<p>총 <strong>{count}</strong>건의 새로운 공고가 발견되었습니다.</p>

<ul>
{items}
</ul>

<p>상세 내용은 <a href="https://your-streamlit-app.com">웹 대시보드</a>에서 확인하세요.</p>
</body>
</html>
"""
