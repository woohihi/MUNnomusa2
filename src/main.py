"""
CLI 모드 진입점
GitHub Actions에서 Streamlit 없이 검색 파이프라인만 실행
"""

import sys
from datetime import datetime
import time

from .sheets_manager import GoogleSheetManager
from .naver_search import NaverSearcher
from .preprocessor import Preprocessor
from .gemini_analyzer import GeminiAnalyzer
from .email_sender import EmailSender


def main():
    """검색 파이프라인 실행"""
    
    print("=" * 60)
    print("AI 노무고문 공고 모니터링 - 자동 검색")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Google Sheets 연결
        print("🔌 Step 1: Google Sheets 연결 중...")
        manager = GoogleSheetManager()
        
        orgs = manager.read_config()
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
            manager.append_search_log(search_logs)
            print(f"📝 SearchLog: {len(search_logs)}건 수집 로그 저장 완료")
        
        # Step 3: 전처리
        print("\n🔧 Step 3: 전처리 시작 (중복 제거 및 키워드 필터링)...")
        existing_urls = manager.get_result_urls() + manager.get_archive_urls()
        # Excluded URL도 가져와서 필터링에 반영 (중복 수집 방지)
        excluded_urls = list(manager.get_excluded_urls())
        
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
            manager.append_search_log(filtered_logs)
            print(f"📝 SearchLog: {len(filtered_logs)}건 필터링 로그 저장 완료")
        
        if not filtered_results:
            print("⚠️  신규 공고 없음 (모두 중복 또는 필터링됨). 종료합니다.")
            
            # 신규 공고는 없지만, 요약 이메일은 보낼지 여부 결정
            # 여기서는 종료하지만 필요시 이메일 전송 로직 추가 가능
            return 0
        
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
            manager.append_search_log(pre_analysis_logs)
            print(f"📝 SearchLog: {len(pre_analysis_logs)}건 분석 대기 로그 저장 (Safety Net)")
        
        # Step 4: Gemini 분석
        print("\n🤖 Step 4: Gemini AI 분석 시작...")
        analyzer = GeminiAnalyzer()
        analyzed_results = analyzer.analyze_batch(filtered_results)
        
        print(f"✅ AI 분석 완료: {len(analyzed_results)}건 적합\n")
        
        # [Log] 분석 결과 업데이트
        post_analysis_logs = []
        
        # 1. AI 거부 항목
        rejected_items = analyzer.get_rejected_items()
        for item in rejected_items:
            post_analysis_logs.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'url': item.get('url', ''),
                'title': item.get('title', ''),
                'search_keyword': item.get('search_keyword', ''),
                'search_query': item.get('search_query', ''),
                'source': item.get('source', ''),
                'stage': 'rejected',
                'reason': item.get('rejection_reason', 'AI 거부')
            })
            
        # 2. AI 적합 항목 (Pending으로 이동)
        for item in analyzed_results:
            post_analysis_logs.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'url': item.get('url', ''),
                'title': item.get('original_title', ''),
                'search_keyword': item.get('search_keyword', ''),
                'search_query': item.get('search_query', ''),
                'source': item.get('source', ''),
                'stage': 'saved',  # Pending에 저장됨을 의미
                'reason': f"적합 판정 - 마감일: {item.get('deadline', 'N/A')}"
            })
            
        if post_analysis_logs:
            manager.append_search_log(post_analysis_logs)
            print(f"📝 SearchLog: {len(post_analysis_logs)}건 최종 분석 결과 로그 저장 완료")
        
        if not analyzed_results:
            print("⚠️  적합한 공고 없음. 종료합니다.")
            return 0
        
        # Step 5: Pending Sheet 저장 (검토 대기)
        print("\n💾 Step 5: 검토 대기 시트(Pending) 저장 중...")
        
        pending_records = []
        
        for item in analyzed_results:
            # 기관명 추출 (URL or Hint)
            org_hint = item.get('organization_hint', '')  # Track A의 경우
            if not org_hint:
                # URL 도메인 등으로 추측하거나 Gemini가 추출한 정보 사용 가능하면 좋음
                # 현재는 url의 도메인 부분만 간단히 사용하거나 Unknown
                if item.get('url'):
                    try:
                        org_hint = item['url'].split('/')[2]
                    except:
                        org_hint = 'Unknown'
                else:
                    org_hint = 'Unknown'
            
            # AI 추천 분류 (기본값)
            # 마감일이 지났으면 Archive 추천
            suggested = 'Results'
            deadline_str = item.get('deadline')
            if deadline_str:
                try:
                    deadline_date = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                    if deadline_date < datetime.now().date():
                        suggested = 'Archive'
                except:
                    pass

            # 과거 공고 플래그 확인
            if item.get('is_past_announcement'):
                suggested = 'Archive'
            
            record = {
                'url': item.get('url', ''),
                'title': item.get('original_title', ''),
                'organization': org_hint,
                'deadline': item.get('deadline', ''),
                'summary': item.get('summary', ''),
                'suggested_target': suggested,
                'collected_date': datetime.now().strftime('%Y-%m-%d')
            }
            pending_records.append(record)
        
        manager.append_pending_batch(pending_records)
        
        print(f"✅ {len(pending_records)}건 Pending 저장 완료\n")
        
        # Step 6: 검색 결과 요약 이메일 발송
        print("📧 Step 6: 검색 결과 요약 이메일 발송 중...")
        sender = EmailSender()
        
        if sender.enabled:
            # 현재 상태 로드 (통계용)
            results = manager.read_results().to_dict('records')
            archives = manager.read_archive().to_dict('records')
            
            success = sender.send_search_summary(stats, filtered_items, rejected_items, results, archives)
            
            if success:
                print("✅ 이메일 발송 완료\n")
            else:
                print("⚠️  이메일 발송 실패\n")
        else:
            print("⚠️  이메일 설정 비활성화 (sender_email 없음)\n")
        
        # 최종 요약
        print("=" * 60)
        print("✅ 작업 완료! (관리자 검토 대기 중)")
        print(f"- 수집: {len(search_results)}건")
        print(f"- 1차 필터링 후: {len(filtered_results)}건")
        print(f"- AI 분석 적합: {len(analyzed_results)}건")
        print(f"- Pending 저장: {len(pending_records)}건 (Streamlit에서 검토 필요)")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 치명적인 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
