"""
Gemini AI 분석 모듈
공고 적합성 판별 및 데이터 추출
"""

from google import genai
from google.genai import types
from typing import Dict, Any, Optional, List
import json
import re
import time
from datetime import datetime

from .config import get_config, GEMINI_RATE_LIMIT_DELAY


# ===========================
# 공인노무사 Agent 시스템 인스트럭션
# ===========================
_LABOR_EXPERT_INSTRUCTION = """
당신은 15년 경력의 공인노무사입니다.
노동법, 인사관리, 노사관계 분야 전문가로서, 공공기관과 기업에서
노무고문·자문위원 역할을 직접 수행해본 경험이 있습니다.

【당신의 임무】
주어진 공고가 공인노무사가 수임 가능한 노무 자문 계약인지 판별하고, 필요한 정보를 추출합니다.

【적합 (is_relevant = true) 조건 — 아래 중 하나 이상 해당해야 함】
- 제목 또는 본문에 다음 중 하나가 명시됨:
  "노무고문", "고문노무사", "자문노무사", "노무사 위촉", "노무사 선정",
  "노무 자문", "노무자문", "인사노무 자문", "노사관계 자문", "노무 고문"
- 위에 해당하지 않더라도, 공공기관이 노동법·인사·노사관계 분야 전문가를
  위촉 또는 고문 계약으로 선발하는 공고임이 본문에서 명확히 확인되는 경우

【반드시 제외 (is_relevant = false)】
- "위촉" 단독 사용 (노무 관련 명시 없음) → 감사위원, 환경위원, 문화위원 등 무관
- "법률고문" 단독 (법무·세무·회계 분야일 수 있음, 노무 명시 없으면 제외)
- "자문위원" 단독 (분야 불명확) → 노무/노동/인사 관련 명시 없으면 제외
- 단순 뉴스 기사, 보도자료, 인터뷰
- 노무법인·법률사무소 자체 홍보, 광고
- 합격 수기, 면접 후기, 강의 홍보
- 일반 직원 채용 (사무원, 연구원, 행정직 등)
- 용역 입찰 (청소, 경비, 시설관리, 건설, IT 등)
- 본문이 없고 제목에 적합 조건의 명확한 키워드가 없는 경우

【판단 원칙】
- 마감일이 지난 공고도 적합성 판단 대상 (과거 자료로 보관)
- **불명확하거나 애매한 경우 → is_relevant = false (확실한 것만 통과)**
- 본문 없이 제목만 있을 때는 위 【적합 조건】의 키워드가 제목에 직접 있어야만 true
"""


