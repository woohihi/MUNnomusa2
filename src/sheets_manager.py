"""
Google Sheets 관리 모듈
CRUD 작업 및 데이터 영속성 담당
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd

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
            
            sheet.update('A1:F1', [RESULTS_COLUMNS])
            sheet.format('A1:F1', {
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
            
            all_records = results_sheet.get_all_records()
            rows_to_delete = []
            
            for idx, record in enumerate(all_records, start=2):  # 헤더 skip
                if record.get('url') in expired_urls:
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
            archive_sheet.append_rows(rows)
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
            
            sheet.update('A1:I1', [ARCHIVE_COLUMNS])
            sheet.format('A1:I1', {
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
        검색 로그를 SearchLog Sheet에 추가 (중복 URL 제외)
        
        Args:
            logs: [{'timestamp': '...', 'url': '...', 'title': '...', 
                   'search_keyword': '...', 'search_query': '...', 
                   'source': '...', 'stage': '...', 'reason': '...'}, ...]
        """
        if not logs:
            return
        
        try:
            sheet = self.spreadsheet.worksheet(SHEET_NAMES['search_log'])
            
            # 기존 URL 목록 조회
            existing_urls = self.get_searchlog_urls()
            
            # 중복 URL 제외
            new_logs = [log for log in logs if log.get('url', '') not in existing_urls]
            
            if not new_logs:
                print(f"📝 SearchLog: 신규 URL 없음 (모두 중복)")
                return
            
            rows = [
                [log.get(col, '') for col in SEARCHLOG_COLUMNS]
                for log in new_logs
            ]
            
            sheet.append_rows(rows)
            
            print(f"📝 SearchLog 추가: {len(new_logs)}건 (중복 제외: {len(logs) - len(new_logs)}건)")
            
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
            sheet.format('A1:G1', {'textFormat': {'bold': True}, 'horizontalAlignment': 'CENTER'})
            
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
            
            sheet.append_rows(rows)
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
            
            records = results_sheet.get_all_records()
            rows_to_move = []
            rows_to_delete = []
            
            for idx, record in enumerate(records, start=2):  # 헤더 skip
                if record.get('url') in urls:
                    # Archive 컬럼 추가
                    archive_row = {**record}
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
            
            records = source_sheet.get_all_records()
            rows_to_delete = []
            
            for idx, record in enumerate(records, start=2):  # 헤더 skip
                if record.get('url') in urls:
                    # 제외 목록에 추가
                    self.add_to_excluded(
                        url=record.get('url', ''),
                        title=record.get('title', ''),
                        reason=reason
                    )
                    rows_to_delete.append(idx)
            
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
