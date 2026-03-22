"""
나라장터(G2B) 검색 모듈 — Track C
공공데이터포털 API를 사용해 용역 입찰 공고 수집

G2B_API_KEY 설정 없으면 자동으로 비활성화(enabled=False)되어
파이프라인에 영향 없이 빈 리스트 반환.

API 키 발급: https://www.data.go.kr (공공데이터포털 회원가입 후 신청)
활용 API: 나라장터 입찰공고정보 조회서비스 (용역/서비스)
"""

import os
import time
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from datetime import datetime, timedelta

from .config import get_config, SEARCH_DAYS_LIMIT


class G2BSearcher:
    """
    나라장터 입찰공고 검색 클래스

    API 키(G2B_API_KEY)가 없으면 enabled=False로 초기화되어 모든 search 메서드가
    빈 리스트를 반환하므로, 키 없이도 파이프라인 전체가 정상 동작함.
    """

    # 나라장터 입찰공고 목록 조회 엔드포인트 (용역/서비스 공고)
    BASE_URL = (
        'https://apis.data.go.kr/1230000/BidPublicInfoService05'
        '/getBidPblancListInfoServcPPSSrch'
    )

    # G2B 공고 상세 URL 템플릿
    DETAIL_URL = (
        'https://www.g2b.go.kr:8101/ep/invitation/publish/'
        'bidInviteDtls.do?bidno={bid_no}&bidSeq={bid_seq}'
    )

    def __init__(self):
        """API 키 확인 및 enabled 플래그 설정"""
        config = get_config()

        # 환경변수 우선, 없으면 Streamlit Secrets에서 조회
        self.api_key = (
            os.getenv('G2B_API_KEY', '')
            or config.get('g2b_api_key', '')
        )
        self.enabled = bool(self.api_key)

        if self.enabled:
            print("✅ 나라장터 API 초기화 완료 → Track C 활성화")
        else:
            print("ℹ️  나라장터 API 키 없음 → Track C 비활성화 (파이프라인 정상 동작)")

    # ===========================
    # 단건 검색
    # ===========================

    def search(self, keyword: str, num_rows: int = 20) -> List[Dict[str, Any]]:
        """
        나라장터 용역 입찰 공고 검색

        Args:
            keyword: 검색어 (예: '노무자문', '고문노무사')
            num_rows: 가져올 결과 수 (기본 20)

        Returns:
            naver_search 형식의 결과 리스트, API 키 없으면 빈 리스트
        """
        if not self.enabled:
            return []

        # 최근 N일 날짜 범위 설정
        today = datetime.now()
        from_date = (today - timedelta(days=SEARCH_DAYS_LIMIT)).strftime('%Y%m%d')
        to_date = today.strftime('%Y%m%d')

        params = {
            'serviceKey': self.api_key,
            'pageNo': '1',
            'numOfRows': str(num_rows),
            'type': 'xml',
            'bidNtceNm': keyword,           # 공고명 검색
            'ntceInsttNm': '',              # 공고기관명 (빈칸=전체)
            'bidBeginDt': from_date,        # 공고일 시작
            'bidEndDt': to_date,            # 공고일 종료
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status()
            results = self._parse_xml(response.text, keyword)
            print(f"🏛️ [Track C] 나라장터 '{keyword}' → {len(results)}건")
            return results

        except requests.exceptions.RequestException as e:
            print(f"❌ 나라장터 검색 실패 ('{keyword}'): {e}")
            return []
        except Exception as e:
            print(f"❌ 나라장터 응답 파싱 실패 ('{keyword}'): {e}")
            return []

    # ===========================
    # 복수 키워드 검색
    # ===========================

    def search_multiple(self, keywords: List[str], num_rows: int = 20) -> List[Dict[str, Any]]:
        """
        여러 키워드로 나라장터 검색 후 중복 제거

        Args:
            keywords: 검색 키워드 리스트
            num_rows: 키워드당 결과 수

        Returns:
            중복 제거된 결과 리스트
        """
        if not self.enabled:
            return []

        all_results = []

        for keyword in keywords:
            results = self.search(keyword, num_rows=num_rows)
            all_results.extend(results)
            time.sleep(0.3)  # API Rate Limiting

        # URL 기준 중복 제거
        seen_urls = set()
        unique = []
        for item in all_results:
            url = item.get('link', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(item)

        return unique

    # ===========================
    # XML 파싱
    # ===========================

    def _parse_xml(self, xml_text: str, keyword: str) -> List[Dict[str, Any]]:
        """
        나라장터 API XML 응답을 naver_search 형식으로 변환

        Args:
            xml_text: API 응답 XML 문자열
            keyword: 검색에 사용된 키워드 (메타데이터용)

        Returns:
            변환된 결과 리스트
        """
        root = ET.fromstring(xml_text)

        # API 오류 코드 확인
        result_code = root.findtext('.//resultCode', default='')
        result_msg = root.findtext('.//resultMsg', default='')
        if result_code and result_code != '00':
            print(f"⚠️ 나라장터 API 오류 {result_code}: {result_msg}")
            return []

        items = root.findall('.//item')
        results = []

        for item in items:
            bid_no = item.findtext('bidNtceNo', default='')
            bid_seq = item.findtext('bidNtceOrd', default='1')
            title = item.findtext('bidNtceNm', default='')
            org_name = item.findtext('ntceInsttNm', default='')
            pub_date = item.findtext('bidNtceDt', default='')   # 공고일 (YYYYMMDD HH:MM:SS)
            close_date = item.findtext('bidClseDt', default='') # 마감일

            if not bid_no or not title:
                continue

            # 공고 상세 링크 생성
            link = self.DETAIL_URL.format(bid_no=bid_no, bid_seq=bid_seq)

            # 설명 조합
            description_parts = []
            if org_name:
                description_parts.append(f"발주기관: {org_name}")
            if close_date:
                description_parts.append(f"마감: {self._format_date(close_date)}")
            description = ' | '.join(description_parts)

            results.append({
                'title': title,
                'link': link,
                'description': description,
                'pubDate': self._to_rfc2822(pub_date),  # naver_search 날짜 형식 호환
                'source': 'track_c',
                'search_keyword': keyword,
                'search_query': keyword,
                'search_type': 'g2b',
                'organization_hint': org_name,
            })

        return results

    # ===========================
    # 유틸리티
    # ===========================

    def _format_date(self, date_str: str) -> str:
        """
        나라장터 날짜 형식 변환 (YYYYMMDD HH:MM:SS → YYYY-MM-DD)
        """
        if not date_str:
            return ''
        try:
            # 'YYYYMMDD HH:MM:SS' 또는 'YYYY-MM-DD HH:MM:SS'
            date_str = date_str.strip()
            for fmt in ('%Y%m%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y%m%d', '%Y-%m-%d'):
                try:
                    return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                except ValueError:
                    continue
        except Exception:
            pass
        return date_str[:10]  # 파싱 실패 시 앞 10자리만

    def _to_rfc2822(self, date_str: str) -> str:
        """
        나라장터 날짜를 naver_search의 pubDate 형식으로 변환
        (filter_by_date 호환용)
        날짜 없으면 빈 문자열 반환 → filter_by_date에서 통과 처리됨
        """
        if not date_str:
            return ''
        try:
            date_str = date_str.strip()
            for fmt in ('%Y%m%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y%m%d', '%Y-%m-%d'):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # 네이버 API 형식: 'Mon, 03 Feb 2026 12:34:56 +0900'
                    return dt.strftime('%a, %d %b %Y %H:%M:%S +0900')
                except ValueError:
                    continue
        except Exception:
            pass
        return ''


# ===========================
# 독립 실행 (테스트용)
# ===========================

if __name__ == '__main__':
    print("나라장터 검색 테스트")
    print("-" * 50)

    searcher = G2BSearcher()

    if not searcher.enabled:
        print("G2B_API_KEY 환경변수를 설정하면 실제 검색이 가능합니다.")
        print("테스트: enabled=False일 때 빈 리스트 반환 확인")
        result = searcher.search('노무자문')
        print(f"결과: {result} (빈 리스트 정상)")
    else:
        results = searcher.search_multiple(['노무자문', '고문노무사'])
        print(f"\n결과 샘플 (최대 3건):")
        for item in results[:3]:
            print(f"\n제목: {item['title']}")
            print(f"링크: {item['link']}")
            print(f"설명: {item['description']}")