class GeminiAnalyzer:
    """Gemini 2.0 Flash 분석 클래스"""
    
    def __init__(self):
        """API 키 초기화 및 모델 설정"""
        config = get_config()
        api_key = config['gemini_api_key']
        
        if not api_key:
            raise ValueError("Gemini API 키가 설정되지 않음. Secrets을 확인하세요.")
        
        self.client = genai.Client(api_key=api_key)

        # 사용 가능한 모델 우선순위 (API 키에 따라 일부 모델 제한 가능)
        self._model_names = ['gemini-2.5-flash', 'gemini-2.0-flash']
        self.model_name = self._model_names[0]
        print(f"✅ Gemini {self.model_name} 모델 초기화 완료")
    

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
                # API 호출 (공인노무사 Agent 시스템 인스트럭션 적용)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=_LABOR_EXPERT_INSTRUCTION,
                    ),
                )
                
                # Safety 필터링 등으로 응답이 없을 수 있음
                response_text = None
                try:
                    response_text = response.text
                except (ValueError, AttributeError):
                    # Safety 필터 등에 의해 텍스트가 없는 경우
                    print(f"⚠️  Gemini 응답 텍스트 없음 (Safety 필터링 가능)")
                    return None
                
                if not response_text:
                    print(f"⚠️  Gemini 빈 응답")
                    return None
                
                # JSON 파싱
                result = self._parse_response(response_text)
                
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
                
                # [CRITICAL] 403 Permission Denied / API Key Leaked
                elif "403" in error_msg or "permissiondenied" in error_msg.lower() or "leaked" in error_msg.lower():
                    print("\n" + "="*60)
                    print("🚨 [CRITICAL ERROR] Gemini API 키가 차단되었습니다.")
                    print("이유: API Key가 유출(Leaked)되었거나 권한이 없습니다 (403).")
                    print("="*60 + "\n")
                    
                    # 분석 실패 표시 (상위 호출자에게 알림)
                    return {'critical_error': True, 'msg': 'API Key Blocked'}
                    
                # 404 Not Found: 모델 사용 불가 → 다음 모델로 교체 후 재시도
                elif "404" in error_msg or "not found" in error_msg.lower() or "no longer available" in error_msg.lower():
                    for fb in self._model_names:
                        if fb != self.model_name:
                            print(f"⚠️  모델 교체: {self.model_name} → {fb}")
                            self.model_name = fb
                            break
                    else:
                        print(f"❌ Gemini 분석 실패 (사용 가능한 모델 없음): {e}")
                        return None
                    if attempt < max_retries:
                        continue
                    return None

                # 네트워크 오류 (인터넷 끊김, DNS 실패, 서버 연결 끊김 등)
                # → 재시도 대기 후 복구되면 계속, 안 되면 network_error 반환
                elif any(t in type(e).__name__ for t in ('ConnectError', 'RemoteProtocol', 'TimeoutException', 'ReadTimeout')) \
                        or "getaddrinfo" in error_msg or "Server disconnected" in error_msg \
                        or "ConnectionError" in type(e).__name__:
                    if attempt < max_retries:
                        wait_time = base_delay * (2 ** attempt)  # 10s, 20s, 40s
                        print(f"🌐 네트워크 오류. {wait_time}초 대기 후 재시도... ({attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ 네트워크 오류로 분석 실패 (최대 재시도 초과)")
                        return {'network_error': True}

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
        consecutive_network_errors = 0  # 연속 네트워크 오류 카운터
        MAX_CONSECUTIVE_NETWORK_ERRORS = 5  # 이 이상이면 인터넷 끊긴 것으로 판단, 중단

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
            
            # [Quick Reject 1] 과거 연도 필터링
            # 사용자 요청: "2025년, 2025, 25년" 등 지난 연도 공고 제거 (현재 2026년 기준)
            # 단, '평가', '성과', '결산' 등은 작년 실적을 올해 평가하는 경우일 수 있으므로 제외
            
            found_year = None
            
            # 4자리 연도 (20XX)
            match_4 = re.search(r'(20\d{2})', title)
            if match_4:
                found_year = int(match_4.group(1))
            else:
                # 2자리 연도 ('XX년, XX년도)
                match_2 = re.search(r"['\s]?(\d{2})년", title)
                if match_2:
                    y2 = int(match_2.group(1))
                    # 2000년대 가정
                    found_year = 2000 + y2
            
            # 과거 연도이고, 예외 키워드가 없으면 거부
            safe_past_keywords = ['평가', '성과', '결산', '실적', '감사']
            
            if found_year and found_year < current_year:
                # 예외 키워드 확인
                is_safe = any(sk in title_lower for sk in safe_past_keywords)
                
                if not is_safe:
                    # [변경] 예전엔 그냥 Skip 했으나, 사용자가 Archive 저장을 원할 수 있음
                    # 따라서 relevant=True로 하되, is_past_announcement=True 설정하여
                    # 나중에 Pending 시트 저장 시 'Archive'로 분류되게 함.
                    
                    result = {
                        'is_relevant': True,
                        'url': item.get('link', ''),
                        'original_title': title,
                        'summary': f"📉 과거 공고 자동 분류 ({found_year}년)",
                        'deadline': f"{found_year}-12-31",  # 편의상 연말
                        'term_months': None,
                        'start_date': None,
                        'is_past_announcement': True,  # 핵심 플래그
                        'search_keyword': item.get('search_keyword', ''),
                        'search_query': item.get('search_query', ''),
                        'source': item.get('source', '')
                    }
                    relevant_items.append(result)
                    
                    if callback:
                        callback(f"📉 과거 공고 Archive 분류: {found_year}년")
                    continue
            
            # [Quick Reject] 제목 기반 즉시 거부 (API 절약)
            # 노무사가 갈 수 없는 명확한 키워드가 제목에 있으면 Skip
            # 예: '경비원', '미화원', '운전원', '조리원', '시설관리', '사무원', '간호사' 등
            quick_reject_keywords = [
                '경비원', '미화원', '환경미화', '운전원', '조리원', '영양사', '간호사',
                '시설관리', '시설거주', '요양보호사', '사회복지사', '물리치료사',
                '기간제근로자', '공무직', '사무원', '행정원', '연구원', '상담원',
                '대학생', '청년인턴', '체험형', '아르바이트', '단기알바',
                '용역', '입찰', '구매', '공사', '설계', '감리'
            ]
            
            if any(rj in title_no_space for rj in quick_reject_keywords):
                self.rejected_items.append({
                    'url': item.get('link', ''),
                    'title': item.get('title', ''),
                    'rejection_reason': '⚡ Quick Reject: 제목 내 제외 키워드 포함',
                    'search_keyword': item.get('search_keyword', ''),
                    'search_query': item.get('search_query', ''),
                    'source': item.get('source', '')
                })
                if callback:
                    callback(f"⚡ Quick Reject: {title[:20]}...")
                continue

            
            # 그 외는 Gemini 분석
            result = self.analyze(item, callback=callback)
            
            # [CRITICAL] 분석 중단 (API 키 차단 등)
            if result and result.get('critical_error'):
                print(f"⚠️  분석 중단: {result.get('msg')}")
                print(f"👉 남은 항목 {len(items) - idx + 1}건을 '분석 미완료' 상태로 저장합니다.")
                
                # 현재 항목 + 남은 모든 항목을 '분석 미완료'로 처리하여 저장
                remaining_items = items[idx-1:]
                for rem_item in remaining_items:
                    skipped_result = {
                        'is_relevant': True,  # 일단 저장해야 하므로 True
                        'url': rem_item.get('link', ''),
                        'original_title': rem_item.get('title', ''),
                        'summary': f"⚠️ [분석 실패] API 오류로 분석 건너뜀",
                        'deadline': None,
                        'term_months': None,
                        'start_date': None,
                        'is_past_announcement': False,
                        'search_keyword': rem_item.get('search_keyword', ''),
                        'search_query': rem_item.get('search_query', ''),
                        'source': rem_item.get('source', '')
                    }
                    relevant_items.append(skipped_result)
                
                break  # 반복 종료

            # 네트워크 오류 → 연속 횟수 카운트, 임계치 초과 시 중단
            elif result and result.get('network_error'):
                consecutive_network_errors += 1
                print(f"🌐 네트워크 오류 누적: {consecutive_network_errors}/{MAX_CONSECUTIVE_NETWORK_ERRORS}")
                relevant_items.append(self._make_failed_result(item))

                if consecutive_network_errors >= MAX_CONSECUTIVE_NETWORK_ERRORS:
                    print(f"\n❌ 네트워크 연결 불가 판단 → 남은 {len(items) - idx}건 분석 실패 처리 후 저장")
                    for rem_item in items[idx:]:
                        relevant_items.append(self._make_failed_result(rem_item))
                    break

            elif result:
                consecutive_network_errors = 0  # 성공 시 카운터 리셋
                result['search_keyword'] = item.get('search_keyword', '')
                result['search_query'] = item.get('search_query', '')
                result['source'] = item.get('source', '')
                relevant_items.append(result)
            else:
                consecutive_network_errors = 0
                # AI가 거부한 항목
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
        failed = sum(1 for r in relevant_items if '[분석 실패]' in r.get('summary', ''))
        print(f"✅ Gemini 분석 완료: {len(relevant_items) - failed}건 적합, {failed}건 분석실패, {len(self.rejected_items)}건 AI거부")
        
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
이 경우 제목에 ["노무고문", "고문노무사", "자문노무사", "노무사 위촉", "노무자문"] 중 하나가
명확히 포함된 경우에만 is_relevant=true로 판정하세요.
단순 "위촉", "고문", "자문위원" 만으로는 부족합니다. 노무/노동 분야임이 제목에서 확인돼야 합니다.
is_relevant=true인 경우 summary에 "⚠️ 첨부파일 확인 필요" 문구를 추가하세요.
"""
        
        prompt = f"""
