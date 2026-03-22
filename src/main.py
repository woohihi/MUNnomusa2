"""
CLI 모드 진입점
GitHub Actions에서 Streamlit 없이 검색 파이프라인만 실행
"""

import sys
import argparse
from datetime import datetime
import time

from .sheets_manager import GoogleSheetManager
from .naver_search import NaverSearcher
from .preprocessor import Preprocessor
from .gemini_analyzer import GeminiAnalyzer
from .email_sender import EmailSender
from .telegram_sender import send_search_summary as tg_summary, send_error_alert as tg_error


def _reanalyze_pending(limit: int = 0) -> int:
    """
    Pending 시트의 '검토중' 항목을 URL 재방문 + 첨부파일 추출 후 Gemini 재분석.
    '적합' / '거절' / '보류' 상태 항목은 건드리지 않음.
    """
    from .web_scraper import WebScraper
    from .result_processor import ResultProcessor

    print("=" * 60)
    print("Pending 재분석 모드")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        manager = GoogleSheetManager()
        df = manager.read_pending()

        if df.empty:
            print("ℹ️  Pending 시트가 비어있습니다.")
            return 0

        # '검토중' 상태만 재분석 (이미 결정된 항목은 제외)
        decided_statuses = {'적합', '거절', '보류'}
        status_col = df['status'] if 'status' in df.columns else df.get('status', '')
        if not hasattr(status_col, 'isin'):
            import pandas as pd
            status_col = pd.Series(['검토중'] * len(df))
        mask_reanalyze = ~status_col.isin(decided_statuses)
        to_reanalyze = df[mask_reanalyze].to_dict('records')
        decided = df[~mask_reanalyze].to_dict('records')

        print(f"📋 전체 Pending: {len(df)}건")
        print(f"   ├─ 재분석 대상 (검토중): {len(to_reanalyze)}건")
        print(f"   └─ 유지 (적합/거절/보류): {len(decided)}건\n")

        if not to_reanalyze:
            print("ℹ️  재분석 대상이 없습니다.")
            return 0

        if limit > 0:
            to_reanalyze = to_reanalyze[:limit]
            print(f"⚠️  테스트 모드: {limit}건만 재분석\n")

        # Pending 행을 GeminiAnalyzer가 기대하는 형식으로 변환
        items = []
        for row in to_reanalyze:
            items.append({
                'title': row.get('title', ''),
                'link':  row.get('url', ''),
                'description': '',          # 재크롤링으로 채울 예정
                'search_keyword': row.get('search_keyword', ''),
                'search_query':   row.get('search_query', ''),
                'source':         row.get('source', ''),
                'organization_hint': row.get('organization', ''),
            })

        # Step 1: URL 재방문 + 첨부파일(PDF/HWP/HWPX) 텍스트 추출
        # enrich_items는 description이 짧을 때만 크롤링하므로, 재분석에선 직접 fetch
        print("🌐 Step 1: URL 재방문 및 첨부파일 추출 중...")
        scraper = WebScraper()
        enriched = 0
        for i, item in enumerate(items, 1):
            url = item.get('link', '')
            print(f"  [{i}/{len(items)}] {url[:70]}")
            text = scraper.fetch(url)
            if text:
                item['description'] = text
                enriched += 1
        print(f"✅ {enriched}/{len(items)}건 본문 보강 완료\n")

        # Step 2: Gemini 재분석
        print("🤖 Step 2: Gemini 재분석 중...")
        analyzer = GeminiAnalyzer()
        analyzed = analyzer.analyze_batch(items)
        rejected = analyzer.get_rejected_items()
        print(f"✅ 적합 {len(analyzed)}건 / 거부 {len(rejected)}건\n")

        # Step 3: 결과를 Pending 포맷으로 변환
        new_pending_records = ResultProcessor.process_results(analyzed)

        # Step 4: Pending 시트 재작성
        # decided(이미 결정된) 항목은 그대로 유지, 재분석 결과로 교체
        print("💾 Step 3: Pending 시트 업데이트 중...")
        manager.clear_pending()
        manager.init_pending_sheet()  # 헤더 정리 (중복 컬럼 제거)

        # decided 항목 먼저 복원
        if decided:
            manager.append_pending_batch(decided)

        # 재분석 결과 저장
        if new_pending_records:
            # Archive 대상은 Archive로, 나머지는 Pending에
            batch_archive = [r for r in new_pending_records if r.get('suggested_target') == 'Archive']
            batch_pending = [r for r in new_pending_records if r.get('suggested_target') != 'Archive']

            if batch_archive:
                manager.append_archive_batch(batch_archive)
                print(f"📦 과거 공고 {len(batch_archive)}건 → Archive 이동")
            if batch_pending:
                manager.append_pending_batch(batch_pending)

        print(f"\n{'=' * 60}")
        print(f"✅ 재분석 완료!")
        print(f"   - 재분석: {len(to_reanalyze)}건")
        print(f"   - Gemini 적합: {len(analyzed)}건 (Pending 갱신)")
        print(f"   - Gemini 거부: {len(rejected)}건 (Pending에서 제거)")
        print(f"   - 기존 결정 유지: {len(decided)}건")
        print(f"{'=' * 60}")
        return 0

    except Exception as e:
        print(f"\n❌ 재분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """검색 파이프라인 실행"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='Gemini 분석 건수 제한 (0=무제한)')
    parser.add_argument('--orgs', type=int, default=0, help='검색할 기관 수 제한 (0=무제한)')
    parser.add_argument('--approve', action='store_true',
                        help='Pending 시트의 status 컬럼을 읽어 승인/거절 처리만 수행')
    parser.add_argument('--reset', action='store_true',
                        help='모든 데이터 시트 초기화 (Config 제외)')
    parser.add_argument('--reanalyze', action='store_true',
                        help='Pending 시트의 검토중 항목을 URL 재방문 + 첨부파일 추출 후 Gemini 재분석')
    args = parser.parse_args()

    # 시트 초기화 모드
    if args.reset:
        print("=" * 60)
        print("⚠️  시트 전체 초기화")
        print("대상: Results, Archive, Pending, SearchLog, Excluded")
        print("Config 시트는 유지됩니다.")
        print("=" * 60)
        confirm = input("계속하려면 'yes' 입력: ").strip().lower()
        if confirm != 'yes':
            print("취소되었습니다.")
            return 0
        manager = GoogleSheetManager()
        manager.reset_all_data()
        print("\n✅ 초기화 완료")
        return 0

    # 승인 처리 전용 모드
    if args.approve:
        print("=" * 60)
        print("Pending 검토 결과 처리")
        print("=" * 60)
        manager = GoogleSheetManager()
        result = manager.process_pending_approvals()
        print(f"\n완료: 적합 {result['approved']}건 → Results | "
              f"거절 {result['rejected']}건 → Excluded | "
              f"유지 {result['kept']}건")
        return 0

    # Pending 재분석 모드
    if args.reanalyze:
        return _reanalyze_pending(limit=args.limit)

    print("=" * 60)
    print("AI 노무고문 공고 모니터링 - 자동 검색")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Google Sheets 연결
        print("🔌 Step 1: Google Sheets 연결 중...")
        manager = GoogleSheetManager()

        # SearchLog 자동 정리 (30일 이전 행 삭제)
        manager.cleanup_search_log(keep_days=30)

        orgs = manager.read_config()
        if args.orgs > 0:
            orgs = orgs[:args.orgs]
            print(f"⚠️  테스트 모드: {args.orgs}개 기관만 검색")
        print(f"✅ {len(orgs)}개 기관 로드 완료\n")
        
        # Step 2: 네이버 검색
        print("🔍 Step 2: 네이버 검색 시작...")
        searcher = NaverSearcher()
        search_results = searcher.search_all(orgs)
        print(f"✅ 검색 완료: {len(search_results)}건 수집\n")
        
        if not search_results:
            print("⚠️  검색 결과 없음. 종료합니다.")
            return 0
            
        # [Log] 수집된 결과 SearchLog 저장
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
            try:
                manager.append_search_log(search_logs)
                print(f"📝 SearchLog: {len(search_logs)}건 수집 로그 저장 완료")
            except Exception as e:
                print(f"⚠️ SearchLog 저장 실패 (검색은 계속 진행): {e}")
        
        # Step 3: 전처리
        print("\n🔧 Step 3: 전처리 시작 (중복 제거 및 키워드 필터링)...")
        existing_urls = []
        excluded_urls = []

        try:
            # Results + Archive + Pending 모두 중복 제거 대상
            # → Pending 포함으로 분할 실행 시 재분석 방지 (--orgs N 배치 실행 지원)
            existing_urls = (
                manager.get_result_urls()
                + manager.get_archive_urls()
                + list(manager.get_pending_urls())
            )
        except Exception as e:
            print(f"⚠️ URL 목록 조회 실패, 빈 목록으로 진행: {e}")

        # Excluded URL도 가져와서 필터링에 반영 (중복 수집 방지)
        try:
            excluded_urls = list(manager.get_excluded_urls())
        except Exception as e:
            print(f"⚠️ 제외 URL 조회 실패, 빈 목록으로 진행: {e}")
        
        preprocessor = Preprocessor(existing_urls, excluded_urls)
        
        filtered_results = preprocessor.process(search_results)
        stats = preprocessor.get_stats()
        
        print(f"✅ 전처리 완료: {stats['passed']}건 통과 (필터링: {stats['filter_rate']:.1f}%)\n")
        
        # [Log] 필터링된 항목 SearchLog 저장
        filtered_logs = []
        filtered_items = preprocessor.get_filtered_items()
        for item in filtered_items:
            filtered_logs.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'url': item.get('link', ''),
                'title': item.get('title', ''),
                'search_keyword': item.get('search_keyword', ''),
                'search_query': item.get('search_query', ''),
                'source': item.get('source', ''),
                'stage': 'filtered',
                'reason': item.get('filter_reason', '전처리 필터링')
            })
            
        if filtered_logs:
            try:
                manager.append_search_log(filtered_logs)
                print(f"📝 SearchLog: {len(filtered_logs)}건 필터링 로그 저장 완료")
            except Exception as e:
                print(f"⚠️ SearchLog 저장 실패: {e}")
        
        if not filtered_results:
            print("⚠️  신규 공고 없음 (모두 중복 또는 필터링됨). 종료합니다.")
            return 0

        # Step 3.5: 본문 크롤링 (snippet이 부족한 항목 보강)
        print("\n🌐 Step 3.5: 공고 본문 크롤링 중...")
        from .web_scraper import WebScraper
        scraper = WebScraper()
        enriched_count = scraper.enrich_items(filtered_results)
        print(f"✅ 크롤링 완료: {enriched_count}건 본문 보강 ({len(filtered_results)}건 중)\n")

        # [Log] 분석 전 안전장치 (Pre-Analysis Logging)
        # 분석 중에 죽더라도 'analyzing' 상태로 남겨서 추적 가능하게 함
        pre_analysis_logs = []
        for item in filtered_results:
            pre_analysis_logs.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'url': item.get('link', ''),
                'title': item.get('title', ''),
                'search_keyword': item.get('search_keyword', ''),
                'search_query': item.get('search_query', ''),
                'source': item.get('source', ''),
                'stage': 'analyzing',  # 분석 시작 표시
                'reason': '1차 필터 통과 (분석 대기)'
            })
            
        if pre_analysis_logs:
            try:
                manager.append_search_log(pre_analysis_logs)
                print(f"📝 SearchLog: {len(pre_analysis_logs)}건 분석 대기 로그 저장 (Safety Net)")
            except Exception as e:
                print(f"⚠️ SearchLog 저장 실패: {e}")
        
        # Step 4+5: Gemini 분석 → 100건 단위 즉시 저장 (중간 저장으로 중단 시 손실 방지)
        print("\n🤖 Step 4: Gemini AI 분석 시작...")
        analyzer = GeminiAnalyzer()
        from .result_processor import ResultProcessor

        items_to_analyze = filtered_results
        if args.limit > 0:
            items_to_analyze = filtered_results[:args.limit]
            print(f"⚠️  테스트 모드: {args.limit}건만 분석 ({len(filtered_results)}건 중)")

        BATCH_SIZE = 100  # 100건마다 중간 저장
        total = len(items_to_analyze)
        analyzed_results = []
        auto_archive_records = []
        pending_records = []
        rejected_items = []
        post_analysis_logs = []

        for batch_start in range(0, total, BATCH_SIZE):
            batch = items_to_analyze[batch_start:batch_start + BATCH_SIZE]
            batch_end = batch_start + len(batch)
            print(f"\n💡 [{batch_start+1}~{batch_end}/{total}건] 분석 중...")

            batch_results = analyzer.analyze_batch(batch)
            analyzed_results.extend(batch_results)
            rejected_items.extend(analyzer.get_rejected_items())

            # 분석 결과 즉시 저장
            print(f"💾 [{batch_start+1}~{batch_end}] 중간 저장 중...")
            batch_records = ResultProcessor.process_results(batch_results)
            batch_archive = [r for r in batch_records if r.get('suggested_target') == 'Archive']
            batch_pending = [r for r in batch_records if r.get('suggested_target') != 'Archive']

            if batch_archive:
                manager.append_archive_batch(batch_archive)
                auto_archive_records.extend(batch_archive)
            if batch_pending:
                manager.append_pending_batch(batch_pending)
                pending_records.extend(batch_pending)

            # SearchLog 기록
            for item in analyzer.get_rejected_items():
                post_analysis_logs.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'url': item.get('url', ''), 'title': item.get('title', ''),
                    'search_keyword': item.get('search_keyword', ''),
                    'search_query': item.get('search_query', ''),
                    'source': item.get('source', ''),
                    'stage': 'rejected', 'reason': item.get('rejection_reason', 'AI 거부')
                })
            for item in batch_results:
                post_analysis_logs.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'url': item.get('url', ''), 'title': item.get('original_title', ''),
                    'search_keyword': item.get('search_keyword', ''),
                    'search_query': item.get('search_query', ''),
                    'source': item.get('source', ''),
                    'stage': 'saved',
                    'reason': f"적합 판정 - 마감일: {item.get('deadline', 'N/A')}"
                })

            print(f"✅ [{batch_start+1}~{batch_end}] 저장 완료: Archive {len(batch_archive)}건, Pending {len(batch_pending)}건")

        if post_analysis_logs:
            try:
                manager.append_search_log(post_analysis_logs)
                print(f"📝 SearchLog: {len(post_analysis_logs)}건 최종 분석 결과 로그 저장 완료")
            except Exception as e:
                print(f"⚠️ SearchLog 저장 실패: {e}")

        print(f"\n✅ AI 분석 전체 완료: 적합 {len(analyzed_results)}건 (Archive {len(auto_archive_records)}, Pending {len(pending_records)})\n")

        # Step 5: (중간 저장으로 이미 완료됨)
        print("💾 Step 5: 분석 결과 저장 완료 (중간 저장 처리됨)")

        # Step 6: 검색 결과 요약 이메일 발송
        print("📧 Step 6: 검색 결과 요약 이메일 발송 중...")
        sender = EmailSender()

        if sender.enabled:
            results = manager.read_results().to_dict('records')
            archives = manager.read_archive().to_dict('records')

            success = sender.send_search_summary(
                stats, filtered_items, rejected_items,
                results, archives,
                pending_items=pending_records,
            )

            if success:
                print("✅ 이메일 발송 완료\n")
            else:
                print("⚠️  이메일 발송 실패\n")
        else:
            print("⚠️  이메일 설정 비활성화 (sender_email 없음)\n")

        # Step 7: 텔레그램 알림 전송
        print("📱 Step 7: 텔레그램 알림 전송 중...")
        tg_ok = tg_summary(
            stats=stats,
            pending_count=len(pending_records),
            archive_count=len(auto_archive_records),
            pending_items=pending_records,
        )
        if tg_ok:
            print("✅ 텔레그램 알림 전송 완료\n")
        else:
            print("⚠️  텔레그램 알림 스킵 (설정 없음 또는 전송 실패)\n")

        # 최종 요약
        print("=" * 60)
        print("✅ 작업 완료! (관리자 검토 대기 중)")
        print(f"- 수집: {len(search_results)}건")
        print(f"- 1차 필터링 후: {len(filtered_results)}건")
        print(f"- AI 분석 적합: {len(analyzed_results)}건")
        print(f"- Archive 직접 저장: {len(auto_archive_records)}건 (과거 공고)")
        print(f"- Pending 저장: {len(pending_records)}건 (검토 필요)")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 치명적인 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        tg_error(f"치명적인 오류 발생\n{e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
