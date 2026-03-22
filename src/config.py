"""
설정 관리 모듈
환경 변수 및 전역 상수 정의
"""

import os
from typing import Dict, Any


def _load_streamlit_secrets() -> Dict[str, Any]:
    """
    Streamlit 런타임이 활성화된 경우에만 st.secrets에서 설정 로드.
    GitHub Actions / CLI 환경에서는 빈 딕셔너리 반환.
    """
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is None:
            return {}

        import streamlit as st
        config = {}
        config['naver_client_id'] = st.secrets.get('NAVER_CLIENT_ID', '')
        config['naver_client_secret'] = st.secrets.get('NAVER_CLIENT_SECRET', '')
        config['gemini_api_key'] = st.secrets.get('GEMINI_API_KEY', '')
        config['google_sheets_id'] = st.secrets.get('GOOGLE_SHEETS_ID', '')
        config['g2b_api_key'] = st.secrets.get('G2B_API_KEY', '')

        if 'gcp_service_account' in st.secrets:
            config['gcp_service_account'] = dict(st.secrets['gcp_service_account'])

        if 'email' in st.secrets:
            config['email'] = dict(st.secrets['email'])

        return config
    except Exception:
        return {}


# ===========================
# API 키 및 인증 정보
# ===========================

def get_config() -> Dict[str, Any]:
    """
    Streamlit Secrets 또는 환경 변수에서 설정 로드

    Returns:
        설정 딕셔너리
    """
    # Streamlit Cloud에서 실행 중인 경우 st.secrets 우선 사용
    config = _load_streamlit_secrets()
    
    # 환경 변수에서 로드 (GitHub Actions 등)
    if not config.get('naver_client_id'):
        config['naver_client_id'] = os.getenv('NAVER_CLIENT_ID', '')
    if not config.get('naver_client_secret'):
        config['naver_client_secret'] = os.getenv('NAVER_CLIENT_SECRET', '')
    if not config.get('gemini_api_key'):
        config['gemini_api_key'] = os.getenv('GEMINI_API_KEY', '')
    if not config.get('google_sheets_id'):
        config['google_sheets_id'] = os.getenv('GOOGLE_SHEETS_ID', '')
    if not config.get('g2b_api_key'):
        config['g2b_api_key'] = os.getenv('G2B_API_KEY', '')  # 없으면 Track C 비활성화

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

    # 로컬 CLI 실행용: .streamlit/secrets.toml 직접 로드 (환경변수도 없을 경우)
    if not config.get('naver_client_id') and os.path.exists('.streamlit/secrets.toml'):
        try:
            try:
                import tomllib  # Python 3.11+
                open_mode = 'rb'
            except ImportError:
                import toml as tomllib  # External lib
                open_mode = 'r'
                
            with open('.streamlit/secrets.toml', open_mode) as f:
                secrets = tomllib.load(f)
                
            config['naver_client_id'] = secrets.get('NAVER_CLIENT_ID', '')
            config['naver_client_secret'] = secrets.get('NAVER_CLIENT_SECRET', '')
            config['gemini_api_key'] = secrets.get('GEMINI_API_KEY', '')
            config['google_sheets_id'] = secrets.get('GOOGLE_SHEETS_ID', '')
            config['g2b_api_key'] = secrets.get('G2B_API_KEY', '')  # 나라장터 (선택)

            if 'gcp_service_account' in secrets:
                config['gcp_service_account'] = secrets['gcp_service_account']

            if 'email' in secrets:
                config['email'] = secrets['email']
        except Exception as e:
            print(f"⚠️ 로컬 secrets.toml 로드 중 오류: {e}")
    
    return config


# ===========================
# Google Sheets 설정
# ===========================

# 네이버 검색 엔드포인트
NAVER_ENDPOINTS = {
    'webkr': 'https://openapi.naver.com/v1/search/webkr.json',
    'blog':  'https://openapi.naver.com/v1/search/blog.json',
    'news':  'https://openapi.naver.com/v1/search/news.json',
}

# Track A grade별 검색 결과 수 (기관 정밀 감시)
GRADE_DISPLAY_MAP = {'A': 20, 'B': 10, 'C': 5}

# 나라장터(G2B) 검색 키워드 (Track C)
G2B_KEYWORDS = ['노무자문', '고문노무사', '자문노무사']

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
# grade: A(집중/display=20), B(일반/display=10), C(최소/display=5). 없으면 'B' 기본값
CONFIG_COLUMNS = ['organization', 'keywords', 'active', 'grade']

# Results Sheet 컬럼
RESULTS_COLUMNS = [
    'url', 'title', 'organization', 'deadline',
    'summary', 'collected_date', 'source', 'search_keyword', 'search_query'
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
# status:   검토중 / 적합 / 거절 / 보류  (사용자가 시트에서 직접 입력)
# priority: 긴급 / 일반 / 자동통과 / 기한미정 / 과거참고 / 분석실패  (시스템 자동 산정)
PENDING_COLUMNS = [
    'url', 'title', 'organization', 'deadline',
    'summary', 'suggested_target', 'collected_date',
    'source', 'search_keyword', 'search_query', 'status', 'priority'
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
# '전문가 모집', '자문위원', '인사위원' 등 범용 키워드는 노이즈가 심하므로 구체화하거나 제거
DEFAULT_JOB_KEYWORDS = [
    '노무고문', '고문노무사', '자문노무사', '노무자문', 
    '인사노무 자문위원', '노무 자문위원', '노무 전문위원', '인사위원회 위원'
]


# ===========================
# 검색 파이프라인 설정
# ===========================

# 14일 (2주) 제한
SEARCH_DAYS_LIMIT = 14

# 네이버 검색 결과 수 (최대 100)
NAVER_DISPLAY_COUNT = 20

# Gemini Rate Limiting (초 단위)
# Pay-as-you-go (Billing Enabled): 0.1 (제한 해제, 고속 분석)
GEMINI_RATE_LIMIT_DELAY = 0.1

# 전처리 점수 기준 (0~100)
SCORE_HIGH_THRESHOLD = 60   # 이 이상 → HIGH priority (Gemini 전송)
SCORE_SKIP_THRESHOLD = 40   # 이 미만 → 스킵 (비용 절감 / 30→40 상향으로 노이즈 감소)


# ===========================
# 전처리 필터 키워드
# ===========================

# 유효 키워드 (Track A 결과 검증용)
# '평가', '심의', '인사'는 너무 광범위하여 제거 (인사말, 심의회 등 노이즈 유발)
VALID_KEYWORDS = [
    '노무', '법률', '고문', '자문', '위원', '위촉'
]

# 네거티브 키워드 (제외 필터)
# 주의: '공사', '용역'은 기관명에 자주 포함되므로 제외
NEGATIVE_KEYWORDS = [
    '입찰', '구매', '청소', '경비', '아파트', '시스템 구축', '건설', 
    '시공', '납품', '물품', '설비', '철거', '폐기물', '운송',
    # 노이즈 필터 (자소서, 뉴스, 광고 등)
    '자기소개서', '자소서', '합격후기', '면접후기', 
    '수강', '강의', '설명회', '이벤트', '교육생',
    '기자', '보도자료', '뉴스', '신문', '속보',
    '홍보', '광고', '무료상담', '법률상담', '무료진단',
    '학원', '과외', '스터디', '동아리',
    '아르바이트', '알바', '단기', '계약직', '파견'
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

