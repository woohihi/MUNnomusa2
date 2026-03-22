"""
웹 크롤러 모듈
네이버 API snippet이 부족할 때 원본 URL에서 공고 본문을 직접 수집
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import List


class WebScraper:
    """공공기관 공고 페이지 본문 추출기"""

    TIMEOUT = 8          # 페이지 응답 대기 최대 시간 (초)
    MAX_CHARS = 2500     # Gemini에 전달할 본문 최대 글자수

    # 본문 영역 탐색 우선순위 (id/class 키워드)
    _CONTENT_IDS = re.compile(
        r'content|main|body|view|detail|notice|article|board', re.I
    )

    # 제거할 태그
    _NOISE_TAGS: List[str] = [
        'script', 'style', 'nav', 'header', 'footer',
        'aside', 'iframe', 'noscript', 'form',
    ]

    # 첨부파일만 있는 페이지 판단 키워드
    _ATTACHMENT_ONLY_KEYWORDS = ['붙임', '첨부파일', '별첨', '참조', 'hwp', 'pdf']

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        })

    def fetch(self, url: str) -> str:
        """
        URL에서 공고 본문 텍스트 추출.

        Returns:
            추출된 본문 텍스트 (최대 MAX_CHARS자). 실패 시 빈 문자열.
        """
        if not url or not url.startswith('http'):
            return ''

        try:
            resp = self._session.get(url, timeout=self.TIMEOUT, allow_redirects=True)
            resp.encoding = resp.apparent_encoding  # 한국어 인코딩 자동 감지 (EUC-KR 포함)

            if resp.status_code != 200:
                return ''

            return self._parse(resp.text, url)

        except requests.exceptions.Timeout:
            print(f"⏱  크롤링 타임아웃: {url[:60]}")
            return ''
        except Exception as e:
            print(f"⚠️  크롤링 실패 ({url[:60]}...): {type(e).__name__}")
            return ''

    def enrich_items(self, items: list, min_desc_len: int = 80) -> int:
        """
        description이 짧은 항목들의 본문을 크롤링으로 보강.

        Args:
            items: search_results 리스트 (dict). 'description', 'link' 키 사용
            min_desc_len: 이 글자수 미만이면 크롤링 시도

        Returns:
            실제로 보강된 항목 수
        """
        enriched = 0
        for item in items:
            desc = item.get('description', '') or ''
            # snippet이 충분하면 스킵
            if len(desc) >= min_desc_len:
                continue

            url = item.get('link', '')
            scraped = self.fetch(url)
            if scraped:
                item['description'] = scraped
                enriched += 1

        return enriched

    # ===========================
    # 내부 파싱 로직
    # ===========================

    def _parse(self, html: str, url: str) -> str:
        soup = BeautifulSoup(html, 'html.parser')

        # 불필요한 태그 제거
        for tag in soup(self._NOISE_TAGS):
            tag.decompose()

        # 본문 영역 우선 탐색
        content = (
            soup.find('article')
            or soup.find('main')
            or self._find_by_attr(soup, 'id', self._CONTENT_IDS)
            or self._find_by_attr(soup, 'class', self._CONTENT_IDS)
            or soup.find('body')
        )

        if not content:
            return ''

        text = content.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text).strip()  # 다중 공백 정리

        # 너무 짧으면 본문이 없는 것으로 판단
        if len(text) < 50:
            return ''

        # 첨부파일만 있는 페이지 여부 표시
        text_lower = text.lower()
        is_attachment_only = (
            len(text) < 200
            and any(kw in text_lower for kw in self._ATTACHMENT_ONLY_KEYWORDS)
        )
        if is_attachment_only:
            return f'[첨부파일 확인 필요] {text[:200]}'

        return text[:self.MAX_CHARS]

    @staticmethod
    def _find_by_attr(soup: BeautifulSoup, attr: str, pattern: re.Pattern):
        """id 또는 class 속성으로 태그 탐색"""
        for tag in soup.find_all(True):
            val = tag.get(attr, '')
            val_str = ' '.join(val) if isinstance(val, list) else str(val)
            if pattern.search(val_str):
                return tag
        return None
