"""
AI 노무고문 공고 모니터링 웹 서비스
Google Sheets 기반 데이터베이스 + Streamlit 웹 인터페이스
"""

__version__ = "1.0.0"

# Windows cp949 인코딩 문제 해결
# print()에서 이모지(❌, ✅, ⏳ 등) 출력 시
# 'cp949 codec can't encode character' 에러를 방지하기 위해
# stdout/stderr를 UTF-8로 재설정
import sys
import io

if sys.platform == 'win32':
    try:
        # stdout이 TextIOWrapper인 경우 (일반 콘솔)
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace'
            )
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding='utf-8', errors='replace'
            )
    except Exception:
        # Streamlit 환경 등에서는 이미 UTF-8일 수 있음 → 무시
        pass
