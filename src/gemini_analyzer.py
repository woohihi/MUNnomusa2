"""
Gemini AI 분석 모듈
공고 적합성 판별 및 데이터 추출
"""

import google.generativeai as genai
from typing import Dict, Any, Optional, List
import json
import time
from datetime import datetime

from .config import get_config, GEMINI_RATE_LIMIT_DELAY


class GeminiAnalyzer:
    """Gemini 2.0 Flash 분석 클래스"""
    
    def __init__(self):
        """API 키 초기화 및 모델 설정"""
        config = get_config()
        api_key = config['gemini_api_key']
        
        if not api_key:
            raise ValueError("Gemini API 키가 설정되지 않음. Secrets을 확인하세요.")
        
        genai.configure(api_key=api_key)
        
        # Gemini 2.0 Flash 모델 사용 (1.5 deprecated)
        # 사용 가능한 모델: gemini-2.0-flash, gemini-2.0-flash-lite, gemini-1.5-flash-latest
        model_names = ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-flash-latest']
        
        for model_name in model_names:
            try:
                self.model = genai.GenerativeModel(model_name)
                print(f"✅ Gemini {model_name} 모델 초기화 완료")
                break
            except Exception as e:
                print(f"⚠️ {model_name} 초기화 실패: {e}")
                continue
        else:
            raise ValueError("사용 가능한 Gemini 모델이 없습니다.")
    

    def analyze(self, item: Dict[str, Any], callback=None) -> Optional[Dict[str, Any]]:
        """
        Gemini를 사용하여 공고 분석 (429 Quota Exceeded 재시도 로직 포함)
        
        Args:
            item: 공고 정보 딕셔너리
            callback: 상태 업데이트용 콜백 함수
            
        Returns:
            분석 결과 딕셔너리 또는 None
        """
        title = item.get('title', '')
        description = item.get('description', '')
        url = item.get('link', '')
        
        # 빈 본문 체크
        is_empty_body = self._is_empty_description(description)
        
        # 프롬프트 생성
        prompt = self._build_prompt(title, description, is_empty_body)
        
        max_retries = 3
        
        # 기본 딜레이 (4초)
        time.sleep(GEMINI_RATE_LIMIT_DELAY)
        
        base_delay = 10  # 429 발생 시 기본 대기 시간 (초)

        for attempt in range(max_retries + 1):
            try:
                # API 호출
                response = self.model.generate_content(prompt)
                
                # JSON 파싱
                result = self._parse_response(response.text)
                
                # 적합하지 않으면 None 반환
                if not result or not result.get('is_relevant'):
                    return None
                
                # URL 추가
                result['url'] = url
                result['original_title'] = title
                
                return result
                
            except Exception as e:
                error_msg = str(e)
                print(f"🐞 예외 타입: {type(e)}") # 디버깅용
                print(f"📄 예외 메시지: {error_msg[:100]}...")
                
                # 429 Quota Exceeded 또는 503 Service Unavailable 처리
                if "429" in error_msg or "quota" in error_msg.lower() or "resource exhausted" in error_msg.lower() or "503" in error_msg:
                    if attempt < max_retries:
                        wait_time = base_delay * (2 ** attempt)  # 10s, 20s, 40s
                        msg = f"⏳ Quota 초과 (429/503). {wait_time}초 대기 중... ({attempt + 1}/{max_retries})"
                        print(msg)
                        
                        # 사용자에게 대기 상태 알림 (카운트다운)
                        for remaining in range(wait_time, 0, -1):
                            if callback:
                                callback(f"{msg[:-1]}, {remaining}s...)")
                            time.sleep(1)
                            
                        continue
                    else:
                        print(f"❌ Gemini 분석 실패 (최대 재시도 초과): {e}")
                        return None
                else:
                    print(f"❌ Gemini 분석 실패: {e}")
                    return None
    
    def analyze_batch(self, items: List[Dict[str, Any]], callback=None) -> List[Dict[str, Any]]:
        """
        여러 공고 배치 분석
        
        Args:
            items: 검색 결과 리스트
            callback: 진행 상황 업데이트용 콜백 함수 (optional)
        
        Returns:
            적합한 공고 리스트
        """
        if callback:
            callback(f"🤖 Gemini 분석 시작: {len(items)}건")
        else:
            print(f"🤖 Gemini 분석 시작: {len(items)}건")
            print("-" * 50)
        
        relevant_items = []
        self.rejected_items = []  # 거부된 항목 추적
        
        # 제목에 있으면 무조건 통과시키는 핵심 키워드
        must_pass_keywords = [
            '노무법인', '노무고문', '노무자문', '고문노무사', '자문노무사',
            '노무사위촉', '노무사선정', '노무사모집', '인사노무'
        ]
        
        # 현재 연도
        current_year = datetime.now().year
        
        for idx, item in enumerate(items, start=1):
            if callback:
                callback(f"🤖 분석 중... ({idx}/{len(items)}): {item.get('title', '')[:30]}...")
            else:
                print(f"분석 중... ({idx}/{len(items)})", end='\r')
            
            title = item.get('title', '')
            title_lower = title.lower()
            # 띄어쓰기 제거한 버전 (노무 고문 → 노무고문)
            title_no_space = title_lower.replace(' ', '')
            
            # 제목에 핵심 키워드가 있으면 Gemini 분석 없이 바로 통과
            if any(kw in title_no_space for kw in must_pass_keywords):
                # 제목에서 연도 추출 (4자리 또는 2자리)
                import re
                
                posting_year = None
                
                # 1. 4자리 연도 먼저 시도 (예: "2026년", "2025년도")
                year_match_4 = re.search(r'(20\d{2})년', title)
                if year_match_4:
                    posting_year = int(year_match_4.group(1))
                else:
                    # 2. 2자리 연도 시도 (예: "'23년", "23년도", "24년")
                    year_match_2 = re.search(r"['\"]?(\d{2})년", title)
                    if year_match_2:
                        short_year = int(year_match_2.group(1))
                        # 20XX로 변환 (21~29 → 2021~2029, 00~20 → 2000~2020)
                        posting_year = 2000 + short_year
                
                is_past = False
                if posting_year:
                    is_past = posting_year < current_year
                
                result = {
                    'is_relevant': True,
                    'url': item.get('link', ''),
                    'original_title': title,
                    'summary': f"⚡ 키워드 매칭 자동 통과 ({posting_year if posting_year else '연도 미상'}년)",
                    'deadline': f"{posting_year}-12-31" if posting_year and is_past else None,  # 과거 공고는 해당 연도 말로 설정
                    'term_months': None,
                    'start_date': None,
                    'is_past_announcement': is_past,  # 과거 공고 여부 표시
                    # 원본 데이터 유지
                    'search_keyword': item.get('search_keyword', ''),
                    'search_query': item.get('search_query', ''),
                    'source': item.get('source', '')
                }
                relevant_items.append(result)
                continue
            
            # 그 외는 Gemini 분석
            result = self.analyze(item, callback=callback)
            
            if result:
                # 원본 데이터 추가
                result['search_keyword'] = item.get('search_keyword', '')
                result['search_query'] = item.get('search_query', '')
                result['source'] = item.get('source', '')
                relevant_items.append(result)
            else:
                # 거부 사유 저장 (원본 데이터 포함)
                self.rejected_items.append({
                    'url': item.get('link', ''),
                    'title': item.get('title', ''),
                    'rejection_reason': 'AI 분석: 노무고문/자문위원 관련 공고 아님',
                    'search_keyword': item.get('search_keyword', ''),
                    'search_query': item.get('search_query', ''),
                    'source': item.get('source', '')
                })
        
        print()  # 줄바꿈
        print("-" * 50)
        print(f"✅ Gemini 분석 완료: {len(relevant_items)}건 적합 ({len(items) - len(relevant_items)}건 제외)")
        
        return relevant_items
    
    def get_rejected_items(self) -> List[Dict[str, Any]]:
        """
        AI가 거부한 항목 목록 반환
        
        Returns:
            거부된 항목 리스트 (rejection_reason 포함)
        """
        return getattr(self, 'rejected_items', [])
    
    # ===========================
    # 프롬프트 생성
    # ===========================
    
    def _build_prompt(self, title: str, description: str, is_empty_body: bool) -> str:
        """
        Gemini 프롬프트 생성
        
        Args:
            title: 공고 제목
            description: 공고 본문
            is_empty_body: 본문이 비어있는지 여부
        
        Returns:
            프롬프트 문자열
        """
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 빈 본문 경고 문구
        empty_warning = ""
        if is_empty_body:
            empty_warning = """
⚠️ 주의: 본문이 비어있거나 "붙임 참조" 등으로만 구성되어 있습니다.
이 경우 제목에 [노무, 고문, 자문, 위촉, 법률] 키워드가 명확하다면 무조건 is_relevant=true로 판정하고,
summary에 "⚠️ 첨부파일 확인 필요" 문구를 추가하세요.
"""
        
        prompt = f"""
당신은 공인노무사 채용 공고 분석 전문가입니다.
아래 공고가 공인노무사가 지원할 수 있는 직무인지 판별하고, 필요한 정보를 추출하세요.

오늘 날짜: {today}

{empty_warning}

<입력>
제목: {title}
본문: {description if description else "본문 없음 - 첨부파일 참조"}

<출력 형식>
반드시 아래 JSON 형식으로만 응답하세요. 추가 설명 없이 JSON만 출력하세요.

{{
  "is_relevant": true 또는 false,
  "summary": "간단한 요약 (1-2문장)",
  "deadline": "YYYY-MM-DD" 또는 null,
  "term_months": 24 또는 null,
  "start_date": "YYYY-MM-DD" 또는 null
}}

<판정 규칙>
1. **적합성 (is_relevant)**:
   - 공인노무사가 지원 가능한 직무인가? (노무고문, 노무자문, 법률자문, 인사위원, 평가위원, 노무사 위촉 등)
   - 제목이나 본문에 [노무사, 노무고문, 노무자문, 위촉, 법률고문, 인사노무] 키워드가 있으면 true
   - 본문이 없어도 제목에 관련 키워드가 있으면 true
   - 마감일 정보가 없거나 불명확해도 관련 공고면 true (마감일은 별도 확인 가능)
   - **중요: 마감일이 이미 지났더라도 노무 관련 공고면 무조건 is_relevant=true로 판정**
   - **과거 공고도 '과거 자료'로 Archive에 기록되므로 마감 여부와 관계없이 적합성만 판단**
   - **제외 대상 (is_relevant=false)**:
     - 단순 뉴스 기사, 보도자료, 인터뷰 (채용 공고가 아님)
     - 노무법인/법률사무소의 자체 홍보글, 광고, 블로그 마케팅
     - "합격 자기소개서", "면접 후기", "취업 팁", "강의 홍보"
     - 특정 사건 수임 홍보 ("XX사건 승소 사례" 등)
     - 단순 용역 입찰 (청소, 경비, 시설관리 등)
     - 노무사가 아닌 일반 직원(사무직, 경리 등) 채용 공고
   - 단, 명백히 관련 없는 공고 (채용 아닌 일반 뉴스, 상품 광고 등)만 false

2. **요약 (summary)**:
   - 공고의 핵심 내용을 1-2문장으로 간결하게 요약
   - 본문이 없고 제목만으로 판정한 경우 "⚠️ 첨부파일 확인 필요" 문구 추가

3. **마감일 (deadline)**:
   - 지원 마감일을 "YYYY-MM-DD" 형식으로 추출
   - 정보가 없으면 null

4. **임기 (term_months)**:
   - 위촉 기간/임기를 개월 단위 숫자로 추출
   - 예: "2년" → 24, "1년 6개월" → 18
   - 정보가 없으면 null

5. **시작일 (start_date)**:
   - 위촉 시작일을 "YYYY-MM-DD" 형식으로 추출
   - 정보가 없으면 null

이제 분석을 시작하세요.
"""
        
        return prompt
    
    def _is_empty_description(self, description: str) -> bool:
        """
        본문이 비어있는지 확인
        
        Args:
            description: 본문 텍스트
        
        Returns:
            비어있으면 True
        """
        if not description:
            return True
        
        # 짧은 본문 (30자 이하)
        if len(description.strip()) < 30:
            return True
        
        # "붙임 참조", "첨부파일 참조" 등 키워드만 있음
        empty_keywords = ['붙임', '첨부', '참조', '별첨', '파일']
        
        if any(kw in description for kw in empty_keywords) and len(description) < 50:
            return True
        
        return False
    
    def _parse_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Gemini 응답 JSON 파싱
        
        Args:
            response_text: Gemini 응답 텍스트
        
        Returns:
            파싱된 딕셔너리 또는 None
        """
        try:
            # 코드 블록 제거 (```json ... ```)
            cleaned = response_text.strip()
            
            if cleaned.startswith('```'):
                # ```json\n{...}\n``` 형태
                lines = cleaned.split('\n')
                cleaned = '\n'.join(lines[1:-1])
            
            # JSON 파싱
            data = json.loads(cleaned)
            
            return data
            
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON 파싱 실패: {e}")
            print(f"응답 텍스트: {response_text[:200]}...")
            return None


# ===========================
# 독립 실행 (테스트용)
# ===========================

if __name__ == '__main__':
    from typing import List
    
    print("Gemini 분석기 테스트")
    print("-" * 50)
    
    analyzer = GeminiAnalyzer()
    
    # 테스트 케이스
    test_items = [
        {
            'title': '한국환경공단 노무자문위원 위촉 공고',
            'description': '2년 임기의 노무자문위원을 모집합니다. 마감: 2026-02-20',
            'link': 'http://example.com/1'
        },
        {
            'title': '제5기 자문위원 위촉',
            'description': '붙임 참조',  # 빈 본문 테스트
            'link': 'http://example.com/2'
        }
    ]
    
    results = analyzer.analyze_batch(test_items)
    
    print(f"\n분석 결과 ({len(results)}건):")
    for r in results:
        print(f"\n제목: {r['original_title']}")
        print(f"요약: {r['summary']}")
        print(f"마감: {r.get('deadline', 'N/A')}")
