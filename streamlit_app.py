"""
Streamlit 웹 대시보드
AI 노무고문 공고 모니터링 시스템
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import io

# 로컬 모듈 import
from src.sheets_manager import GoogleSheetManager
from src.naver_search import NaverSearcher
from src.preprocessor import Preprocessor
from src.gemini_analyzer import GeminiAnalyzer
from src.predictor import Predictor
from src.email_sender import EmailSender


# ===========================
# 페이지 설정
# ===========================

st.set_page_config(
    page_title="AI 노무고문 공고 모니터링",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===========================
# 세션 상태 초기화
# ===========================

if 'sheets_manager' not in st.session_state:
    st.session_state.sheets_manager = None

if 'last_search_time' not in st.session_state:
    st.session_state.last_search_time = None


# ===========================
# 헬퍼 함수
# ===========================

@st.cache_resource
def get_sheets_manager():
    """Google Sheets Manager 싱글톤"""
    try:
        manager = GoogleSheetManager()
        return manager
    except Exception as e:
        st.error(f"Google Sheets 연결 실패: {e}")
        return None


def calculate_dday(deadline_str: str) -> str:
    """
    D-day 계산
    
    Args:
        deadline_str: 'YYYY-MM-DD'
    
    Returns:
        'D-X' 또는 '마감'
    """
    if not deadline_str:
        return 'N/A'
    
    try:
        deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        today = datetime.now().date()
        delta = (deadline - today).days
        
        if delta < 0:
            return '마감'
        elif delta == 0:
            return 'D-Day'
        else:
            return f'D-{delta}'
    except:
        return 'N/A'


def export_to_obsidian(df: pd.DataFrame) -> str:
    """
    Obsidian 마크다운 포맷으로 변환
    
    Args:
        df: Results DataFrame
    
    Returns:
        마크다운 문자열
    """
    md = f"# 노무고문 공고 목록\n\n"
    md += f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += "---\n\n"
    
    for idx, row in df.iterrows():
        md += f"## {row.get('organization', 'Unknown')}\n\n"
        md += f"### {row.get('title', 'Untitled')}\n\n"
        md += f"- **마감일**: {row.get('deadline', 'N/A')}\n"
        md += f"- **D-day**: {calculate_dday(row.get('deadline', ''))}\n"
        md += f"- **링크**: [{row.get('url', '#')}]({row.get('url', '#')})\n"
        md += f"- **요약**: {row.get('summary', '')}\n\n"
        md += "---\n\n"
    
    return md


# ===========================
# 메인 UI
# ===========================

st.title("🔍 AI 노무고문 공고 모니터링 시스템")
st.caption("공공기관 노무고문/자문위원 모집 공고 24시간 감시 및 예측")

# 탭 생성
tab1, tab2, tab3, tab4 = st.tabs(["🏠 현재 공고", "🔍 검색 실행", "📈 예측 알림", "⚙️ 설정"])


# ===========================
# 탭 1: 현재 공고
# ===========================

with tab1:
    st.header("📋 진행 중인 공고")
    
    manager = get_sheets_manager()
    
    if manager is None:
        st.error("❌ Google Sheets에 연결할 수 없습니다. Secrets을 확인하세요.")
        st.stop()
    
    # Results Sheet 로드
    results_df = manager.read_results()
    
    if results_df.empty:
        st.info("📭 현재 진행 중인 공고가 없습니다. '검색 실행' 탭에서 검색을 시작하세요.")
    else:
        # D-day 컬럼 추가
        results_df['D-day'] = results_df['deadline'].apply(calculate_dday)
        
        # 기관별 필터
        col1, col2 = st.columns([1, 3])
        
        with col1:
            orgs = ['전체'] + sorted(results_df['organization'].dropna().unique().tolist())
            selected_org = st.selectbox("기관 필터", orgs)
        
        with col2:
            sort_by = st.selectbox("정렬", ['마감일 임박순', '최근 수집순', '기관명순'])
        
        # 필터링
        display_df = results_df.copy()
        
        if selected_org != '전체':
            display_df = display_df[display_df['organization'] == selected_org]
        
        # 정렬
        if sort_by == '마감일 임박순':
            display_df = display_df.sort_values('deadline')
        elif sort_by == '최근 수집순':
            display_df = display_df.sort_values('collected_date', ascending=False)
        else:
            display_df = display_df.sort_values('organization')
        
        # 표시
        st.dataframe(
            display_df[['organization', 'title', 'deadline', 'D-day', 'summary', 'url']],
            use_container_width=True,
            hide_index=True,
            column_config={
                'organization': '기관명',
                'title': '제목',
                'deadline': '마감일',
                'D-day': 'D-day',
                'summary': '요약',
                'url': st.column_config.LinkColumn('링크', display_text='🔗 바로가기')
            }
        )
        
        st.caption(f"총 {len(display_df)}건")
        
        # ===========================
        # 수동 분류 기능
        # ===========================
        
        st.subheader("📂 수동 분류")
        
        # 선택할 URL 목록
        selected_urls = st.multiselect(
            "분류할 공고 선택 (URL로 선택)",
            options=display_df['url'].tolist(),
            format_func=lambda x: display_df[display_df['url'] == x]['title'].values[0][:50] + '...' if len(display_df[display_df['url'] == x]['title'].values[0]) > 50 else display_df[display_df['url'] == x]['title'].values[0]
        )
        
        if selected_urls:
            st.info(f"📌 {len(selected_urls)}건 선택됨")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📦 선택 항목 → Archive 이동", type="secondary", use_container_width=True):
                    try:
                        manager.move_to_archive(selected_urls)
                        st.success(f"✅ {len(selected_urls)}건 Archive로 이동 완료!")
                        st.cache_resource.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 이동 실패: {e}")
            
            with col2:
                reason = st.text_input("제외 사유", value="관련 없음", key="exclude_reason")
                if st.button("🚫 선택 항목 → 제외 목록 추가", type="primary", use_container_width=True):
                    try:
                        manager.move_to_excluded(selected_urls, source='results', reason=reason)
                        st.success(f"✅ {len(selected_urls)}건 제외 목록에 추가 완료!")
                        st.cache_resource.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 제외 실패: {e}")
        
        st.divider()
        
        # 액션 버튼
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Obsidian 마크다운 복사
            md_content = export_to_obsidian(display_df)
            st.download_button(
                label="📋 Obsidian 마크다운 복사",
                data=md_content,
                file_name=f"공고목록_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown"
            )
        
        with col2:
            # Excel 다운로드
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                display_df.to_excel(writer, index=False, sheet_name='공고')
            
            st.download_button(
                label="📊 Excel 다운로드",
                data=buffer.getvalue(),
                file_name=f"공고목록_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


# ===========================
# 탭 2: 검토 및 검색
# ===========================

with tab2:
    st.header("📋 공고 검토 및 검색")
    
    manager = get_sheets_manager()
    
    # ---------------------------
    # Pending (검토 대기) 섹션
    # ---------------------------
    if manager:
        pending_df = manager.read_pending()
        
        if not pending_df.empty:
            st.warning(f"⚠️ **{len(pending_df)}건의 자동 검색 결과**가 검토 대기 중입니다.")
            
            with st.expander("📝 검토 대기 목록 열기", expanded=True):
                # 편집 가능한 테이블
                edited_pending_df = st.data_editor(
                    pending_df[['title', 'organization', 'deadline', 'summary', 'suggested_target', 'url']],
                    column_config={
                        'title': st.column_config.TextColumn('제목', width='large'),
                        'organization': st.column_config.TextColumn('기관', width='small'),
                        'deadline': st.column_config.TextColumn('마감일', width='small'),
                        'summary': st.column_config.TextColumn('요약', width='medium'),
                        'suggested_target': st.column_config.SelectboxColumn(
                            '분류',
                            options=['Results', 'Archive', 'Excluded'],
                            required=True,
                            width='small'
                        ),
                        'url': st.column_config.LinkColumn('URL', width='small', display_text='🔗')
                    },
                    hide_index=True,
                    use_container_width=True,
                    key='pending_editor'
                )
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("💾 검토 완료 및 저장", type="primary", use_container_width=True):
                        results_to_save = []
                        archive_to_save = []
                        excluded_to_save = []
                        
                        for idx, row in edited_pending_df.iterrows():
                            target = row['suggested_target']
                            record = {
                                'url': row['url'],
                                'title': row['title'],
                                'organization': row['organization'],
                                'deadline': row['deadline'],
                                'summary': row['summary'],
                                'collected_date': datetime.now().strftime('%Y-%m-%d')
                            }
                            
                            if target == "Results":
                                results_to_save.append(record)
                            elif target == "Archive":
                                record['term_months'] = ''
                                record['start_date'] = ''
                                record['next_expected_date'] = ''
                                archive_to_save.append(record)
                            elif target == "Excluded":
                                excluded_to_save.append({
                                    'url': record['url'],
                                    'title': record['title'],
                                    'reason': '수동 제외 (Pending 검토)'
                                })
                        
                        # 배치 저장
                        if results_to_save:
                            manager.append_results_batch(results_to_save)
                        if archive_to_save:
                            manager.append_archive_batch(archive_to_save)
                        if excluded_to_save:
                            manager.add_to_excluded_batch(excluded_to_save)
                        
                        # Pending 시트 비우기
                        manager.clear_pending()
                        manager.archive_expired()
                        
                        st.success(f"✅ 처리 완료! Results: {len(results_to_save)}건, Archive: {len(archive_to_save)}건, Excluded: {len(excluded_to_save)}건")
                        st.rerun()
                
                with col2:
                    if st.button("🗑️ 모두 무시하고 삭제", use_container_width=True):
                        manager.clear_pending()
                        st.warning("Pending 목록이 삭제되었습니다.")
                        st.rerun()
            
            st.divider()

    # ---------------------------
    # 수동 검색 섹션
    # ---------------------------
    st.subheader("🔍 수동 검색 실행")
    
    st.info("버튼을 클릭하면 Two-Track 검색 (VIP 기관 + 광역 키워드)을 즉시 실행합니다.")
    
    # 기존 데이터 현황 표시
    manager = get_sheets_manager()
    if manager:
        with st.expander("📊 기존 데이터 현황 (중복 체크용)", expanded=True):
            result_urls = manager.get_result_urls()
            archive_urls = manager.get_archive_urls()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("📌 현재 공고 (Results)", f"{len(result_urls)}건")
            col2.metric("📁 마감 공고 (Archive)", f"{len(archive_urls)}건")
            col3.metric("🔗 총 URL (중복 제외)", f"{len(result_urls) + len(archive_urls)}건")
            
            st.caption("위 URL들은 검색 결과에서 자동으로 제외됩니다.")
    
    if st.button("🚀 지금 검색 시작", type="primary", use_container_width=True):
        
        manager = get_sheets_manager()
        
        if manager is None:
            st.error("Google Sheets 연결 실패")
            st.stop()
        
        # 프로그레스 바
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: 네이버 검색
            status_text.text("Step 1/4: 네이버 검색 중...")
            progress_bar.progress(25)
            
            searcher = NaverSearcher()
            orgs = manager.read_config()
            
            search_results = searcher.search_all(orgs)
            
            st.success(f"✅ 검색 완료: {len(search_results)}건 수집")
            
            # SearchLog에 수집된 모든 결과 저장
            from datetime import datetime
            search_logs = []
            for item in search_results:
                search_logs.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'url': item.get('link', ''),
                    'title': item.get('title', ''),
                    'search_keyword': item.get('search_keyword', ''),
                    'search_query': item.get('search_query', ''),
                    'source': item.get('source', ''),
                    'stage': 'collected',
                    'reason': '수집됨'
                })
            
            if search_logs:
                manager.append_search_log(search_logs)
                st.info(f"📝 SearchLog에 {len(search_logs)}건 기록됨")

            
            # Step 2: 전처리
            status_text.text("Step 2/4: 전처리 중 (중복 제거, 키워드 필터링)...")
            progress_bar.progress(50)
            
            existing_urls = manager.get_result_urls() + manager.get_archive_urls()
            excluded_urls = list(manager.get_excluded_urls())
            preprocessor = Preprocessor(existing_urls, excluded_urls)
            
            filtered_results = preprocessor.process(search_results)
            
            stats = preprocessor.get_stats()
            filtered_items = preprocessor.get_filtered_items()
            st.info(f"전처리 완료: {stats['passed']}건 통과 (필터링률: {stats['filter_rate']:.1f}%)")
            
            if not filtered_results:
                st.warning("⚠️  신규 공고가 없습니다. 모두 중복이거나 필터링되었습니다.")
                progress_bar.progress(100)
                
                # 이메일 발송 옵션 (신규 없어도 요약 보고서 발송 가능)
                st.divider()
                st.subheader("📧 검색 결과 요약 이메일 발송")
                st.info(f"총 {stats['total']}건 검색 → 중복 {stats['duplicates']}건, 키워드 미충족 {stats['keyword_failed']}건으로 필터링됨")
                
                if st.button("📧 검색 결과 요약 보고서 발송", type="primary"):
                    try:
                        results = manager.read_results().to_dict('records')
                        archives = manager.read_archive().to_dict('records')
                        
                        sender = EmailSender()
                        if sender.send_search_summary(stats, filtered_items, [], results, archives):
                            st.success("✅ 검색 결과 요약 이메일 발송 완료!")
                        else:
                            st.error("❌ 이메일 발송 실패 (설정 확인 필요)")
                    except Exception as e:
                        st.error(f"❌ 이메일 발송 오류: {e}")
                
                st.stop()
            
            # Step 3: Gemini 분석
            status_text.text(f"Step 3/4: AI 분석 중 ({len(filtered_results)}건)...")
            progress_bar.progress(75)
            
            analyzer = GeminiAnalyzer()
            analyzed_results = analyzer.analyze_batch(filtered_results)
            
            st.success(f"✅ AI 분석 완료: {len(analyzed_results)}건 적합")
            
            # 필터링/거부 결과를 SearchLog에 기록
            filter_logs = []
            
            # 전처리기에서 필터링된 항목 기록
            filtered_items = preprocessor.get_filtered_items()
            for item in filtered_items:
                filter_logs.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'url': item.get('link', ''),
                    'title': item.get('title', ''),
                    'search_keyword': item.get('search_keyword', ''),
                    'search_query': item.get('search_query', ''),
                    'source': item.get('source', ''),
                    'stage': 'filtered',
                    'reason': item.get('filter_reason', '전처리 필터링')
                })
            
            # Gemini에서 거부된 항목 기록
            rejected_items = analyzer.get_rejected_items()
            for item in rejected_items:
                filter_logs.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'url': item.get('url', ''),
                    'title': item.get('title', ''),
                    'search_keyword': item.get('search_keyword', ''),
                    'search_query': item.get('search_query', ''),
                    'source': item.get('source', ''),
                    'stage': 'rejected',
                    'reason': item.get('rejection_reason', 'AI 거부')
                })
            
            # AI 통과한 항목 기록 (saved 단계)
            for item in analyzed_results:
                filter_logs.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'url': item.get('url', ''),
                    'title': item.get('original_title', ''),
                    'search_keyword': item.get('search_keyword', ''),
                    'search_query': item.get('search_query', ''),
                    'source': item.get('source', ''),
                    'stage': 'saved',
                    'reason': f"적합 판정 - 마감일: {item.get('deadline', 'N/A')}"
                })
            
            if filter_logs:
                manager.append_search_log(filter_logs)
                st.info(f"📝 SearchLog에 필터링/저장 결과 {len(filter_logs)}건 기록됨")
            
            # 상세 로그 표시
            with st.expander("📊 검색 상세 로그 보기", expanded=False):
                # 1. 수집된 URL 목록
                st.subheader("🔍 수집된 URL 목록")
                if search_results:
                    collected_df = pd.DataFrame([
                        {
                            '제목': r.get('title', '')[:50] + '...' if len(r.get('title', '')) > 50 else r.get('title', ''),
                            'URL': r.get('link', ''),
                            '검색어': r.get('search_query', 'N/A'),
                            '출처': r.get('source', 'N/A')
                        }
                        for r in search_results
                    ])
                    st.dataframe(collected_df, use_container_width=True)
                else:
                    st.info("수집된 결과가 없습니다.")
                
                # 2. 필터링된 항목
                st.subheader("🚫 필터링된 항목")
                if filtered_items:
                    filtered_df = pd.DataFrame([
                        {
                            '제목': f.get('title', '')[:40] + '...' if len(f.get('title', '')) > 40 else f.get('title', ''),
                            'URL': f.get('link', ''),
                            '사유': f.get('filter_reason', 'N/A')
                        }
                        for f in filtered_items
                    ])
                    st.dataframe(filtered_df, use_container_width=True)
                else:
                    st.info("필터링된 항목이 없습니다.")
                
                # 3. AI 거부 항목
                st.subheader("🤖 AI 거부 항목")
                if rejected_items:
                    rejected_df = pd.DataFrame([
                        {
                            '제목': r.get('title', '')[:40] + '...' if len(r.get('title', '')) > 40 else r.get('title', ''),
                            'URL': r.get('url', ''),
                            '사유': r.get('rejection_reason', 'N/A')
                        }
                        for r in rejected_items
                    ])
                    st.dataframe(rejected_df, use_container_width=True)
                else:
                    st.info("AI가 거부한 항목이 없습니다.")
            
            if not analyzed_results:
                st.warning("⚠️  적합한 공고가 없습니다.")
                progress_bar.progress(100)
                st.stop()
            
            # Step 4: Google Sheets 저장
            status_text.text("Step 4/4: 데이터베이스 업데이트 중...")
            progress_bar.progress(90)
            
            # 데이터 변환 (마감 여부에 따라 초기 분류)
            all_records = []  # 모든 공고
            today = datetime.now().date()
            
            for item in analyzed_results:
                deadline_str = item.get('deadline', '')
                is_expired = False
                
                # 1. is_past_announcement 플래그 확인 (키워드 자동 통과 시 설정됨)
                if item.get('is_past_announcement', False):
                    is_expired = True
                # 2. 마감일 기준 확인
                elif deadline_str:
                    try:
                        deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                        is_expired = deadline < today
                    except ValueError:
                        pass
                
                record = {
                    'url': item.get('url', ''),
                    'title': item.get('original_title', ''),
                    'organization': item.get('url', '').split('/')[2] if item.get('url') else 'Unknown',
                    'deadline': deadline_str,
                    'summary': item.get('summary', ''),
                    'collected_date': datetime.now().strftime('%Y-%m-%d'),
                    # 초기 분류 추천
                    'suggested_target': 'Archive' if is_expired else 'Results'
                }
                all_records.append(record)
            
            progress_bar.progress(100)
            status_text.text("✅ 분석 완료! 아래에서 분류를 확인/수정하고 저장하세요.")
            
            # 세션에 결과 저장 (분류 선택용)
            st.session_state.pending_records = all_records
            st.session_state.search_completed = True
            
        except Exception as e:
            st.error(f"❌ 검색 중 오류 발생: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # ===========================
    # 분류 및 저장 UI (검색 완료 후)
    # ===========================
    
    if st.session_state.get('search_completed') and st.session_state.get('pending_records'):
        st.divider()
        st.header("📂 검색 결과 분류")
        st.info("'분류' 컬럼에서 직접 선택하세요. 수정 후 '저장' 버튼을 클릭하면 됩니다.")
        
        records = st.session_state.pending_records
        
        # 데이터프레임 생성
        df = pd.DataFrame(records)
        
        # 분류 컬럼 이름 변경 (suggested_target → 분류)
        df = df.rename(columns={'suggested_target': '분류'})
        
        # 편집 가능한 테이블
        edited_df = st.data_editor(
            df[['title', 'organization', 'deadline', 'summary', '분류', 'url']],
            column_config={
                'title': st.column_config.TextColumn('제목', width='large'),
                'organization': st.column_config.TextColumn('기관', width='small'),
                'deadline': st.column_config.TextColumn('마감일', width='small'),
                'summary': st.column_config.TextColumn('요약', width='medium'),
                '분류': st.column_config.SelectboxColumn(
                    '분류',
                    options=['Results', 'Archive', 'Excluded'],
                    required=True,
                    width='small'
                ),
                'url': st.column_config.LinkColumn('URL', width='small', display_text='🔗')
            },
            hide_index=True,
            use_container_width=True,
            key='classification_editor'
        )
        
        # 저장 버튼
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 분류대로 저장", type="primary", use_container_width=True):
                manager = get_sheets_manager()
                
                results_to_save = []
                archive_to_save = []
                excluded_to_save = []
                
                for idx, row in edited_df.iterrows():
                    target = row['분류']
                    record = {
                        'url': row['url'],
                        'title': row['title'],
                        'organization': row['organization'],
                        'deadline': row['deadline'],
                        'summary': row['summary'],
                        'collected_date': datetime.now().strftime('%Y-%m-%d')
                    }
                    
                    if target == "Results":
                        results_to_save.append(record)
                    elif target == "Archive":
                        record['term_months'] = ''
                        record['start_date'] = ''
                        record['next_expected_date'] = ''
                        archive_to_save.append(record)
                    elif target == "Excluded":
                        excluded_to_save.append({
                            'url': record['url'],
                            'title': record['title'],
                            'reason': '수동 제외 (검색 결과에서)'
                        })
                
                # 배치 저장 (API 호출 최소화)
                if results_to_save:
                    manager.append_results_batch(results_to_save)
                if archive_to_save:
                    manager.append_archive_batch(archive_to_save)
                if excluded_to_save:
                    manager.add_to_excluded_batch(excluded_to_save)
                
                # 자동 아카이빙
                manager.archive_expired()
                
                st.success(f"✅ 저장 완료! Results: {len(results_to_save)}건, Archive: {len(archive_to_save)}건, Excluded: {len(excluded_to_save)}건")
                
                # 이메일 발송 세션에 저장 (선택적 발송용)
                st.session_state.email_ready = True
                st.session_state.saved_results_count = len(results_to_save)
                st.session_state.saved_archive_count = len(archive_to_save)
                
                # 세션 정리
                st.session_state.pending_records = None
                st.session_state.search_completed = False
                st.session_state.last_search_time = datetime.now()
        
        with col2:
            if st.button("🗑️ 결과 취소", use_container_width=True):
                st.session_state.pending_records = None
                st.session_state.search_completed = False
                st.warning("검색 결과가 취소되었습니다.")
                st.rerun()
    
    # 이메일 발송 섹션 (저장 완료 후)
    if st.session_state.get('email_ready'):
        st.divider()
        st.subheader("📧 일일 리포트 이메일 발송")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.info(f"저장 완료! Results: {st.session_state.get('saved_results_count', 0)}건, Archive: {st.session_state.get('saved_archive_count', 0)}건")
        
        with col2:
            if st.button("📧 리포트 발송", type="primary", use_container_width=True):
                try:
                    # 데이터 로드
                    manager = get_sheets_manager()
                    search_logs = manager.read_search_log()
                    results = manager.read_results().to_dict('records')
                    archives = manager.read_archive().to_dict('records')
                    
                    # 이메일 발송
                    sender = EmailSender()
                    if sender.send_daily_report(search_logs, results, archives):
                        st.success("✅ 일일 리포트 이메일 발송 완료!")
                    else:
                        st.error("❌ 이메일 발송 실패 (설정 확인 필요)")
                    
                    st.session_state.email_ready = False
                except Exception as e:
                    st.error(f"❌ 이메일 발송 오류: {e}")
        
        if st.button("❌ 이메일 발송 안 함"):
            st.session_state.email_ready = False
            st.rerun()
    
    # 마지막 검색 시간 표시
    if st.session_state.last_search_time:
        st.caption(f"마지막 검색: {st.session_state.last_search_time.strftime('%Y-%m-%d %H:%M:%S')}")


# ===========================
# 탭 3: 예측 알림
# ===========================

with tab3:
    st.header("📈 임기 만료 예측")
    
    manager = get_sheets_manager()
    
    if manager is None:
        st.error("Google Sheets 연결 실패")
        st.stop()
    
    # Archive 데이터 로드
    archive_df = manager.read_archive()
    
    if archive_df.empty:
        st.info("📭 아카이브 데이터가 없습니다. 마감된 공고가 축적되면 예측이 가능합니다.")
    else:
        predictor = Predictor(archive_df)
        opportunities = predictor.calculate_opportunities()
        
        if not opportunities:
            st.success("✅ 현재 30일 이내로 임박한 예상 공고가 없습니다.")
        else:
            st.warning(f"⚠️  {len(opportunities)}개 기관의 임기가 곧 만료됩니다!")
            
            # 카드 스타일로 표시
            for opp in opportunities:
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.markdown(f"### 🎯 {opp['organization']}")
                        st.caption(opp['message'])
                    
                    with col2:
                        st.metric("예상 공고일", opp['next_expected_date'])
                    
                    with col3:
                        st.metric("D-day", f"D-{opp['d_day']}", delta=f"{opp['term_months']}개월 임기")
                    
                    st.divider()


# ===========================
# 탭 4: 설정
# ===========================

with tab4:
    st.header("⚙️ 시스템 설정")
    
    manager = get_sheets_manager()
    
    # Google Sheets 링크
    st.subheader("📊 Google Sheets 관리")
    
    if manager and manager.config.get('google_sheets_id'):
        sheets_url = f"https://docs.google.com/spreadsheets/d/{manager.config['google_sheets_id']}/edit"
        st.markdown(f"[📝 Google Sheets 직접 편집하기]({sheets_url})")
        st.caption("Config 탭에서 감시 대상 기관을 추가/수정할 수 있습니다.")
    
    st.divider()
    
    # VIP 기관 목록 (Track A)
    st.subheader("🏛️ VIP 기관 목록 (Track A)")
    st.caption("이 기관들은 이름으로 직접 검색됩니다.")
    
    if manager:
        try:
            orgs = manager.read_config()
            if orgs:
                org_df = pd.DataFrame(orgs)
                st.dataframe(org_df, use_container_width=True)
            else:
                st.warning("등록된 VIP 기관이 없습니다. 아래에서 시트를 초기화하거나 새 기관을 추가하세요.")
            
            # 시트 초기화 버튼
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("🔄 기본 기관으로 초기화"):
                    manager.init_config_sheet()
                    st.success("✅ Config 시트 초기화 완료!")
                    st.rerun()
            
            # 새 기관 추가 (항상 표시)
            with st.expander("➕ 새 기관 추가", expanded=not orgs):
                with st.form("add_org_form"):
                    new_org = st.text_input("기관명", placeholder="예: 한국수자원공사")
                    new_keywords = st.text_input("키워드 (쉼표로 구분)", placeholder="예: 노무고문,노무자문")
                    new_active = st.checkbox("활성화", value=True)
                    
                    if st.form_submit_button("추가"):
                        if new_org and new_keywords:
                            manager.add_config_row({
                                'organization': new_org,
                                'keywords': new_keywords,
                                'active': new_active
                            })
                            st.success(f"✅ '{new_org}' 추가 완료!")
                            st.rerun()
                        else:
                            st.warning("기관명과 키워드를 입력하세요.")
                            
        except Exception as e:
            st.error(f"기관 목록 로드 실패: {e}")
    
    st.divider()
    
    # Track B 키워드 (Google Sheets에서 로드)
    st.subheader("🔍 검색 키워드 (Track B)")
    st.caption("이 키워드들은 VIP 기관과 조합하거나 단독으로 검색됩니다.")
    
    if manager:
        try:
            keywords = manager.read_keywords()
            if keywords:
                keyword_cols = st.columns(3)
                for i, kw in enumerate(keywords):
                    keyword_cols[i % 3].markdown(f"• {kw}")
            else:
                st.warning("등록된 키워드가 없습니다.")
            
            # 키워드 관리 버튼
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("🔄 기본 키워드로 초기화"):
                    manager.init_keywords_sheet()
                    st.success("✅ Keywords 시트 초기화 완료!")
                    st.rerun()
            
            # 새 키워드 추가
            with st.expander("➕ 새 키워드 추가", expanded=not keywords):
                with st.form("add_keyword_form"):
                    new_keyword = st.text_input("키워드", placeholder="예: 노무사 위촉")
                    
                    if st.form_submit_button("추가"):
                        if new_keyword:
                            manager.add_keyword(new_keyword, True)
                            st.success(f"✅ '{new_keyword}' 추가 완료!")
                            st.rerun()
                        else:
                            st.warning("키워드를 입력하세요.")
                            
        except Exception as e:
            st.error(f"키워드 로드 실패: {e}")
    
    st.divider()
    
    # API 연결 테스트
    st.subheader("🔌 API 연결 상태")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Google Sheets 테스트"):
            if manager and manager.test_connection():
                st.success("✅ 연결됨")
            else:
                st.error("❌ 연결 실패")
    
    with col2:
        if st.button("네이버 API 테스트"):
            try:
                searcher = NaverSearcher()
                result = searcher.search("테스트", display=1)
                if result:
                    st.success("✅ 연결됨")
                else:
                    st.warning("⚠️  응답 없음")
            except:
                st.error("❌ 연결 실패")
    
    with col3:
        if st.button("Gemini API 테스트"):
            try:
                analyzer = GeminiAnalyzer()
                st.success("✅ 연결됨")
            except:
                st.error("❌ 연결 실패")
    
    st.divider()
    
    # 아카이빙 수동 실행
    st.subheader("🗄️  데이터 관리")
    
    if st.button("마감된 공고 아카이빙"):
        if manager:
            manager.archive_expired()
            st.success("✅ 아카이빙 완료!")
            st.rerun()
    
    st.caption("마감일이 지난 공고를 Results → Archive로 이동합니다.")


# ===========================
# 푸터
# ===========================

st.divider()
st.caption("AI 노무고문 공고 모니터링 시스템 v1.0 | Powered by Gemini 1.5 Flash")
