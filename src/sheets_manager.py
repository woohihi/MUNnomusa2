"""
Google Sheets 관리 모듈
CRUD 작업 및 데이터 영속성 담당
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import time

from .config import (
    get_config, SHEET_NAMES, CONFIG_COLUMNS, 
    RESULTS_COLUMNS, ARCHIVE_COLUMNS, INITIAL_ORGANIZATIONS,
    SEARCHLOG_COLUMNS, KEYWORDS_COLUMNS, DEFAULT_JOB_KEYWORDS,
    EXCLUDED_COLUMNS, PENDING_COLUMNS
)


class GoogleSheetManager:
    """Google Sheets API 추상화 클래스"""
    
    def __init__(self):
        """
        Google Sheets 인증 및 스프레드시트 초기화
        """
        self.config = get_config()
        self.client = None
        self.spreadsheet = None
        self._sheet_cache = {}  # 시트 객체 캐시
        self.authenticate()
    
    def authenticate(self):
        """
        Service Account로 Google Sheets 인증
        """
        try:
            # Service Account JSON으로 인증
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = Credentials.from_service_account_info(
                self.config['gcp_service_account'],
                scopes=scopes
            )
            
            self.client = gspread.authorize(creds)
            
            # 스프레드시트 열기
            self.spreadsheet = self.client.open_by_key(
                self.config['google_sheets_id']
            )
            
            print(f"✅ Google Sheets 연결 성공: {self.spreadsheet.title}")
            
        except Exception as e:
            print(f"❌ Google Sheets 인증 실패: {e}")
            raise
    
    def get_sheet(self, sheet_key: str):
        """
        시트 객체를 캐싱하여 반환 (API 호출 최소화)
        
        Args:
            sheet_key: SHEET_NAMES 딕셔너리의 키
        
        Returns:
            gspread.Worksheet 객체
        """
        if sheet_key not in self._sheet_cache:
            sheet_name = SHEET_NAMES.get(sheet_key, sheet_key)
            self._sheet_cache[sheet_key] = self.spreadsheet.worksheet(sheet_name)
        return self._sheet_cache[sheet_key]
    
    def _with_retry(self, func, *args, max_retries=3, **kwargs):
        """
        Google Sheets API 호출 재시도 래퍼
        429(Quota), 500(Server Error), 503(Service Unavailable) 에러 시
        Exponential Backoff으로 자동 재시도
        
        Args:
            func: 실행할 함수 (gspread 메서드)
            *args: 함수 인자
            max_retries: 최대 재시도 횟수
            **kwargs: 함수 키워드 인자
        
        Returns:
            함수 실행 결과
        """
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except gspread.exceptions.APIError as e:
                last_exception = e
                status_code = 0
                # gspread APIError에서 상태 코드 추출
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    status_code = e.response.status_code
                elif hasattr(e, 'code'):
                    status_code = e.code
                else:
                    # 에러 메시지에서 추출 시도
                    error_msg = str(e)
                    for code in [429, 500, 503]:
                        if str(code) in error_msg:
                            status_code = code
                            break
                
                if status_code in (429, 500, 503) and attempt < max_retries:
                    wait_time = 5 * (2 ** attempt)  # 5초, 10초, 20초
                    print(f"⏳ Google Sheets API 오류 ({status_code}). {wait_time}초 후 재시도... ({attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    raise
        raise last_exception
    
    # ===========================
    # Config Sheet 작업
    # ===========================
    
    def read_config(self) -> List[Dict[str, Any]]:
        """
        Config Sheet에서 감시 대상 기관 리스트 로드
        
        Returns:
            활성화된 기관 리스트 [{'organization': '...', 'keywords': '...'}, ...]
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['config'])
            records = sheet.get_all_records()
            
            # active=True인 기관만 필터링
            active_orgs = [
                r for r in records
                if r.get('active') in [True, 'TRUE', 'true', 1, '1']
            ]

            # grade 컬럼 없는 기존 시트와 호환: 없으면 'B' 기본값
            for org in active_orgs:
                grade = str(org.get('grade', '')).strip().upper()
                if grade not in ('A', 'B', 'C'):
                    org['grade'] = 'B'
                else:
                    org['grade'] = grade

            print(f"📋 Config Sheet: {len(active_orgs)}개 활성 기관 로드됨")
            return active_orgs
            
        except gspread.exceptions.WorksheetNotFound:
            print("⚠️  Config Sheet 없음. 초기화 필요")
            return []
        except Exception as e:
            print(f"❌ Config 읽기 실패: {e}")
            return []
    
    def init_config_sheet(self):
        """
        Config Sheet 초기화 (헤더 + 10개 기관 데이터)
        """
        try:
            # 기존 시트 확인 및 삭제
            try:
                sheet = self.spreadsheet.worksheet(SHEET_NAMES['config'])
                print("⚠️  기존 Config Sheet 발견. 덮어쓰기...")
            except gspread.exceptions.WorksheetNotFound:
                sheet = self.spreadsheet.add_worksheet(
                    title=SHEET_NAMES['config'],
                    rows=100,
                    cols=10
                )
            
            # 헤더 작성
            sheet.update('A1:C1', [CONFIG_COLUMNS])
            
            # 초기 데이터 작성
            data_rows = [
                [org['organization'], org['keywords'], org['active']]
                for org in INITIAL_ORGANIZATIONS
            ]
            
            sheet.update(f'A2:C{len(data_rows)+1}', data_rows)
            
            # 포맷팅 (헤더 굵게)
            sheet.format('A1:C1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            print(f"✅ Config Sheet 초기화 완료 ({len(data_rows)}개 기관)")
            
        except Exception as e:
            print(f"❌ Config Sheet 초기화 실패: {e}")
            raise
    
    def add_config_row(self, org_data: Dict[str, Any]):
        """
        Config Sheet에 새 기관 추가
        
        Args:
            org_data: {'organization': '...', 'keywords': '...', 'active': True/False}
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['config'])
            
            row = [
                org_data.get('organization', ''),
                org_data.get('keywords', ''),
                org_data.get('active', True)
            ]
            
            sheet.append_row(row)
            print(f"✅ Config 추가: {org_data.get('organization')}")
            
        except Exception as e:
            print(f"❌ Config 추가 실패: {e}")
            raise
    
    # ===========================
    # Results Sheet 작업
    # ===========================
    
    def read_results(self) -> pd.DataFrame:
        """
        Results Sheet에서 현재 진행 중인 공고 로드
        
        Returns:
            DataFrame (컬럼: url, title, organization, deadline, summary, collected_date)
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['results'])
            records = sheet.get_all_records()
            df = pd.DataFrame(records)
            
            if df.empty:
                # 빈 DataFrame 반환 (컬럼 유지)
                return pd.DataFrame(columns=RESULTS_COLUMNS)
            
            print(f"📊 Results Sheet: {len(df)}건 공고 로드됨")
            return df
            
        except gspread.exceptions.WorksheetNotFound:
            print("⚠️  Results Sheet 없음. 초기화 필요")
            return pd.DataFrame(columns=RESULTS_COLUMNS)
        except Exception as e:
            print(f"❌ Results 읽기 실패: {e}")
            return pd.DataFrame(columns=RESULTS_COLUMNS)
    
    def get_result_urls(self) -> List[str]:
        """
        Results Sheet의 URL 리스트 (중복 체크용)
        
        Returns:
            URL 문자열 리스트
        """
        df = self.read_results()
        return df['url'].tolist() if not df.empty else []
    
    def append_result(self, data: Dict[str, Any]):
        """
        신규 공고를 Results Sheet에 추가
        
        Args:
            data: {'url': '...', 'title': '...', 'organization': '...', 
                   'deadline': 'YYYY-MM-DD', 'summary': '...', 'collected_date': 'YYYY-MM-DD'}
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['results'])
            
            # 컬럼 순서대로 행 생성
            row = [data.get(col, '') for col in RESULTS_COLUMNS]
            sheet.append_row(row)
            
            print(f"✅ Results 추가: {data.get('title', 'Unknown')}")
            
        except gspread.exceptions.WorksheetNotFound:
            self.init_results_sheet()
            self.append_result(data)  # 재귀 호출
        except Exception as e:
            print(f"❌ Results 추가 실패: {e}")
    
    def append_results_batch(self, data_list: List[Dict[str, Any]]):
        """
        여러 공고를 한 번에 추가 (배치 작업)
        
        Args:
            data_list: 딕셔너리 리스트
        """
        if not data_list:
            return
        
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['results'])
            
            rows = [
                [data.get(col, '') for col in RESULTS_COLUMNS]
                for data in data_list
            ]
            
            sheet.append_rows(rows)
            
            print(f"✅ Results 배치 추가: {len(data_list)}건")
            
        except gspread.exceptions.WorksheetNotFound:
            self.init_results_sheet()
            self.append_results_batch(data_list)
        except Exception as e:
            print(f"❌ Results 배치 추가 실패: {e}")
    
    def init_results_sheet(self):
        """Results Sheet 초기화 (헤더만)"""
        try:
            try:
                sheet = self.spreadsheet.worksheet(SHEET_NAMES['results'])
            except gspread.exceptions.WorksheetNotFound:
                sheet = self.spreadsheet.add_worksheet(
                    title=SHEET_NAMES['results'],
                    rows=500,
                    cols=10
                )
            
            sheet.update('A1:I1', [RESULTS_COLUMNS])
            sheet.format('A1:I1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.8, 'green': 0.9, 'blue': 1.0}
            })
            
            print("✅ Results Sheet 초기화 완료")
            
        except Exception as e:
            print(f"❌ Results Sheet 초기화 실패: {e}")
            raise
    
    # ===========================
    # Archive Sheet 작업
    # ===========================
    
    def read_archive(self) -> pd.DataFrame:
        """
        Archive Sheet에서 마감된 공고 로드
        
        Returns:
            DataFrame (컬럼: Results + term_months, start_date, next_expected_date)
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['archive'])
            records = sheet.get_all_records()
            df = pd.DataFrame(records)
            
            if df.empty:
                return pd.DataFrame(columns=ARCHIVE_COLUMNS)
            
            print(f"📦 Archive Sheet: {len(df)}건 공고 로드됨")
            return df
            
        except gspread.exceptions.WorksheetNotFound:
            print("⚠️  Archive Sheet 없음. 초기화 필요")
            return pd.DataFrame(columns=ARCHIVE_COLUMNS)
        except Exception as e:
            print(f"❌ Archive 읽기 실패: {e}")
            return pd.DataFrame(columns=ARCHIVE_COLUMNS)
    
    def get_archive_urls(self) -> List[str]:
        """
        Archive Sheet의 URL 리스트 (중복 체크용)
        
        Returns:
            URL 문자열 리스트
        """
        df = self.read_archive()
        return df['url'].tolist() if not df.empty else []
    
    def archive_expired(self):
        """
        마감일 지난 공고를 Results → Archive로 이동
        """
        try:
            results_df = self.read_results()
            
            if results_df.empty:
                print("📭 Results Sheet가 비어있음. 아카이빙 스킵")
                return
            
            # 마감일 파싱 및 필터링
            today = datetime.now().date()
            expired_rows = []
            
            for idx, row in results_df.iterrows():
                deadline_str = row.get('deadline', '')
                
                if not deadline_str:
                    continue
                
                try:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                    
                    if deadline < today:
                        # Archive 컬럼 추가 (CRM 데이터는 비워둠)
                        archive_row = row.to_dict()
                        archive_row['term_months'] = ''
                        archive_row['start_date'] = ''
                        archive_row['next_expected_date'] = ''
                        expired_rows.append(archive_row)
                        
                except ValueError:
                    pass
            
            if not expired_rows:
                print("✅ 마감된 공고 없음")
                return
            
            # Archive Sheet에 추가
            archive_sheet = self.spreadsheet.worksheet(SHEET_NAMES['archive'])
            rows = [
                [data.get(col, '') for col in ARCHIVE_COLUMNS]
                for data in expired_rows
            ]
            archive_sheet.append_rows(rows)
            
            # Results Sheet에서 삭제 (역순으로 삭제)
            results_sheet = self.spreadsheet.worksheet(SHEET_NAMES['results'])
            expired_urls = [r['url'] for r in expired_rows]
            
            # get_all_records 대신 get_all_values 사용 (행 번호 정확도 보장)
            all_values = results_sheet.get_all_values()
            if len(all_values) < 2:
                return

            headers = all_values[0]
            try:
                url_col_idx = headers.index('url')
            except ValueError:
                return

            rows_to_delete = []
            
            for idx, row in enumerate(all_values[1:], start=2):  # 헤더 skip
                current_url = row[url_col_idx] if len(row) > url_col_idx else ''
                if current_url in expired_urls:
                    rows_to_delete.append(idx)
            
            # 역순으로 삭제 (행 번호 변경 방지)
            for row_idx in sorted(rows_to_delete, reverse=True):
                results_sheet.delete_rows(row_idx)
            
            print(f"✅ 아카이빙 완료: {len(expired_rows)}건 이동")
            
        except gspread.exceptions.WorksheetNotFound:
            self.init_archive_sheet()
            self.archive_expired()
        except Exception as e:
            print(f"❌ 아카이빙 실패: {e}")
    
    def append_archive_batch(self, data_list: List[Dict[str, Any]]):
        """
        여러 과거 공고를 Archive에 직접 추가 (마감된 공고용)
        
        Args:
            data_list: Archive 컬럼 형식의 딕셔너리 리스트
        """
        if not data_list:
            return
        
        try:
            archive_sheet = self.spreadsheet.worksheet(SHEET_NAMES['archive'])
            rows = [
                [data.get(col, '') for col in ARCHIVE_COLUMNS]
                for data in data_list
            ]
            self._with_retry(archive_sheet.append_rows, rows)
            print(f"✅ Archive에 {len(data_list)}건 직접 저장")
            
        except gspread.exceptions.WorksheetNotFound:
            self.init_archive_sheet()
            self.append_archive_batch(data_list)
        except Exception as e:
            print(f"❌ Archive 배치 추가 실패: {e}")
    
    def init_archive_sheet(self):
        """Archive Sheet 초기화 (헤더만)"""
        try:
            try:
                sheet = self.spreadsheet.worksheet(SHEET_NAMES['archive'])
            except gspread.exceptions.WorksheetNotFound:
                sheet = self.spreadsheet.add_worksheet(
                    title=SHEET_NAMES['archive'],
                    rows=1000,
                    cols=12
                )
            
            sheet.update('A1:L1', [ARCHIVE_COLUMNS])
            sheet.format('A1:L1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 1.0, 'green': 0.9, 'blue': 0.8}
            })
            
            print("✅ Archive Sheet 초기화 완료")
            
        except Exception as e:
            print(f"❌ Archive Sheet 초기화 실패: {e}")
            raise
    
    # ===========================
    # SearchLog Sheet 작업
    # ===========================
    
    def get_searchlog_urls(self) -> set:
        """
        SearchLog에 이미 기록된 URL 목록 조회
        
        Returns:
            기존 URL들의 set
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['search_log'])
            records = sheet.get_all_records()
            
            urls = {record.get('url', '') for record in records if record.get('url')}
            return urls
            
        except gspread.exceptions.WorksheetNotFound:
            return set()
        except Exception as e:
            print(f"⚠️ SearchLog URL 조회 실패: {e}")
            return set()
    
    def append_search_log(self, logs: List[Dict[str, Any]]):
        """
        검색 로그를 SearchLog Sheet에 추가 (Append Only)
        
        SearchLog는 URL의 라이프사이클을 추적하는 이벤트 로그입니다.
        동일 URL이 여러 stage(collected → filtered → analyzing → saved)를 거치므로
        URL 중복 체크 없이 단순 추가합니다.
        
        Args:
            logs: [{'timestamp': '...', 'url': '...', 'title': '...', 
                   'search_keyword': '...', 'search_query': '...', 
                   'source': '...', 'stage': '...', 'reason': '...'}, ...]
        """
        if not logs:
            return
        
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['search_log'])
            
            rows = [
                [log.get(col, '') for col in SEARCHLOG_COLUMNS]
                for log in logs
            ]
            
            # 재시도 로직 적용 (429 에러 대응)
            self._with_retry(sheet.append_rows, rows)
            
            print(f"📝 SearchLog 추가: {len(logs)}건")
            
        except gspread.exceptions.WorksheetNotFound:
            self.init_search_log_sheet()
            self.append_search_log(logs)
        except Exception as e:
            print(f"❌ SearchLog 추가 실패: {e}")
    
    def read_search_log(self) -> List[Dict[str, Any]]:
        """
        SearchLog Sheet에서 모든 검색 로그 로드
        
        Returns:
            로그 딕셔너리 리스트
        """
        try:
            sheet = self.get_sheet('search_log')
            records = sheet.get_all_records()
            return records
        except gspread.exceptions.WorksheetNotFound:
            return []
        except Exception as e:
            print(f"⚠️ SearchLog 로드 실패: {e}")
            return []
    
    def cleanup_search_log(self, keep_days: int = 30) -> int:
        """
        SearchLog에서 오래된 행 삭제 (keep_days일 이전 데이터 제거)

        Args:
            keep_days: 보존할 일수 (기본 30일)

        Returns:
            삭제된 행 수
        """
        from datetime import datetime, timedelta

        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['search_log'])
            all_values = sheet.get_all_values()  # 헤더 포함 전체

            if len(all_values) <= 1:
                return 0  # 헤더만 있으면 스킵

            header = all_values[0]
            rows = all_values[1:]

            cutoff = datetime.now() - timedelta(days=keep_days)

            # timestamp 컬럼 인덱스 찾기
            try:
                ts_idx = header.index('timestamp')
            except ValueError:
                ts_idx = 0  # 첫 번째 컬럼 fallback

            keep_rows = []
            deleted = 0
            for row in rows:
                ts_str = row[ts_idx] if len(row) > ts_idx else ''
                try:
                    ts = datetime.strptime(ts_str[:19], '%Y-%m-%d %H:%M:%S')
                    if ts >= cutoff:
                        keep_rows.append(row)
                    else:
                        deleted += 1
                except (ValueError, TypeError):
                    keep_rows.append(row)  # 파싱 실패 시 보존

            if deleted == 0:
                return 0

            # 시트 재작성 (헤더 + 보존 행)
            sheet.clear()
            self._with_retry(sheet.update, 'A1', [header] + keep_rows)
            print(f"🧹 SearchLog 정리: {deleted}건 삭제 ({keep_days}일 이전), {len(keep_rows)}건 보존")
            return deleted

        except gspread.exceptions.WorksheetNotFound:
            return 0
        except Exception as e:
            print(f"⚠️ SearchLog 정리 실패 (계속 진행): {e}")
            return 0

    def init_search_log_sheet(self):
        """SearchLog Sheet 초기화 (헤더만)"""
        try:
            try:
                sheet = self.spreadsheet.worksheet(SHEET_NAMES['search_log'])
            except gspread.exceptions.WorksheetNotFound:
                sheet = self.spreadsheet.add_worksheet(
                    title=SHEET_NAMES['search_log'],
                    rows=2000,
                    cols=10
                )
            
            sheet.update('A1:H1', [SEARCHLOG_COLUMNS])
            sheet.format('A1:H1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.95, 'blue': 1.0}
            })
            
            print("✅ SearchLog Sheet 초기화 완료")
            
        except Exception as e:
            print(f"❌ SearchLog Sheet 초기화 실패: {e}")
            raise
    
    # ===========================
    # Keywords Sheet 작업
    # ===========================
    
    def read_keywords(self) -> List[str]:
        """
        Keywords Sheet에서 활성화된 키워드 로드
        
        Returns:
            키워드 문자열 리스트
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['keywords'])
            records = sheet.get_all_records()
            
            keywords = [
                r.get('keyword', '') 
                for r in records 
                if r.get('active', True) in [True, 'TRUE', 'true', 1]
            ]
            
            print(f"📋 Keywords 로드: {len(keywords)}개")
            return keywords
            
        except gspread.exceptions.WorksheetNotFound:
            print("⚠️ Keywords Sheet 없음. 기본값 사용")
            return DEFAULT_JOB_KEYWORDS
        except Exception as e:
            print(f"❌ Keywords 읽기 실패: {e}")
            return DEFAULT_JOB_KEYWORDS
    
    def add_keyword(self, keyword: str, active: bool = True):
        """
        Keywords Sheet에 새 키워드 추가
        
        Args:
            keyword: 키워드 문자열
            active: 활성화 여부
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['keywords'])
            sheet.append_row([keyword, active])
            print(f"✅ 키워드 추가: {keyword}")
            
        except gspread.exceptions.WorksheetNotFound:
            self.init_keywords_sheet()
            self.add_keyword(keyword, active)
        except Exception as e:
            print(f"❌ 키워드 추가 실패: {e}")
            raise
    
    def init_keywords_sheet(self):
        """Keywords Sheet 초기화 (기본 키워드 복사)"""
        try:
            try:
                sheet = self.spreadsheet.worksheet(SHEET_NAMES['keywords'])
            except gspread.exceptions.WorksheetNotFound:
                sheet = self.spreadsheet.add_worksheet(
                    title=SHEET_NAMES['keywords'],
                    rows=100,
                    cols=5
                )
            
            # 헤더 작성
            sheet.update('A1:B1', [KEYWORDS_COLUMNS])
            
            # 기본 키워드 작성
            data_rows = [[kw, True] for kw in DEFAULT_JOB_KEYWORDS]
            sheet.update(f'A2:B{len(data_rows)+1}', data_rows)
            
            # 포맷팅
            sheet.format('A1:B1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.95, 'blue': 0.9}
            })
            
            print(f"✅ Keywords Sheet 초기화 완료 ({len(data_rows)}개 키워드)")
            
        except Exception as e:
            print(f"❌ Keywords Sheet 초기화 실패: {e}")
            raise
    
    # ===========================
    # 유틸리티
    # ===========================
    
    def init_all_sheets(self):
        """모든 시트 초기화 (첫 실행 시)"""
        print("🔧 Google Sheets 전체 초기화 시작...")
        self.init_config_sheet()
        self.init_results_sheet()
        self.init_archive_sheet()
        self.init_search_log_sheet()
        print("✅ 모든 시트 초기화 완료!")
    
    def test_connection(self) -> bool:
        """
        연결 테스트
        
        Returns:
            성공 여부
        """
        try:
            title = self.spreadsheet.title
            print(f"✅ 연결 성공: {title}")
            return True
        except Exception as e:
            print(f"❌ 연결 실패: {e}")
            return False
    
    # ===========================
    # Excluded Sheet 작업
    # ===========================
    
    def init_excluded_sheet(self):
        """Excluded Sheet 초기화"""
        try:
            try:
                sheet = self.spreadsheet.worksheet(SHEET_NAMES['excluded'])
                print("✅ Excluded Sheet 이미 존재")
            except gspread.exceptions.WorksheetNotFound:
                sheet = self.spreadsheet.add_worksheet(
                    title=SHEET_NAMES['excluded'],
                    rows=1000,
                    cols=10
                )
            
            sheet.update('A1:D1', [EXCLUDED_COLUMNS])
            sheet.format('A1:D1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.8, 'blue': 0.8}
            })
            
            print("✅ Excluded Sheet 초기화 완료")
            
        except Exception as e:
            print(f"❌ Excluded Sheet 초기화 실패: {e}")
            raise
    
    def get_pending_urls(self) -> set:
        """
        Pending 시트 URL 조회 (중복 수집 방지용)
        분할 실행 시 이미 Pending에 있는 항목은 재분석하지 않도록 차단

        Returns:
            Pending에 저장된 URL들의 set
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['pending'])
            records = sheet.get_all_records(expected_headers=PENDING_COLUMNS)
            urls = {r.get('url', '') for r in records if r.get('url')}
            return urls
        except gspread.exceptions.WorksheetNotFound:
            return set()
        except Exception:
            return set()

    def get_excluded_urls(self) -> set:
        """
        제외 목록 URL 조회
        
        Returns:
            제외된 URL들의 set
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['excluded'])
            records = sheet.get_all_records()
            
            urls = {record.get('url', '') for record in records if record.get('url')}
            return urls
            
        except gspread.exceptions.WorksheetNotFound:
            return set()
        except Exception as e:
            print(f"⚠️ Excluded URL 조회 실패: {e}")
            return set()
    
    def add_to_excluded(self, url: str, title: str, reason: str = "수동 제외"):
        """
        URL을 제외 목록에 추가 (단일)
        
        Args:
            url: 제외할 URL
            title: 공고 제목
            reason: 제외 사유
        """
        self.add_to_excluded_batch([{'url': url, 'title': title, 'reason': reason}])
    
    def add_to_excluded_batch(self, items: List[Dict[str, str]]):
        """
        여러 URL을 제외 목록에 배치로 추가 (API 호출 최소화)
        
        Args:
            items: [{'url': '...', 'title': '...', 'reason': '...'}, ...]
        """
        if not items:
            return
        
        try:
            try:
                sheet = self.get_sheet('excluded')
            except gspread.exceptions.WorksheetNotFound:
                self.init_excluded_sheet()
                self._sheet_cache.pop('excluded', None)  # 캐시 초기화
                sheet = self.get_sheet('excluded')
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            rows = [
                [item['url'], item['title'], item.get('reason', '수동 제외'), timestamp]
                for item in items
            ]
            
            sheet.append_rows(rows)
            print(f"✅ 제외 목록 추가: {len(items)}건")
            
        except Exception as e:
            print(f"❌ 제외 목록 추가 실패: {e}")
            raise
    
    # ===========================
    # Pending Sheet 작업 (검토 대기)
    # ===========================
    
    def init_pending_sheet(self):
        """Pending Sheet 초기화 (헤더만)"""
        try:
            try:
                sheet = self.spreadsheet.add_worksheet(
                    title=SHEET_NAMES['pending'],
                    rows=100,
                    cols=len(PENDING_COLUMNS)
                )
            except gspread.exceptions.APIError:
                # 이미 존재할 경우
                sheet = self.spreadsheet.worksheet(SHEET_NAMES['pending'])
                sheet.clear()
                
            # 헤더 추가
            sheet.update('A1', [PENDING_COLUMNS])
            
            # 포맷팅
            sheet.format('A1:L1', {'textFormat': {'bold': True}, 'horizontalAlignment': 'CENTER'})
            
            print("✅ Pending Sheet 초기화 완료")
            return sheet
            
        except Exception as e:
            print(f"❌ Pending Sheet 초기화 실패: {e}")
            raise

    def append_pending_batch(self, data_list: List[Dict[str, Any]]):
        """
        검토 대기 중인 공고를 Pending Sheet에 배치 추가
        
        Args:
            data_list: 딕셔너리 리스트
        """
        if not data_list:
            return
            
        try:
            try:
                sheet = self.get_sheet('pending')
            except gspread.exceptions.WorksheetNotFound:
                self.init_pending_sheet()
                self._sheet_cache.pop('pending', None)
                sheet = self.get_sheet('pending')
            
            rows = []
            for item in data_list:
                row = [item.get(col, '') for col in PENDING_COLUMNS]
                rows.append(row)
            
            self._with_retry(sheet.append_rows, rows)
            print(f"✅ Pending 추가: {len(data_list)}건")
            
        except Exception as e:
            print(f"❌ Pending 추가 실패: {e}")
            raise

    def read_pending(self) -> pd.DataFrame:
        """
        Pending Sheet에서 검토 대기 공고 로드
        
        Returns:
            DataFrame
        """
        try:
            sheet = self.get_sheet('pending')
            records = sheet.get_all_records()
            return pd.DataFrame(records)
        except gspread.exceptions.WorksheetNotFound:
            return pd.DataFrame(columns=PENDING_COLUMNS)
        except Exception as e:
            print(f"⚠️ Pending 로드 실패: {e}")
            return pd.DataFrame(columns=PENDING_COLUMNS)

    def clear_pending(self):
        """Pending Sheet 데이터 초기화 (검토 완료 후)"""
        try:
            sheet = self.get_sheet('pending')
            # 헤더(1행)는 남기고 2행부터 삭제
            sheet.resize(rows=1)
            sheet.resize(rows=100) # 다시 적당한 크기로
            print("🧹 Pending Sheet 정리 완료")
        except Exception as e:
            print(f"❌ Pending 정리 실패: {e}")

    def process_pending_approvals(self) -> Dict[str, int]:
        """
        Pending 시트의 status 컬럼을 읽어 자동 분류 처리.

        - '적합' → Results 시트로 이동
        - '거절' → Excluded 시트에 추가 (재수집 방지)
        - '보류' / '검토중' / 빈값 → 유지

        Returns:
            {'approved': N, 'rejected': N, 'kept': N}
        """
        from datetime import datetime as dt

        try:
            df = self.read_pending()
        except Exception as e:
            print(f"❌ Pending 읽기 실패: {e}")
            return {'approved': 0, 'rejected': 0, 'kept': 0}

        if df.empty:
            print("ℹ️  Pending 시트가 비어있습니다.")
            return {'approved': 0, 'rejected': 0, 'kept': 0}

        # status 컬럼이 없으면 모두 '검토중' 처리
        if 'status' not in df.columns:
            df['status'] = '검토중'

        approved_rows = df[df['status'] == '적합'].to_dict('records')
        rejected_rows = df[df['status'] == '거절'].to_dict('records')
        kept_rows = df[~df['status'].isin(['적합', '거절'])].to_dict('records')

        # 적합 → Results 이동
        if approved_rows:
            results_data = [
                {
                    'url': r.get('url', ''),
                    'title': r.get('title', ''),
                    'organization': r.get('organization', ''),
                    'deadline': r.get('deadline', ''),
                    'summary': r.get('summary', ''),
                    'collected_date': r.get('collected_date', dt.now().strftime('%Y-%m-%d')),
                    'source': r.get('source', ''),
                    'search_keyword': r.get('search_keyword', ''),
                    'search_query': r.get('search_query', ''),
                }
                for r in approved_rows
            ]
            try:
                self.append_results_batch(results_data)
                print(f"✅ 적합 {len(approved_rows)}건 → Results 이동 완료")
            except Exception as e:
                print(f"❌ Results 이동 실패: {e}")

        # 거절 → Excluded 추가
        if rejected_rows:
            excluded_data = [
                {
                    'url': r.get('url', ''),
                    'title': r.get('title', ''),
                    'reason': '사용자 거절 (Pending 검토)',
                    'excluded_date': dt.now().strftime('%Y-%m-%d'),
                }
                for r in rejected_rows
            ]
            try:
                self.add_to_excluded_batch(excluded_data)
                print(f"✅ 거절 {len(rejected_rows)}건 → Excluded 추가 완료")
            except Exception as e:
                print(f"❌ Excluded 추가 실패: {e}")

        # Pending 시트를 '보류/검토중' 항목만 남기도록 재작성
        try:
            sheet = self.get_sheet('pending')
            sheet.resize(rows=1)  # 헤더만 남기기
            if kept_rows:
                rows = [
                    [r.get(col, '') for col in PENDING_COLUMNS]
                    for r in kept_rows
                ]
                self._with_retry(sheet.append_rows, rows)
            print(f"🧹 Pending 정리 완료: {len(kept_rows)}건 유지")
        except Exception as e:
            print(f"❌ Pending 재작성 실패: {e}")

        return {
            'approved': len(approved_rows),
            'rejected': len(rejected_rows),
            'kept': len(kept_rows),
        }

    def reset_all_data(self) -> Dict[str, bool]:
        """
        모든 데이터 시트를 초기화 (헤더만 남기고 데이터 삭제).
        Config 시트는 건드리지 않음.

        Returns:
            {'results': True, 'archive': True, ...} 각 시트 성공 여부
        """
        targets = ['results', 'archive', 'pending', 'search_log', 'excluded']
        result = {}
        for key in targets:
            try:
                sheet = self.spreadsheet.worksheet(SHEET_NAMES[key])
                sheet.resize(rows=1)  # 헤더(1행)만 남기기
                self._sheet_cache.pop(key, None)
                print(f"🧹 {SHEET_NAMES[key]} 초기화 완료")
                result[key] = True
            except gspread.exceptions.WorksheetNotFound:
                print(f"ℹ️  {SHEET_NAMES[key]} 시트 없음 (스킵)")
                result[key] = True
            except Exception as e:
                print(f"❌ {SHEET_NAMES[key]} 초기화 실패: {e}")
                result[key] = False
        return result

    def move_to_archive(self, urls: List[str]):
        """
        Results에서 Archive로 공고 이동
        
        Args:
            urls: 이동할 URL 리스트
        """
        if not urls:
            return
        
        try:
            results_sheet = self.spreadsheet.worksheet(SHEET_NAMES['results'])
            
            try:
                archive_sheet = self.spreadsheet.worksheet(SHEET_NAMES['archive'])
            except gspread.exceptions.WorksheetNotFound:
                self.init_archive_sheet()
                archive_sheet = self.spreadsheet.worksheet(SHEET_NAMES['archive'])
            
            # get_all_records 대신 get_all_values 사용 (행 번호 정확도 보장)
            all_values = results_sheet.get_all_values()
            if len(all_values) < 2:
                return
                
            headers = all_values[0]
            try:
                url_col_idx = headers.index('url')
            except ValueError:
                print("❌ 'url' 컬럼을 찾을 수 없습니다.")
                return

            rows_to_move = []
            rows_to_delete = []
            
            for idx, row in enumerate(all_values[1:], start=2):  # 헤더 skip
                current_url = row[url_col_idx] if len(row) > url_col_idx else ''
                
                if current_url in urls:
                    # Dict로 변환
                    record = {
                        header: (row[i] if len(row) > i else '') 
                        for i, header in enumerate(headers)
                    }
                    
                    # Archive 컬럼 추가
                    archive_row = record.copy()
                    archive_row['term_months'] = ''
                    archive_row['start_date'] = ''
                    archive_row['next_expected_date'] = ''
                    rows_to_move.append(archive_row)
                    rows_to_delete.append(idx)
            
            if not rows_to_move:
                print("⚠️ 이동할 공고가 없습니다")
                return
            
            # Archive에 추가
            archive_rows = [
                [data.get(col, '') for col in ARCHIVE_COLUMNS]
                for data in rows_to_move
            ]
            archive_sheet.append_rows(archive_rows)
            
            # Results에서 삭제 (역순)
            for row_idx in sorted(rows_to_delete, reverse=True):
                results_sheet.delete_rows(row_idx)
            
            print(f"✅ Archive로 이동: {len(rows_to_move)}건")
            
        except Exception as e:
            print(f"❌ Archive 이동 실패: {e}")
            raise
    
    def move_to_excluded(self, urls: List[str], source: str = 'results', reason: str = "수동 제외"):
        """
        Results 또는 Archive에서 제외 목록으로 이동
        
        Args:
            urls: 이동할 URL 리스트
            source: 출처 ('results' 또는 'archive')
            reason: 제외 사유
        """
        if not urls:
            return
        
        try:
            source_sheet_name = SHEET_NAMES[source]
            source_sheet = self.spreadsheet.worksheet(source_sheet_name)
            
            # get_all_values 사용
            all_values = source_sheet.get_all_values()
            if len(all_values) < 2:
                return
                
            headers = all_values[0]
            try:
                url_col_idx = headers.index('url')
                title_col_idx = headers.index('title') if 'title' in headers else -1
            except ValueError:
                print("❌ 'url' 컬럼을 찾을 수 없습니다.")
                return

            items_to_add = []
            rows_to_delete = []
            
            for idx, row in enumerate(all_values[1:], start=2):  # 헤더 skip
                current_url = row[url_col_idx] if len(row) > url_col_idx else ''
                
                if current_url in urls:
                    current_title = row[title_col_idx] if (title_col_idx != -1 and len(row) > title_col_idx) else 'Unknown'
                    
                    items_to_add.append({
                        'url': current_url,
                        'title': current_title,
                        'reason': reason
                    })
                    rows_to_delete.append(idx)
            
            # 제외 목록에 배치 추가
            if items_to_add:
                self.add_to_excluded_batch(items_to_add)
            
            # 원본에서 삭제 (역순)
            for row_idx in sorted(rows_to_delete, reverse=True):
                source_sheet.delete_rows(row_idx)
            
            print(f"✅ 제외 목록으로 이동: {len(rows_to_delete)}건")
            
        except Exception as e:
            print(f"❌ 제외 목록 이동 실패: {e}")
            raise


# ===========================
# 독립 실행 (테스트용)
# ===========================

if __name__ == '__main__':
    print("Google Sheets Manager 테스트")
    print("-" * 50)
    
    manager = GoogleSheetManager()
    
    # 연결 테스트
    if manager.test_connection():
        # 시트 초기화
        manager.init_all_sheets()
        
        # Config 읽기 테스트
        orgs = manager.read_config()
        print(f"\n활성 기관 {len(orgs)}개:")
        for org in orgs[:3]:
            print(f"  - {org['organization']}")
