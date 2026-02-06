"""
전처리 모듈
AI 호출 전 노이즈 제거 (비용 절감 핵심)
"""

from typing import List, Dict, Any

from .config import VALID_KEYWORDS, NEGATIVE_KEYWORDS


class Preprocessor:
    """비용 절감 전처리 클래스"""
    
    def __init__(self, existing_urls: List[str], excluded_urls: List[str] = None):
        """
        Args:
            existing_urls: DB에 이미 존재하는 URL 리스트 (Results + Archive)
            excluded_urls: 제외 목록 URL 리스트 (Excluded Sheet)
        """
        # 기존 URL과 제외 URL 모두 합쳐서 필터링
        self.existing_urls = set(existing_urls)
        if excluded_urls:
            self.existing_urls.update(excluded_urls)
        
        self.stats = {
            'total': 0,
            'duplicates': 0,
            'keyword_failed': 0,
            'negative_filtered': 0,
            'passed': 0
        }
        
        # 필터링된 항목 추적
        self.filtered_items = []
    
    def process(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        3단계 전처리 파이프라인
        
        Args:
            items: 네이버 검색 결과 리스트
        
        Returns:
            AI 분석 대상 후보 리스트
        """
        self.stats['total'] = len(items)
        
        print(f"🔧 전처리 시작: {len(items)}건")
        print("-" * 50)
        
        # Step 1: 중복 제거
        step1 = self._remove_duplicates(items)
        print(f"Step 1 - 중복 제거: {len(items)}건 → {len(step1)}건")
        
        # Step 2: 키워드 검증 (Track A만)
        step2 = self._validate_keywords(step1)
        print(f"Step 2 - 키워드 검증: {len(step1)}건 → {len(step2)}건")
        
        # Step 3: 네거티브 필터
        step3 = self._filter_negative(step2)
        print(f"Step 3 - 네거티브 필터: {len(step2)}건 → {len(step3)}건")
        
        self.stats['passed'] = len(step3)
        
        print("-" * 50)
        print(f"✅ 전처리 완료: {self.stats['passed']}건 통과 (필터링률: {self._get_filter_rate():.1f}%)")
        
        return step3
    
    # ===========================
    # Step 1: 중복 제거
    # ===========================
    
    def _remove_duplicates(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        DB에 이미 존재하는 URL 제거
        
        Args:
            items: 검색 결과 리스트
        
        Returns:
            신규 URL만 포함된 리스트
        """
        new_items = []
        
        for item in items:
            url = item.get('link', '')
            
            if url and url not in self.existing_urls:
                new_items.append(item)
            else:
                self.stats['duplicates'] += 1
                self.filtered_items.append({
                    **item,
                    'filter_reason': '중복 URL (이미 DB에 존재)'
                })
        
        return new_items
    
    # ===========================
    # Step 2: 키워드 검증
    # ===========================
    
    def _validate_keywords(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Track A 결과에 대해 유효 키워드 검증
        Track B는 이미 키워드로 검색했으므로 통과
        
        Args:
            items: Step 1 통과 리스트
        
        Returns:
            키워드 검증 통과 리스트
        """
        validated = []
        
        for item in items:
            # Track B는 무조건 통과
            if item.get('source') == 'track_b':
                validated.append(item)
                continue
            
            # Track A: 제목 + 설명에 유효 키워드 포함 확인
            title = item.get('title', '').lower()
            description = item.get('description', '').lower()
            combined_text = title + ' ' + description
            
            has_valid_keyword = any(
                kw in combined_text 
                for kw in VALID_KEYWORDS
            )
            
            if has_valid_keyword:
                validated.append(item)
            else:
                self.stats['keyword_failed'] += 1
                self.filtered_items.append({
                    **item,
                    'filter_reason': 'Track A 키워드 미포함 (노무/법률/고문/자문/위원 등)'
                })
        
        return validated
    
    # ===========================
    # Step 3: 네거티브 필터
    # ===========================
    
    def _filter_negative(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        제목에 무관 키워드 포함 시 제거
        
        Args:
            items: Step 2 통과 리스트
        
        Returns:
            네거티브 필터 통과 리스트
        """
        filtered = []
        
        for item in items:
            title = item.get('title', '').lower()
            
            has_negative = any(
                neg in title
                for neg in NEGATIVE_KEYWORDS
            )
            
            if not has_negative:
                filtered.append(item)
            else:
                self.stats['negative_filtered'] += 1
                matched_neg = [neg for neg in NEGATIVE_KEYWORDS if neg in title]
                self.filtered_items.append({
                    **item,
                    'filter_reason': f'네거티브 키워드 포함: {matched_neg}'
                })
        
        return filtered
    
    # ===========================
    # 통계
    # ===========================
    
    def _get_filter_rate(self) -> float:
        """필터링률 계산 (%))"""
        if self.stats['total'] == 0:
            return 0.0
        
        filtered_count = self.stats['total'] - self.stats['passed']
        return (filtered_count / self.stats['total']) * 100
    
    def get_stats(self) -> Dict[str, Any]:
        """
        전처리 통계 반환
        
        Returns:
            {'total': ..., 'duplicates': ..., 'passed': ..., etc}
        """
        return {
            **self.stats,
            'filter_rate': self._get_filter_rate()
        }
    
    def get_filtered_items(self) -> List[Dict[str, Any]]:
        """
        필터링된 항목 목록 반환
        
        Returns:
            필터링된 항목 리스트 (filter_reason 포함)
        """
        return self.filtered_items


# ===========================
# 독립 실행 (테스트용)
# ===========================

if __name__ == '__main__':
    print("전처리 모듈 테스트")
    print("-" * 50)
    
    # 더미 데이터
    test_items = [
        {
            'title': '한국환경공단 노무고문 위촉 공고',
            'link': 'http://example.com/1',
            'description': '2년 임기 자문위원 모집',
            'source': 'track_a'
        },
        {
            'title': '아파트 청소 용역 입찰',
            'link': 'http://example.com/2',
            'description': '청소 용역 업체 모집',
            'source': 'track_a'
        },
        {
            'title': '법률자문위원 위촉',
            'link': 'http://example.com/3',
            'description': '전문가 모집',
            'source': 'track_b'
        }
    ]
    
    # 기존 URL (중복 테스트)
    existing = ['http://example.com/3']
    
    preprocessor = Preprocessor(existing)
    result = preprocessor.process(test_items)
    
    print(f"\n통계: {preprocessor.get_stats()}")
    print(f"\n통과 항목 ({len(result)}건):")
    for item in result:
        print(f"  - {item['title']}")
