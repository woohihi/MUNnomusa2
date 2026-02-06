"""
네이버 검색 API 모듈
Two-Track 검색 (VIP 기관 + 광역 키워드) 수행
"""

import requests
from typing import List, Dict, Any
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time

from .config import (
    get_config, DEFAULT_JOB_KEYWORDS, 
    SEARCH_DAYS_LIMIT, NAVER_DISPLAY_COUNT
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
    
    def search(self, query: str, display: int = NAVER_DISPLAY_COUNT) -> List[Dict[str, Any]]:
        """
        네이버 검색 API 호출
        
        Args:
            query: 검색 쿼리
            display: 결과 수 (최대 100)
        
        Returns:
            검색 결과 리스트 [{'title': '...', 'link': '...', 'description': '...', 'pubDate': '...'}, ...]
        """
        url = "https://openapi.naver.com/v1/search/webkr.json"
        
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
            
            print(f"📡 네이버 검색: '{query}' → {len(items)}건")
            
            # HTML 태그 제거 및 검색어 추가
            for item in items:
                item['title'] = self._clean_html(item.get('title', ''))
                item['description'] = self._clean_html(item.get('description', ''))
                item['search_query'] = query  # 검색어 추가
            
            return items
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 네이버 검색 실패: {e}")
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
    
    def search_track_a(self, organizations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Track A: VIP 타겟 기관 정밀 감시
        
        Args:
            organizations: Config Sheet에서 로드한 기관 리스트
        
        Returns:
            검색 결과 리스트 (source='track_a' 태그 추가됨)
        """
        all_results = []
        
        for org in organizations:
            org_name = org['organization']
            org_keywords = org.get('keywords', '').split(',')  # 쉼표로 구분된 키워드
            
            # 기관의 설정된 키워드와 조합하여 검색
            for kw in org_keywords:
                kw = kw.strip()
                if not kw:
                    continue
                    
                # 쿼리: {기관명} {키워드}
                query = f"{org_name} {kw}"
                results = self.search(query, display=10)
                
                # 메타데이터 추가
                for item in results:
                    item['source'] = 'track_a'
                    item['organization_hint'] = org_name
                    all_results.append(item)
                
                # API Rate Limiting (초당 10건 제한 준수)
                time.sleep(0.2)
        
        # 중복 제거 (URL 기준)
        unique_results = self._deduplicate_by_url(all_results)
        
        # 14일 필터링
        filtered_results = self.filter_by_date(unique_results)
        
        print(f"✅ Track A 완료: {len(filtered_results)}건 (총 {len(organizations)}개 기관)")
        
        return filtered_results
    
    # ===========================
    # Track B: 광역 키워드 검색
    # ===========================
    
    def search_track_b(self, keywords: List[str] = None) -> List[Dict[str, Any]]:
        """
        Track B: 신규 기관 광역 발굴
        
        Args:
            keywords: 직무 키워드 리스트 (None이면 기본값 사용)
        
        Returns:
            검색 결과 리스트 (source='track_b' 태그 추가됨)
        """
        if keywords is None:
            keywords = DEFAULT_JOB_KEYWORDS
        
        all_results = []
        
        for keyword in keywords:
            # 쿼리: {키워드} 그대로 검색
            query = keyword
            results = self.search(query, display=15)
            
            # 메타데이터 추가
            for item in results:
                item['source'] = 'track_b'
                item['keyword_used'] = keyword
                all_results.append(item)
            
            # API Rate Limiting
            time.sleep(0.2)
        
        # 중복 제거
        unique_results = self._deduplicate_by_url(all_results)
        
        # 14일 필터링
        filtered_results = self.filter_by_date(unique_results)
        
        print(f"✅ Track B 완료: {len(filtered_results)}건 (총 {len(keywords)}개 키워드)")
        
        return filtered_results
    
    # ===========================
    # 통합 검색
    # ===========================
    
    def search_all(self, organizations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Track A + Track B 통합 검색
        
        Args:
            organizations: Config Sheet 기관 리스트
        
        Returns:
            통합 검색 결과
        """
        print("🔍 Two-Track 검색 시작...")
        print("-" * 50)
        
        # Track A
        track_a_results = self.search_track_a(organizations)
        
        # Track B
        track_b_results = self.search_track_b()
        
        # 합치기 및 중복 제거
        all_results = track_a_results + track_b_results
        unique_results = self._deduplicate_by_url(all_results)
        
        print("-" * 50)
        print(f"🎯 통합 검색 완료: 총 {len(unique_results)}건 (Track A: {len(track_a_results)}, Track B: {len(track_b_results)})")
        
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
