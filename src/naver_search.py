"""
네이버 검색 API 모듈
Two-Track 검색 (VIP 기관 + 광역 키워드) 수행
Updated: Real-time logging added
"""

import requests
from typing import List, Dict, Any
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import (
    get_config, DEFAULT_JOB_KEYWORDS,
    SEARCH_DAYS_LIMIT, NAVER_DISPLAY_COUNT,
    NAVER_ENDPOINTS, GRADE_DISPLAY_MAP, G2B_KEYWORDS
)


class NaverSearcher:
    """네이버 검색 API 래퍼 클래스"""
    
    def __init__(self):
        """API 키 초기화"""
        self.config = get_config()
        self.client_id = self.config['naver_client_id']
        self.client_secret = self.config['naver_client_secret']
        
        if not self.client_id or not self.client_secret:
            raise ValueError("네이버 API 키가 설정되지 않음. Secrets을 확인하세요.")
    
    def search(self, query: str, display: int = NAVER_DISPLAY_COUNT, search_type: str = 'webkr') -> List[Dict[str, Any]]:
        """
        네이버 검색 API 호출

        Args:
            query: 검색 쿼리
            display: 결과 수 (최대 100)
            search_type: 'webkr' | 'blog' | 'news'

        Returns:
            검색 결과 리스트 [{'title': '...', 'link': '...', 'description': '...', 'pubDate': '...'}, ...]
        """
        url = NAVER_ENDPOINTS.get(search_type, NAVER_ENDPOINTS['webkr'])

        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }

        params = {
            "query": query,
            "display": display,
            "sort": "date"  # 최신순
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            items = data.get('items', [])

            print(f"📡 네이버 {search_type} 검색: '{query}' → {len(items)}건")

            # HTML 태그 제거 및 검색어 추가
            for item in items:
                item['title'] = self._clean_html(item.get('title', ''))
                item['description'] = self._clean_html(item.get('description', ''))
                item['search_query'] = query  # 검색어 추가
                item['search_type'] = search_type  # 검색 유형 추가

            return items

        except requests.exceptions.RequestException as e:
            print(f"❌ 네이버 {search_type} 검색 실패: {e}")
            return []
    
    def _clean_html(self, text: str) -> str:
        """
        HTML 태그 제거 (<b>, </b> 등)
        
        Args:
            text: 원본 텍스트
        
        Returns:
            정제된 텍스트
        """
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text()
    
    def filter_by_date(self, items: List[Dict[str, Any]], days: int = SEARCH_DAYS_LIMIT) -> List[Dict[str, Any]]:
        """
        14일 이내 게시물만 필터링
        
        Args:
            items: 검색 결과 리스트
            days: 일수 제한 (기본 14일)
        
        Returns:
            필터링된 결과 리스트
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered = []
        
        for item in items:
            pub_date_str = item.get('pubDate', '')
            
            if not pub_date_str:
                # webkr.json은 pubDate를 반환하지 않음 - 통과시킴
                filtered.append(item)
                continue
            
            try:
                # 네이버 API 날짜 형식: "Mon, 03 Feb 2026 12:34:56 +0900"
                pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %z')
                
                # Timezone 제거 후 비교
                if pub_date.replace(tzinfo=None) >= cutoff_date:
                    filtered.append(item)
                    
            except ValueError:
                # 파싱 실패 시 포함 (안전하게)
                filtered.append(item)
        
        print(f"📅 날짜 필터링: {len(items)}건 → {len(filtered)}건 (최근 {days}일)")
        return filtered
    
    # ===========================
    # Track A: VIP 기관 검색
    # ===========================
    
    def search_track_a(self, organizations: List[Dict[str, Any]], callback=None) -> List[Dict[str, Any]]:
        """
        Track A: VIP 타겟 기관 정밀 감시 (webkr + blog 2가지 검색)
        기관의 grade에 따라 검색 결과 수 차별화 (A: 20건, B: 10건, C: 5건)

        Args:
            organizations: Config Sheet에서 로드한 기관 리스트
            callback: 진행 상황 업데이트용 콜백 함수 (optional)

        Returns:
            검색 결과 리스트 (source='track_a' 태그 추가됨)
        """
        all_results = []
        # Track A는 webkr + blog 2가지 검색 (뉴스는 공고보다 보도 기사가 많아 노이즈)
        search_types = ['webkr', 'blog']

        for idx, org in enumerate(organizations):
            org_name = org['organization']
            org_keywords = org.get('keywords', '').split(',')  # 쉼표로 구분된 키워드
            grade = str(org.get('grade', 'B')).strip().upper() or 'B'
            display = GRADE_DISPLAY_MAP.get(grade, 10)

            # 기관의 설정된 키워드와 조합하여 검색
            for kw in org_keywords:
                kw = kw.strip()
                if not kw:
                    continue

                if callback:
                    callback(f"🔎 [Track A/{grade}] 검색 중 ({idx+1}/{len(organizations)}): {org_name} - {kw}")
                else:
                    print(f"🔎 [Track A/{grade}] 검색 중: {org_name} - {kw}")

                # webkr + blog 각각 검색
                for stype in search_types:
                    query = f"{org_name} {kw}"
                    results = self.search(query, display=display, search_type=stype)

                    for item in results:
                        item['source'] = 'track_a'
                        item['search_keyword'] = kw
                        item['organization_hint'] = org_name
                        item['org_grade'] = grade
                        all_results.append(item)

                    # API Rate Limiting (초당 10건 제한 준수)
                    time.sleep(0.2)

        # 중복 제거 (URL 기준)
        unique_results = self._deduplicate_by_url(all_results)

        # 14일 필터링
        filtered_results = self.filter_by_date(unique_results)

        print(f"✅ Track A 완료: {len(filtered_results)}건 (총 {len(organizations)}개 기관, webkr+blog)")

        return filtered_results
    
    # ===========================
    # Track B: 광역 키워드 검색
    # ===========================
    
    def search_track_b(self, keywords: List[str] = None, callback=None) -> List[Dict[str, Any]]:
        """
        Track B: 신규 기관 광역 발굴 (webkr + blog + news 3가지 검색)

        Args:
            keywords: 직무 키워드 리스트 (None이면 기본값 사용)
            callback: 진행 상황 업데이트용 콜백 함수 (optional)

        Returns:
            검색 결과 리스트 (source='track_b' 태그 추가됨)
        """
        if keywords is None:
            keywords = DEFAULT_JOB_KEYWORDS

        all_results = []
        # Track B는 webkr + blog 검색 (news는 기사/보도자료 노이즈가 심해 제외)
        search_types = ['webkr', 'blog']

        for idx, keyword in enumerate(keywords):
            if callback:
                callback(f"🌍 [Track B] 광역 검색 중 ({idx+1}/{len(keywords)}): {keyword}")
            else:
                print(f"🌍 [Track B] 광역 검색 중: {keyword}")

            for stype in search_types:
                results = self.search(keyword, display=15, search_type=stype)

                for item in results:
                    item['source'] = 'track_b'
                    item['search_keyword'] = keyword
                    item['keyword_used'] = keyword
                    all_results.append(item)

                # API Rate Limiting
                time.sleep(0.2)

        # 중복 제거
        unique_results = self._deduplicate_by_url(all_results)

        # 14일 필터링
        filtered_results = self.filter_by_date(unique_results)

        print(f"✅ Track B 완료: {len(filtered_results)}건 (총 {len(keywords)}개 키워드, webkr+blog)")

        return filtered_results
    
    # ===========================
    # 통합 검색
    # ===========================
    
    def search_all(self, organizations: List[Dict[str, Any]], callback=None) -> List[Dict[str, Any]]:
        """
        Track A + Track B + Track C(나라장터, optional) 통합 검색

        Args:
            organizations: Config Sheet 기관 리스트
            callback: 진행 상황 업데이트용 콜백 함수 (optional)

        Returns:
            통합 검색 결과
        """
        if callback:
            callback("🔍 Multi-Track 검색 시작...")
        else:
            print("🔍 Multi-Track 검색 시작...")
            print("-" * 50)

        # Track A + Track B 병렬 실행 (각 트랙은 내부적으로 순차 실행)
        # Naver API 10 req/sec 제한: 각 트랙이 0.2s sleep → 합산 ~10 req/sec 유지
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(self.search_track_a, organizations, callback)
            future_b = executor.submit(self.search_track_b, None, callback)
            track_a_results = future_a.result()
            track_b_results = future_b.result()

        # Track C (나라장터 API, API 키 없으면 자동 skip)
        track_c_results = []
        try:
            from .g2b_search import G2BSearcher
            g2b = G2BSearcher()
            if g2b.enabled:
                if callback:
                    callback("🏛️ [Track C] 나라장터 검색 중...")
                else:
                    print("🏛️ [Track C] 나라장터 검색 중...")
                track_c_results = g2b.search_multiple(G2B_KEYWORDS)
                print(f"✅ Track C 완료: {len(track_c_results)}건")
        except Exception as e:
            print(f"⚠️ Track C (나라장터) 오류 (검색 계속 진행): {e}")

        # 합치기 및 중복 제거
        all_results = track_a_results + track_b_results + track_c_results
        unique_results = self._deduplicate_by_url(all_results)

        print("-" * 50)
        print(
            f"🎯 통합 검색 완료: 총 {len(unique_results)}건 "
            f"(Track A: {len(track_a_results)}, Track B: {len(track_b_results)}, Track C: {len(track_c_results)})"
        )

        return unique_results
    
    # ===========================
    # 유틸리티
    # ===========================
    
    def _deduplicate_by_url(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        URL 기준 중복 제거 (첫 번째만 유지)
        
        Args:
            items: 검색 결과 리스트
        
        Returns:
            중복 제거된 리스트
        """
        seen_urls = set()
        unique_items = []
        
        for item in items:
            url = item.get('link', '')
            
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_items.append(item)
        
        return unique_items


# ===========================
# 독립 실행 (테스트용)
# ===========================

if __name__ == '__main__':
    print("네이버 검색 테스트")
    print("-" * 50)
    
    searcher = NaverSearcher()
    
    # Track B 테스트
    results = searcher.search_track_b(['노무고문'])
    
    print(f"\n결과 샘플 (최대 3건):")
    for item in results[:3]:
        print(f"\n제목: {item['title']}")
        print(f"링크: {item['link']}")
        print(f"설명: {item['description'][:100]}...")