아래 공고를 분석하여 공인노무사 지원 가능 여부를 판별하고, 필요한 정보를 추출하세요.

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
   - 노무고문·고문노무사·자문노무사·노무사 위촉·노무자문 등 **노무사가 직접 계약 주체가 되는 공고**인가?
   - 제목 또는 본문에 ["노무고문", "고문노무사", "자문노무사", "노무사 위촉", "노무자문", "노무 자문"] 중 하나가 명시돼야 true
   - "위촉" 단독, "법률고문" 단독, "자문위원" 단독은 노무 분야 명시 없으면 false
   - 본문이 없을 때는 위 키워드가 제목에 직접 있어야만 true (제목이 모호하면 false)
   - 마감일이 지난 공고도 위 조건 충족 시 true (과거 자료로 보관)
   - **불명확하거나 애매한 경우 → false**
   - **제외 대상 (is_relevant=false)**:
     - 단순 뉴스 기사, 보도자료, 인터뷰
     - 노무법인/법률사무소의 자체 홍보글, 광고
     - "합격 자기소개서", "면접 후기", "취업 팁", "강의 홍보"
     - 특정 사건 수임 홍보
     - 단순 용역 입찰 (청소, 경비, 시설관리 등)
     - 일반 직원(사무직, 경리, 연구원 등) 채용 공고
     - 감사위원, 환경위원, 문화위원 등 노무 무관 위원 위촉

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

    def _make_failed_result(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """네트워크/API 오류로 분석 실패한 항목을 '분석실패' 상태로 저장용 딕셔너리 생성"""
        return {
            'is_relevant': True,
            'url': item.get('link', ''),
            'original_title': item.get('title', ''),
            'summary': '⚠️ [분석 실패] 네트워크 오류 또는 API 차단으로 분석 불가 — 재실행 시 자동 처리',
            'deadline': None,
            'term_months': None,
            'start_date': None,
            'is_past_announcement': False,
            'search_keyword': item.get('search_keyword', ''),
            'search_query': item.get('search_query', ''),
            'source': item.get('source', ''),
        }

    def _extract_deadline_from_text(self, text: str):
        """
        텍스트(description/본문)에서 마감일 패턴 추출.
        키워드 자동통과 항목의 과거 공고 감지에 사용.

        Returns:
            (deadline_str: 'YYYY-MM-DD' or None, is_past: bool)
        """
        from datetime import date as _date

        today = _date.today()
        candidates = []

        # 패턴 1: YYYY-MM-DD 또는 YYYY.MM.DD 또는 YYYY/MM/DD
        for m in re.finditer(r'(20\d{2})[-./](\d{1,2})[-./](\d{1,2})', text):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                candidates.append(_date(y, mo, d))
            except ValueError:
                pass

        # 패턴 2: YYYY년 MM월 DD일
        for m in re.finditer(r'(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일', text):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                candidates.append(_date(y, mo, d))
            except ValueError:
                pass

        if not candidates:
            return None, False

        # 가장 최근 날짜를 마감일로 채택 (공고 본문에는 여러 날짜가 섞일 수 있음)
        # 단, 미래 날짜 > 과거 날짜 우선 (마감일은 보통 가장 나중 날짜)
        future = [d for d in candidates if d >= today]
        if future:
            chosen = min(future)  # 가장 가까운 미래 날짜
            return chosen.strftime('%Y-%m-%d'), False

        # 모두 과거이면 가장 최근 과거 날짜
        chosen = max(candidates)
        return chosen.strftime('%Y-%m-%d'), True

    def _parse_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Gemini 응답 JSON 파싱 (다양한 응답 형태 대응)
        
        Args:
            response_text: Gemini 응답 텍스트
        
        Returns:
            파싱된 딕셔너리 또는 None
        """
        if not response_text or not response_text.strip():
            print("⚠️  Gemini 응답이 비어있음 (Safety 필터링 가능)")
            return None
        
        try:
            # 코드 블록 제거 (```json ... ``` 또는 ``` ... ```)
            cleaned = response_text.strip()
            
            if cleaned.startswith('```'):
                # ```json\n{...}\n``` 형태
                lines = cleaned.split('\n')
                # 첫 줄(```json)과 마지막 줄(```) 제거
                start_idx = 1
                end_idx = len(lines) - 1
                if end_idx > start_idx:
                    cleaned = '\n'.join(lines[start_idx:end_idx])
                else:
                    cleaned = '\n'.join(lines[start_idx:])
            
            # JSON 객체 추출 시도 ({...} 범위 찾기)
            json_match = re.search(r'\{[\s\S]*\}', cleaned)
            if json_match:
                cleaned = json_match.group(0)
            
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
