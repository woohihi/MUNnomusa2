"""
전처리 모듈
AI 호출 전 노이즈 제거 (비용 절감 핵심)
"""

from typing import List, Dict, Any

from .config import VALID_KEYWORDS, NEGATIVE_KEYWORDS, SCORE_HIGH_THRESHOLD, SCORE_SKIP_THRESHOLD


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
            'score_skipped': 0,
            'score_high': 0,
            'score_normal': 0,
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

        # Step 4: 점수 기반 필터 (Gemini 비용 절감)
        step4 = self._filter_by_score(step3)
        self.stats['passed'] = len(step4)
        print(
            f"Step 4 - 점수 필터: {len(step3)}건 → {len(step4)}건 "
            f"(HIGH: {self.stats['score_high']}, NORMAL: {self.stats['score_normal']}, "
            f"SKIP: {self.stats['score_skipped']})"
        )

        print("-" * 50)
        print(f"✅ 전처리 완료: {self.stats['passed']}건 통과 (필터링률: {self._get_filter_rate():.1f}%)")

        return step4
    
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
    # Step 4: 점수 기반 필터
    # ===========================

    # 핵심 키워드 (제목+설명에 있으면 높은 점수)
    _HIGH_SCORE_KEYWORDS = [
        '노무고문', '고문노무사', '자문노무사', '노무자문',
        '노무사위촉', '노무사선정', '노무사모집', '인사노무자문'
    ]
    _MED_SCORE_KEYWORDS = ['노무', '고문', '자문', '위촉']
    _ANNOUNCEMENT_SIGNALS = ['모집', '위촉', '공고', '선정', '안내']

    def _calculate_score(self, item: Dict[str, Any]) -> int:
        """
        규칙 기반 점수 산정 (0~100)

        - 출처 점수 (max 30): 공공기관 도메인(.go.kr/.or.kr) 여부
        - 핵심 키워드 점수 (max 40): 노무고문/자문 등 핵심 키워드
        - 공고 신호 점수 (max 20): 제목에 모집/위촉/공고 등 포함
        - 검색 출처 보정 (max 10): Track B/C는 이미 키워드로 검색됨
        """
        score = 0
        title = item.get('title', '')
        description = item.get('description', '')
        url = item.get('link', '')
        text = title + ' ' + description

        # 출처 점수 (max 30)
        if '.go.kr' in url or '.or.kr' in url:
            score += 30
        elif item.get('source') == 'track_a':
            score += 15  # 기관 직접 검색이므로 중간 점수

        # 핵심 키워드 점수 (max 40)
        if any(kw in text for kw in self._HIGH_SCORE_KEYWORDS):
            score += 40
        elif any(kw in text for kw in self._MED_SCORE_KEYWORDS):
            score += 20

        # 공고 신호 점수 (max 20)
        if any(sig in title for sig in self._ANNOUNCEMENT_SIGNALS):
            score += 20

        # Track B/C 보정 (이미 키워드로 검색됨)
        if item.get('source') in ('track_b', 'track_c'):
            score += 10

        return min(score, 100)

    def _filter_by_score(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        점수 기반 필터 — SCORE_SKIP_THRESHOLD 미만 항목 스킵

        각 항목에 'score'와 'score_priority' 필드를 추가
        (SearchLog 기록 및 Gemini 우선순위 참고용)
        """
        passed = []

        for item in items:
            score = self._calculate_score(item)
            item['score'] = score

            if score >= SCORE_HIGH_THRESHOLD:
                item['score_priority'] = 'HIGH'
                self.stats['score_high'] += 1
                passed.append(item)
            elif score >= SCORE_SKIP_THRESHOLD:
                item['score_priority'] = 'NORMAL'
                self.stats['score_normal'] += 1
                passed.append(item)
            else:
                self.stats['score_skipped'] += 1
                self.filtered_items.append({
                    **item,
                    'filter_reason': f'점수 미달 스킵 (score={score}, threshold={SCORE_SKIP_THRESHOLD})'
                })

        return passed

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
