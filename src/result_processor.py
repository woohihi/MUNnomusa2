from datetime import datetime, date
from typing import List, Dict, Any


def _calculate_priority(item: Dict, deadline_str: str, is_expired: bool) -> str:
    """
    Pending 시트용 우선순위 산정.

    Returns:
        '긴급' | '일반' | '자동통과' | '기한미정' | '과거참고' | '분석실패'
    """
    summary = item.get('summary', '')

    if '[분석 실패]' in summary:
        return '분석실패'

    if is_expired:
        return '과거참고'

    is_auto = '키워드 매칭 자동 통과' in summary

    if not deadline_str:
        return '자동통과' if is_auto else '기한미정'

    try:
        diff = (datetime.strptime(deadline_str, '%Y-%m-%d').date() - date.today()).days
        if diff <= 7:
            return '긴급'
        return '자동통과' if is_auto else '일반'
    except (ValueError, TypeError):
        return '기한미정'


class ResultProcessor:
    """
    Gemini 분석 결과를 시트 저장용 포맷으로 변환하고 
    자동 분류(Results vs Archive)를 수행하는 공통 로직 클래스
    """
    
    @staticmethod
    def process_results(analyzed_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Gemini 분석 결과 리스트를 받아서Pending 시트용 레코드 포맷으로 변환합니다.
        
        Args:
            analyzed_results: GeminiAnalyzer.analyze_batch()의 반환값
            
        Returns:
            Pending 시트에 저장할 레코드 리스트 (suggested_target 포함)
        """
        today = datetime.now().date()
        processed_records = []

        for item in analyzed_results:
            deadline_str = item.get('deadline', '')
            is_expired = False
            summary = item.get('summary', '')
            
            # 1. 과거 공고 플래그 확인 (Quick Reject 또는 키워드 통과 시 설정됨)
            if item.get('is_past_announcement', False):
                is_expired = True
                # 요약에 명시 (중복 추가 방지)
                if '과거 공고' not in summary:
                    summary = f"📉 [과거 공고] {deadline_str if deadline_str else ''} 마감 (자동 분류). " + summary

            # 2. 마감일 날짜 비교
            elif deadline_str:
                try:
                    deadline_date = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                    if deadline_date < today:
                        is_expired = True
                except (ValueError, TypeError):
                    # 날짜 형식이 아니면 넘어감
                    pass
            
            # 3. 기관명 추출 로직 (Track A Hint → search_keyword → URL 도메인)
            org_hint = (
                item.get('organization_hint', '')
                or item.get('search_keyword', '')
                or ''
            )
            if not org_hint:
                if item.get('url'):
                    try:
                        org_hint = item['url'].split('/')[2]
                    except IndexError:
                        org_hint = 'Unknown'
                else:
                    org_hint = 'Unknown'

            # 4. 레코드 생성
            priority = _calculate_priority(item, deadline_str, is_expired)
            record = {
                'url': item.get('url', ''),
                'title': item.get('original_title', '') or item.get('title', ''),
                'organization': org_hint,
                'deadline': deadline_str,
                'summary': summary.strip(),
                'collected_date': datetime.now().strftime('%Y-%m-%d'),
                'suggested_target': 'Archive' if is_expired else 'Results',
                'source': item.get('source', ''),
                'search_keyword': item.get('search_keyword', ''),
                'search_query': item.get('search_query', ''),
                'status': '검토중',
                'priority': priority,
            }
            
            processed_records.append(record)
            
        return processed_records
