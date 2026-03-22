"""
웹 크롤러 모듈
네이버 API snippet이 부족할 때 원본 URL에서 공고 본문을 직접 수집.
첨부파일(PDF / HWP / HWPX)이 있으면 다운로드 후 텍스트 추출.
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from typing import List
from urllib.parse import urljoin, urlparse


class WebScraper:
    """공공기관 공고 페이지 본문 + 첨부파일 텍스트 추출기"""

    TIMEOUT = 8           # 페이지 응답 대기 (초)
    FILE_TIMEOUT = 15     # 첨부파일 다운로드 대기 (초)
    MAX_CHARS = 3000      # Gemini에 전달할 최대 글자수

    # 본문 영역 탐색 우선순위 (id/class 키워드)
    _CONTENT_IDS = re.compile(
        r'content|main|body|view|detail|notice|article|board', re.I
    )

    # 제거할 태그
    _NOISE_TAGS: List[str] = [
        'script', 'style', 'nav', 'header', 'footer',
        'aside', 'iframe', 'noscript', 'form',
    ]

    # 첨부파일 확장자
    _ATTACH_EXTS = ('.pdf', '.hwp', '.hwpx')

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

    # ===========================
    # 공개 인터페이스
    # ===========================

    def fetch(self, url: str) -> str:
        """
        URL에서 공고 본문 텍스트 추출.
        본문이 부족하면 첨부파일(PDF/HWP/HWPX)에서 추가 텍스트 추출.

        Returns:
            추출된 텍스트 (최대 MAX_CHARS자). 실패 시 빈 문자열.
        """
        if not url or not url.startswith('http'):
            return ''

        try:
            resp = self._session.get(url, timeout=self.TIMEOUT, allow_redirects=True)
            resp.encoding = resp.apparent_encoding

            if resp.status_code != 200:
                return ''

            soup = BeautifulSoup(resp.text, 'html.parser')
            page_text = self._parse_page(soup)

            # 본문이 충분하면 첨부파일 탐색 불필요
            if len(page_text) >= 300 and '[첨부파일' not in page_text:
                return page_text[:self.MAX_CHARS]

            # 첨부파일 링크 탐색 후 텍스트 보강
            attach_text = self._extract_from_attachments(soup, url)
            if attach_text:
                combined = (page_text + '\n\n[첨부파일 내용]\n' + attach_text).strip()
                return combined[:self.MAX_CHARS]

            return page_text[:self.MAX_CHARS]

        except requests.exceptions.Timeout:
            print(f"⏱  크롤링 타임아웃: {url[:60]}")
            return ''
        except Exception as e:
            print(f"⚠️  크롤링 실패 ({url[:60]}...): {type(e).__name__}")
            return ''

    def enrich_items(self, items: list, min_desc_len: int = 80) -> int:
        """
        description이 짧은 항목들의 본문을 크롤링으로 보강.

        Returns:
            실제로 보강된 항목 수
        """
        enriched = 0
        for item in items:
            desc = item.get('description', '') or ''
            if len(desc) >= min_desc_len:
                continue

            url = item.get('link', '')
            scraped = self.fetch(url)
            if scraped:
                item['description'] = scraped
                enriched += 1

        return enriched

    # ===========================
    # 페이지 본문 파싱
    # ===========================

    def _parse_page(self, soup: BeautifulSoup) -> str:
        for tag in soup(self._NOISE_TAGS):
            tag.decompose()

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
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) < 50:
            return ''

        # 첨부파일만 있는 페이지 표시
        text_lower = text.lower()
        is_attachment_only = (
            len(text) < 200
            and any(kw in text_lower for kw in ['붙임', '첨부파일', '별첨', '참조', 'hwp', 'pdf'])
        )
        if is_attachment_only:
            return f'[첨부파일 확인 필요] {text[:200]}'

        return text

    # ===========================
    # 첨부파일 탐색 + 추출
    # ===========================

    def _extract_from_attachments(self, soup: BeautifulSoup, base_url: str) -> str:
        """
        페이지에서 첨부파일 링크를 찾아 텍스트 추출.
        PDF → pdfplumber, HWP → olefile PrvText, HWPX → XML 파싱.
        """
        links = self._find_attachment_links(soup, base_url)
        if not links:
            return ''

        texts = []
        for file_url, ext in links[:3]:  # 최대 3개 파일만 처리
            try:
                file_bytes = self._download_file(file_url)
                if not file_bytes:
                    continue

                if ext == '.pdf':
                    text = self._extract_pdf(file_bytes)
                elif ext == '.hwpx':
                    text = self._extract_hwpx(file_bytes)
                elif ext == '.hwp':
                    text = self._extract_hwp(file_bytes)
                else:
                    continue

                if text and len(text) > 30:
                    print(f"    📎 첨부파일 추출 성공 ({ext.upper()}): {len(text)}자")
                    texts.append(text)

            except Exception as e:
                print(f"    ⚠️  첨부파일 처리 실패 ({ext}): {type(e).__name__}")
                continue

        return '\n\n'.join(texts)[:2000]

    def _find_attachment_links(self, soup: BeautifulSoup, base_url: str) -> list:
        """
        페이지에서 PDF/HWP/HWPX 링크 추출.
        Returns: [(절대URL, 확장자), ...]
        """
        found = []
        seen = set()

        for tag in soup.find_all('a', href=True):
            href = tag['href']
            lower = href.lower()

            # 확장자 확인
            ext = None
            for e in self._ATTACH_EXTS:
                if lower.endswith(e) or (e in lower and '?' in lower):
                    ext = e
                    break

            # 다운로드/첨부 링크 패턴 (확장자 없어도 URL 패턴으로 탐지)
            if not ext:
                dl_patterns = ['download', 'filedown', 'atchfile', 'attach', 'file_down', 'dwnld']
                if any(p in lower for p in dl_patterns):
                    # Content-Type으로 판별해야 하므로 일단 포함
                    ext = '.pdf'  # 시도해볼 확장자 (실제 타입은 다운로드 후 확인)

            if not ext:
                continue

            # 절대 URL 변환
            abs_url = urljoin(base_url, href)
            if abs_url in seen:
                continue
            seen.add(abs_url)
            found.append((abs_url, ext))

        return found

    def _download_file(self, url: str) -> bytes:
        """파일 다운로드. 실패 시 빈 bytes 반환."""
        try:
            resp = self._session.get(url, timeout=self.FILE_TIMEOUT, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 100:
                return resp.content
        except Exception:
            pass
        return b''

    # ===========================
    # 파일 형식별 텍스트 추출
    # ===========================

    def _extract_pdf(self, data: bytes) -> str:
        """PDF → 텍스트 (pdfplumber 사용)"""
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages_text = []
                for page in pdf.pages[:10]:  # 최대 10페이지
                    t = page.extract_text()
                    if t:
                        pages_text.append(t)
                return '\n'.join(pages_text)
        except ImportError:
            print("    ⚠️  pdfplumber 미설치: pip install pdfplumber")
            return ''
        except Exception:
            return ''

    def _extract_hwp(self, data: bytes) -> str:
        """
        HWP → 텍스트.
        OLE 컨테이너의 PrvText 스트림(미리보기 텍스트)을 읽음.
        완전한 파싱은 아니지만 공고 분류에 충분한 텍스트를 빠르게 추출.
        """
        try:
            import olefile
            with olefile.OleFileIO(io.BytesIO(data)) as ole:
                # PrvText: HWP 파일의 텍스트 미리보기 스트림 (UTF-16LE)
                if ole.exists('PrvText'):
                    raw = ole.openstream('PrvText').read()
                    text = raw.decode('utf-16-le', errors='ignore')
                    text = re.sub(r'\s+', ' ', text).strip()
                    if len(text) > 30:
                        return text

                # PrvText 없으면 BodyText 스트림 시도
                for entry in ole.listdir():
                    if 'bodytext' in '/'.join(entry).lower():
                        try:
                            raw = ole.openstream(entry).read()
                            # HWP BodyText는 압축된 binary — 텍스트 패턴만 추출
                            text = self._extract_korean_from_binary(raw)
                            if len(text) > 30:
                                return text
                        except Exception:
                            continue

        except ImportError:
            print("    ⚠️  olefile 미설치: pip install olefile")
        except Exception:
            pass
        return ''

    def _extract_hwpx(self, data: bytes) -> str:
        """HWPX → 텍스트 (ZIP + XML 구조)"""
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                texts = []
                for name in z.namelist():
                    # 본문 XML 파일 탐색
                    if 'content' in name.lower() and name.endswith('.xml'):
                        try:
                            xml_bytes = z.read(name)
                            root = ET.fromstring(xml_bytes)
                            # 모든 텍스트 노드 추출
                            parts = [
                                t.strip()
                                for t in root.itertext()
                                if t.strip()
                            ]
                            texts.append(' '.join(parts))
                        except Exception:
                            continue

                combined = '\n'.join(texts)
                return re.sub(r'\s+', ' ', combined).strip()
        except Exception:
            pass
        return ''

    def _extract_korean_from_binary(self, data: bytes) -> str:
        """바이너리에서 한글 텍스트 패턴 추출 (HWP BodyText 등 압축 스트림 fallback)"""
        try:
            # UTF-16LE로 디코딩 후 한글/ASCII 문자만 추출
            text = data.decode('utf-16-le', errors='ignore')
            # 한글 + 영문 + 숫자 + 기본 기호만 남김
            cleaned = re.sub(r'[^\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F\w\s\.,\(\)\[\]%:-]', ' ', text)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            return cleaned
        except Exception:
            return ''

    # ===========================
    # 유틸리티
    # ===========================

    @staticmethod
    def _find_by_attr(soup: BeautifulSoup, attr: str, pattern: re.Pattern):
        for tag in soup.find_all(True):
            val = tag.get(attr, '')
            val_str = ' '.join(val) if isinstance(val, list) else str(val)
            if pattern.search(val_str):
                return tag
        return None
