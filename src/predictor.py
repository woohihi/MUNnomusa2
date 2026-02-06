"""
예측 시스템 모듈
과거 데이터 기반 다음 공고 시기 예측 (CRM)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd

from .config import PREDICTION_ALERT_DAYS


class Predictor:
    """잠재 공고 예측 클래스"""
    
    def __init__(self, archive_df: pd.DataFrame):
        """
        Args:
            archive_df: Archive Sheet 데이터 (DataFrame)
        """
        self.archive_df = archive_df
    
    def calculate_opportunities(self) -> List[Dict[str, Any]]:
        """
        D-30 이내 예상 공고 계산
        
        Returns:
            예측 리스트 [{'organization': '...', 'next_expected_date': '...', 'd_day': ..., 'message': '...'}, ...]
        """
        if self.archive_df.empty:
            print("📭 Archive 데이터 없음. 예측 불가")
            return []
        
        today = datetime.now().date()
        predictions = []
        
        for idx, row in self.archive_df.iterrows():
            term_months = row.get('term_months', '')
            start_date_str = row.get('start_date', '')
            organization = row.get('organization', 'Unknown')
            
            # 필수 데이터 존재 확인
            if not term_months or not start_date_str:
                continue
            
            try:
                # term_months를 숫자로 변환
                term = self._parse_term_months(term_months)
                
                if term is None:
                    continue
                
                # start_date 파싱
                start_date = datetime.strptime(str(start_date_str), '%Y-%m-%d').date()
                
                # 다음 예상 공고일 = 시작일 + 임기
                next_date = start_date + timedelta(days=term * 30)
                
                # D-day 계산
                days_until = (next_date - today).days
                
                # D-30 이내만 포함
                if 0 < days_until <= PREDICTION_ALERT_DAYS:
                    predictions.append({
                        'organization': organization,
                        'next_expected_date': next_date.strftime('%Y-%m-%d'),
                        'd_day': days_until,
                        'term_months': term,
                        'message': f"{organization}의 자문위원 임기 만료 예상 (D-{days_until})"
                    })
                    
            except (ValueError, TypeError) as e:
                # 날짜 파싱 실패 시 스킵
                continue
        
        # D-day 오름차순 정렬
        predictions.sort(key=lambda x: x['d_day'])
        
        print(f"🎯 예측 완료: {len(predictions)}개 기관 임박")
        
        return predictions
    
    def _parse_term_months(self, term: Any) -> Optional[int]:
        """
        임기를 개월 단위 숫자로 변환
        
        Args:
            term: 임기 (숫자 또는 문자열)
        
        Returns:
            개월 수 (정수) 또는 None
        """
        if isinstance(term, (int, float)):
            return int(term)
        
        if isinstance(term, str):
            try:
                return int(term)
            except ValueError:
                return None
        
        return None
    
    def get_alert_count(self) -> int:
        """
        예측 알림 대상 개수
        
        Returns:
            D-30 이내 기관 수
        """
        opportunities = self.calculate_opportunities()
        return len(opportunities)


# ===========================
# 독립 실행 (테스트용)
# ===========================

if __name__ == '__main__':
    from typing import Optional
    
    print("예측 시스템 테스트")
    print("-" * 50)
    
    # 더미 Archive 데이터
    test_data = pd.DataFrame([
        {
            'organization': '한국환경공단',
            'url': 'http://example.com/1',
            'title': '노무자문위원 위촉',
            'deadline': '2024-02-20',
            'summary': '2년 임기',
            'collected_date': '2024-02-01',
            'term_months': 24,
            'start_date': '2024-02-01',
            'next_expected_date': ''
        },
        {
            'organization': '인천항만공사',
            'url': 'http://example.com/2',
            'title': '법률고문 위촉',
            'deadline': '2025-06-30',
            'summary': '1년 임기',
            'collected_date': '2025-06-15',
            'term_months': 12,
            'start_date': '2025-07-01',
            'next_expected_date': ''
        }
    ])
    
    predictor = Predictor(test_data)
    opportunities = predictor.calculate_opportunities()
    
    print(f"\n예측 결과 ({len(opportunities)}건):")
    for opp in opportunities:
        print(f"\n{opp['message']}")
        print(f"  예상 공고일: {opp['next_expected_date']}")
        print(f"  임기: {opp['term_months']}개월")
