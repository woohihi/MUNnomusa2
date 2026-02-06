"""
CLI 모드 진입점
GitHub Actions에서 Streamlit 없이 검색 파이프라인만 실행
"""

import sys
from datetime import datetime

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
        print("🔌 Google Sheets 연결 중...")
        manager = GoogleSheetManager()
        
        orgs = manager.read_config()
        print(f"✅ {len(orgs)}개 기관 로드 완료\n")
        
        # Step 2: 네이버 검색
        print("🔍 네이버 검색 시작...")
        searcher = NaverSearcher()
        search_results = searcher.search_all(orgs)
        print(f"✅ 검색 완료: {len(search_results)}건\n")
        
        if not search_results:
            print("⚠️  검색 결과 없음. 종료합니다.")
            return 0
        
        # Step 3: 전처리
        print("🔧 전처리 시작...")
        existing_urls = manager.get_result_urls() + manager.get_archive_urls()
        preprocessor = Preprocessor(existing_urls)
        
        filtered_results = preprocessor.process(search_results)
        stats = preprocessor.get_stats()
        
        print(f"✅ 전처리 완료: {stats['passed']}건 통과\n")
        
        if not filtered_results:
            print("⚠️  신규 공고 없음 (모두 중복 또는 필터링됨). 종료합니다.")
            return 0
        
        # Step 4: Gemini 분석
        print("🤖 Gemini AI 분석 시작...")
        analyzer = GeminiAnalyzer()
        analyzed_results = analyzer.analyze_batch(filtered_results)
        
        print(f"✅ AI 분석 완료: {len(analyzed_results)}건 적합\n")
        
        if not analyzed_results:
            print("⚠️  적합한 공고 없음. 종료합니다.")
            return 0
        
        # Step 5: Pending Sheet 저장 (검토 대기)
        print("💾 검토 대기 시트(Pending) 저장 중...")
        
        pending_records = []
        
        for item in analyzed_results:
            # 기관명 추출
            org_hint = item.get('organization_hint', '')  # Track A의 경우
            if not org_hint:
                org_hint = item.get('organization', 'Unknown')
            
            # AI 추천 분류 (기본값)
            suggested = 'Results'
            
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
        print("📧 검색 결과 요약 이메일 발송 중...")
        sender = EmailSender()
        
        if sender.enabled:
            # 현재 상태 로드
            results = manager.read_results().to_dict('records')
            archives = manager.read_archive().to_dict('records')
            
            # 통계 정보
            filtered_items = preprocessor.get_filtered_items()
            rejected_items = analyzer.rejected_items
            
            success = sender.send_search_summary(stats, filtered_items, rejected_items, results, archives)
            
            if success:
                print("✅ 이메일 발송 완료\n")
            else:
                print("⚠️  이메일 발송 실패\n")
        else:
            print("⚠️  이메일 설정 비활성화\n")
        
        # 최종 요약
        print("=" * 60)
        print("✅ 작업 완료! (검토 대기 상태)")
        print(f"- 검색: {len(search_results)}건")
        print(f"- 필터링: {stats['passed']}건 통과 ({stats['filter_rate']:.1f}% 제거)")
        print(f"- AI 분석: {len(analyzed_results)}건 적합")
        print(f"- Pending 저장: {len(pending_records)}건")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
