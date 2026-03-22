# Gemini API 유료 플랜 설정 가이드 (Pay-as-you-go)

사용자님이 보유하신 **"Gemini Advanced (월 2.9만원)"** 구독은 **챗봇(gemini.google.com)** 전용이며, **API(개발용)**와는 별개입니다.  
API 사용량 제한(429 Error)을 해결하기 위해서는 **Google Cloud Platform(GCP)**에서 결제 계정을 연결해야 합니다.

비용은 충격적으로 저렴합니다. (Flash 모델 기준)

## 💰 1. 비용 구조 (Gemini 2.0 Flash)
- **입력 (Prompt):** 100만 토큰당 약 **$0.10 (약 140원)**
- **출력 (Response):** 100만 토큰당 약 **$0.40 (약 560원)**
- **실제 예상 비용:** 공고 4,000건을 매일 분석해도 **월 5,000원 미만**일 가능성이 높습니다.
- **무료 구간:** 유료 설정을 하더라도 매월 일정량까지는 무료입니다.

---

## 🚀 2. 설정 방법 (3분 소요)

### Step 1: Google Cloud Console 접속
1. [Google Cloud Console](https://console.cloud.google.com/)에 접속합니다.
2. API 키를 발급받았던 Google 계정으로 로그인합니다.
3. 상단 프로젝트 선택창에서 현재 API 키를 사용 중인 프로젝트를 선택합니다.

### Step 2: 결제 계정 연결
1. 좌측 메뉴에서 **[결제 (Billing)]**를 클릭합니다.
2. "결제 계정 연결(Link a billing account)" 버튼을 누릅니다.
3. "결제 계정 만들기"를 선택하고 해외 결제 가능한 신용카드를 등록합니다.
   - *팁: Google은 봇 확인을 위해 $1 가승인 후 취소할 수 있습니다.*

### Step 3: API 할당량 확인
1. 결제 연결 후, 좌측 메뉴에서 **[API 및 서비스]** > **[할당량(Quotas)]**으로 이동합니다.
2. "Generative Language API"를 검색합니다.
3. `Requests per minute` 제한이 늘어났는지 확인합니다. (기본 15 RPM → 1000+ RPM으로 증가)

---

## ⚡ 3. 코드 설정 변경 (유료 전환 후)
결제 설정이 완료되면 `src/config.py`에서 속도 제한을 해제하여 분석 속도를 비약적으로 높일 수 있습니다.

```python
# src/config.py

# 변경 전 (무료)
GEMINI_RATE_LIMIT_DELAY = 4.0  # 4초 대기

# 변경 후 (유료)
GEMINI_RATE_LIMIT_DELAY = 0.1  # 0.1초 (사실상 대기 없음)
```

> **유의사항:** 결제 연동 후에도 안전을 위해 Google Cloud Console의 [예산 및 알림] 메뉴에서 "월 $10 알림"을 설정해두시는 것을 권장합니다.
