# PROGRESS.md

## 현재 상태

모든 마일스톤(M0~M19) 완료. `commerce-decision-demo` GCP 프로젝트(계정 `ysm@subproject.kr`)에 실제로 배포했고, 전체 파이프라인(데이터 생성 → GCS → BigQuery → metrics → decisions → Gemini → snapshot → Cloud Run 앱, 매일 실행되는 Cloud Scheduler → Cloud Run Job 자동화)을 라이브로 실행하고 검증했다. Cloud Scheduler의 실제 무인 트리거도 1회성 테스트로 직접 확인했다. 모든 GCP 자동화는 프로젝트 기본 서비스 계정이 아니라 전용 최소권한 서비스 계정 3개로 실행된다.

**저장소와 앱 모두 공개 전환 완료(2026-09-23)**:
- GitHub 저장소 공개: `https://github.com/yimsemin/commerce-decision-demo` (계정 `yimsemin`). 설명/토픽/홈페이지 URL 설정 완료.
- 랜딩페이지 공개: `https://yimsemin.github.io/commerce-decision-demo/` (GitHub Pages, `main` 브랜치 `docs/` 폴더 서빙).
- Cloud Run 앱 공개: `https://commerce-decision-app-6uj2ksurka-du.a.run.app` -- 익명 접근 200 확인됨(인증 불필요).
- `main`은 `develop`을 `git checkout --orphan`으로 재압축한 상태로 유지되며, 원격에 푸시되어 있다. `develop`은 계속 로컬 전용 작업 브랜치.

이어서 작업할 사람은 **"새 에이전트/다른 컴퓨터에서 이어가기"**부터 읽을 것.

## 마일스톤

- [x] M0 저장소 부트스트랩
- [x] M1 합성 데이터 생성기 (4개 시나리오 심음)
- [x] M2 Cloud Storage + BigQuery 적재 -- 클라우드 검증
- [x] M3 KPI/메트릭 레이어 -- 클라우드 검증(SQL == pandas 미러)
- [x] M4 결정적 이슈 탐지 규칙
- [x] M5 경영 의사결정 웹앱(Streamlit/Cloud Run) -- 클라우드 검증(인증 전용)
- [x] M6 Gemini 해석 레이어 -- 클라우드 검증(실제 `gemini-2.5-flash` 호출 성공)
- [x] M7 예약 리프레시 자동화(Cloud Scheduler/Cloud Run Job) -- 클라우드 검증(실제 무인 트리거 확인)
- [x] M8 End-to-end 검증 (`docs/verification.md`)
- [x] M20 확장 구조(Lens 모듈화) + 임계값 조정 (로컬 검증 완료, **클라우드 재배포는 아직 안 함** -- 아래 "확장 구조" 참고)
- [x] M9 포트폴리오 README/스크린샷/아키텍처 다이어그램
- [x] M10 실제 GCP 라이브 배포
- [x] M11 최소권한 IAM 리팩터 + 스케줄러 실발화 테스트 + 정리
- [x] M12 Git 워크플로 확정(브랜치/커밋 규칙/AI 트레일러 금지, 훅으로 강제) + 문서 한글화·압축
- [x] M13 GitHub 비공개 저장소 생성 + `main`(단일 초기 커밋) 푸시
- [x] M14 공개용 내러티브 랜딩페이지 (`docs/index.html`) -- 발표자 없이도 4개 시나리오를 직접 골라 끝까지 따라갈 수 있는 인터랙티브 페이지. 로컬 검증 완료(이미지 로드, mermaid 렌더링, 모바일 레이아웃)
- [x] M15 저장소 공개 전환 + GitHub Pages 활성화 -- 라이브 확인됨
- [x] M16 Cloud Run 공개 접근 전환 -- 프로젝트 한정 org policy 오버라이드 + `allUsers` invoker 바인딩, 익명 접근 라이브 확인됨
- [x] M17 앱 i18n(한국어/영어) + 비교 시점(기준일) 선택 -- 스냅샷을 여러 기준일로 미리 계산해 사이드바에서 선택, 앱은 여전히 정적 파일만 읽음
- [x] M18 랜딩페이지 어절 단위 줄바꿈(`word-break: keep-all`) + 라이트/다크 모드 토글
- [x] M19 인사이트 강화 1~3 -- 이슈별 예상 매출 영향($), 기준일 히스토리 기반 추세 차트, 같은 심각도 내 $영향 기준 2차 정렬

## 핵심 기술 결정

| 결정 | 선택 | 이유 |
|---|---|---|
| 데이터 | 합성 데이터만 사용 | 실제 데이터 의존성 회피 |
| 근거(source of truth) | BigQuery SQL이 결정적 계산, Gemini는 해석만 | AI 해석은 근거가 있고 감사 가능해야 함 |
| GCS CLI | `gcloud storage` (`gsutil` 아님) | `gsutil`은 레거시 |
| 인프라 스크립트 | 재현 가능한 프로비저닝 스크립트로 명명, "IaC"라 부르지 않음 | Terraform은 필요 생길 때까지 범위 밖 |
| 공개 읽기 경로 | 리프레시가 `app_snapshot.json`을 만들어 GCS에 저장, 앱은 이것만 읽음 | 공개 트래픽이 BigQuery/Gemini를 직접 호출하지 않게 함 |
| GCP 리전 | `asia-northeast3`(서울) | 오너 지시 |
| Gemini 모델/위치 | `gemini-2.5-flash` @ Vertex AI `global` | 문서 조사로 지원 확인; 데이터가 합성이라 리전 제약 불필요 |
| Python | 3.14.5, `.python-version`에 고정 | 로컬에 있는 유일한 버전 |
| 패키지 구조 | `src/commerce_lab/` (src-layout), 기능별 서브패키지 | 표준적, importpath 충돌 방지 |
| 데이터 생성 의존성 | pandas + numpy만 (Faker 없음) | 결정성을 직접 통제 |
| 합성 데이터 기간 | 고정: 2026-05-25~2026-09-21(120일), 최근 30일 vs 이전 30일 | 실행 시각과 무관하게 출력이 고정됨 |
| 고객 도메인 | 별도 생성 대신 orders.csv에서 파생 | PROJECT.md §5 요구사항 |
| BigQuery 데이터셋 | `raw`/`staging`/`metrics` 3개 | PROJECT.md §4 계층 구조 반영 |
| 재고 리필 정책 | 일반 SKU는 실수요 추종형 반응 재입고, 시나리오 SKU만 예외 | 초기엔 고정 재입고량이라 23/24 SKU가 오탐(실제 버그, 수정함) |
| Gemini 실패 처리 | 절대 예외를 던지지 않고 `None`으로 저하 | 외부 API 실패가 파이프라인/앱을 깨면 안 됨 |
| 앱/리프레시 컨테이너 분리 | `Dockerfile`(앱, 최소 의존성) vs `Dockerfile.job`(리프레시, BigQuery/Gemini SDK 포함) | 상시 구동 앱에 불필요한 SDK를 넣지 않음 |
| **서비스 계정** | 전용 최소권한 SA 3개(`cloudbuild-deployer`, `commerce-app-runtime`, `commerce-refresh-runtime`), 프로젝트 기본 SA는 쓰지 않음 | 2024년 이후 GCP 기본 동작/권장사항; 오너가 "우회 말고 정식 방법"을 명시적으로 요청 |
| BigQuery 데이터셋 권한 | `bq add-iam-policy-binding -d`는 allowlist 필요해서 막힘 → 데이터셋 access ACL(`bq update`)로 부여 | BigQuery의 오래되고 여전히 표준적으로 지원되는 방법 |
| Cloud Build 소스/로그 버킷 | 자동 생성되는 `_cloudbuild` 버킷 대신 전용 스테이징 버킷(`${PROJECT}-build-staging`) 사용 | 권한을 미리, 명확하게 스코프하기 위해 |
| Cloud Run 공개 접근 | 프로젝트 한정 org policy 오버라이드로 공개 전환 완료 | 조직 전체 정책은 유지하면서 이 프로젝트만 예외 허용 -- 자세한 내용은 "공개 전환 실행 기록" |
| **Git 워크플로** | 브랜치 `main`/`develop`, 커밋 접두어(`feat:`/`fix:`/`docs:` 등) 강제, AI 어트리뷰션 트레일러 절대 금지 -- `.githooks/commit-msg`로 기술적으로 강제 | 오너 지시(2026-09-23); 상세 규칙은 `CLAUDE.md` "Git" 섹션 |
| 문서 언어/분량 | 모든 문서 한국어, 세션 로그성 서술은 압축·삭제 | 오너 지시(2026-09-23) |
| 라이선스 | MIT (`LICENSE`) | 저장소는 비공개지만 라이선스는 미리 셋업 |
| 랜딩페이지 호스팅 | GitHub Pages, `main` 브랜치 `docs/` 폴더 서빙 (빌드 없음) | 기존 정적사이트 툴링이 전혀 없어서 가장 단순한 경로 선택; `docs/screenshots/`를 상대경로로 그대로 재사용 가능 |
| 랜딩페이지 스크린샷 | Playwright로 로컬 앱에서 시나리오당 2장(증거+판단) 신규 캡처, `docs/screenshots/scenarios/` | 기존 6장(탭 전체 화면)은 특정 이슈를 짚어주지 못해서 별도 캡처 필요; 목업 아님(실제 로컬 실행) |
| 랜딩페이지 이미지 로딩 | `loading="lazy"` 미사용 | Streamlit 스타일 탭 전환(스크롤이 아니라 `display:none` 토글)과 네이티브 lazy-load가 상호작용 나쁨 -- 비활성 패널의 이미지가 아예 로드되지 않는 버그 확인, 제거로 해결 |
| 랜딩페이지 한글 줄바꿈 | `word-break: keep-all` | 기본값은 음절 단위로 아무 데서나 줄바꿈 가능 -- 어절(공백) 단위로만 끊기도록 강제 |
| 랜딩페이지 테마 | localStorage에 저장하는 라이트/다크 토글, 최초 방문 시 OS `prefers-color-scheme` 따름 | 별도 서버/계정 없이 방문자별로 기억되면 충분 |
| 앱 i18n | 결정 카드 문장(headline/likely_drivers/possible_action)은 `issue_type`+`affected`+`supporting_kpi`(이미 스냅샷에 있는 구조화된 사실)로부터 언어별로 새로 렌더링(`app/i18n.py`), 파이프라인/스키마는 변경 없음 | 사실과 서술을 분리하는 기존 원칙과 일치; `kpi_to_monitor` 등 식별자는 번역하지 않음 |
| Gemini 요약과 언어 | 한국어 화면은 항상 결정적 대체 요약(`fallback_executive_summary(lang="ko")`) 사용, Gemini 실제 호출은 영어 1회만 유지 | Gemini 호출을 언어별로 2배 늘리지 않음; AI가 잘못 번역/왜곡할 여지 자체를 차단 |
| 비교 시점(기준일) 선택 | `build_snapshot_history()`가 최신 기준일 + 15일 간격 과거 기준일 최대 5개를 모두 미리 계산해 `app_snapshot.json` 하나에 번들, 앱은 사이드바 슬라이더로 그중 하나를 선택할 뿐 | "앱은 절대 BigQuery/Gemini를 직접 호출하지 않는다"는 기존 아키텍처 불변식을 지키면서 시점 조절을 지원하는 가장 단순한 방법; window_days(30일)는 심어진 시나리오 임계값과 맞물려 있어 고정, 기준일만 이동 |
| 예상 매출 영향(`estimated_revenue_impact`) | 마케팅 효율 악화/매출 하락 규칙에서만 계산(이미 있는 KPI만으로 직접 유도 가능), 품절/과잉재고/고객구성 변화는 `None`(원가·판매가·주문귀속 데이터 없음) | 방어 불가능한 추정치를 만들지 않음 -- 계산 근거가 없으면 그냥 비워둠 |
| 이슈 정렬(top_issues) | 심각도가 여전히 1차 정렬 기준, 같은 등급 안에서만 `estimated_revenue_impact` 절대값으로 2차 정렬 | 심각도는 결정적 규칙이 내린 판단이라 $값으로 뒤집지 않음; 등급 내 우선순위만 보강 |
| KPI 추세 차트 | 결정 카드마다 `kpi_trend()`로 히스토리의 모든 기준일에서 같은 세그먼트/SKU 값을 조회해 미니 라인차트 표시(2개 미만이면 숨김) | M17에서 만든 다중 기준일 스냅샷을 재활용 -- 새 계산/저장 없이 기존 데이터로 추세를 보여줌 |
| **예산 하드캡** | 기존 결제 예산(당시 ₩5,000, 알림 전용 -- 이후 ₩20,000으로 상향)에 Pub/Sub 토픽을 연결하고, 100% 도달 시 프로젝트 결제 자체를 끊는 Cloud Function(`budget-hardcap`, 2nd gen)을 추가 | 오너 지시(2026-09-23) -- 예산 알림은 이메일만 보낼 뿐 지출을 막지 않아서, "예상치 못한 비용 급증/예산 외 결제" 가능성에 대한 실질적 안전장치가 없었음. 결제를 끄는 방식은 프로젝트 단위라 Cloud Run 앱을 포함한 모든 과금 리소스가 함께 정지되는 트레이드오프가 있고, 이건 오너에게 사전 설명 후 진행 |
| 하드캡 함수의 Billing API 호출 방식 | `google-cloud-billing` 클라이언트 라이브러리 대신 `google-auth`+`requests`로 REST 직접 호출 | 클라이언트 라이브러리의 grpc/cryptography 의존성 체인이 Cloud Functions buildpack 빌드에서 원인 불명 실패(로그에 상세 원인이 안 남는 빌드 단계 실패)를 일으켜, 더 가벼운 대안으로 교체해 해결 |
| 하드캡 함수의 빌드 서비스 계정 | Cloud Functions gen2 기본값(프로젝트 기본 Compute SA) 대신 기존 `cloudbuild-deployer` 재사용(`--build-service-account`) | 프로젝트 기본 Compute SA는 이 프로젝트에서 의도적으로 권한이 전혀 없음(다른 SA들과 같은 이유) -- gen2 함수 빌드가 이 SA를 쓰면서 별다른 로그 없이 조용히 실패했음. 새 SA에 권한을 넓히는 대신 이미 최소권한으로 세팅된 배포자 SA를 재사용하고, 함수 전용 자동 생성 리소스(`gcf-artifacts` 저장소, `gcf-v2-sources-*` 버킷)에만 추가로 권한을 부여 |
| Gemini 보수적 제한 | `max_output_tokens=400`, `temperature=0.2`, thinking 예산 0, 요청 타임아웃 30초·재시도 없음, 저장 요약 최대 1500자, 환경변수 `GEMINI_ENABLED=false`로 호출 전체 차단(킬스위치) | 오너 지시(2026-09-24): Gemini 경로가 남용/과금 표적이 되기 쉬움. 호출은 스케줄된 리프레시 잡에서만(앱은 절대 호출 안 함), 프롬프트는 파이프라인이 계산한 구조화 사실만 사용해 사용자 입력이 끼어들 여지가 없음. 라이브 잡 실행으로 정상 동작 확인 |
| 다른 AI로 복사·붙여넣기 | Overview 탭 expander에 복사 버튼이 있는 프롬프트(`app/copy_prompt.py`, 한/영) -- 선택된 기준일의 상위 이슈 사실만 담음 | 오너 아이디어(2026-09-24): 인사이트 해석을 Gemini에 한정하지 않고 ChatGPT/Claude 등으로 이어가게 함. 앱이 외부 AI를 대신 호출하지 않으므로 추가 비용·공격면 없음 |
| 예산 알림 임계값 | 실제 지출 50/90/100% + 예상 지출(forecast) 100% | 급증을 결제 집계 지연 전에 더 일찍 인지. 하드캡 함수는 실제 지출 ≥ 예산일 때만 동작하므로 forecast 알림은 이메일 경고 역할 |
| Artifact Registry 정리 정책 | 최근 3개 버전 유지 + untagged 즉시 삭제 + 14일 지난 버전 삭제(`scripts/artifact_cleanup_policy.json`, 3개 저장소 공통 적용) | 재배포마다 이미지가 무기한 누적돼 스토리지 비용이 조용히 늘어나는 것을 방지 -- 재배포 직후 직전 버전으로 되돌릴 여지는 남기되 무제한 보관은 하지 않음 |
| 하드캡 함수의 시그니처 | `def stop_billing(cloud_event)` 대신 `def stop_billing(event, context)` (레거시 "background function" 시그니처) | `gcloud functions deploy --trigger-topic`(신규 `--trigger-topic-project`류가 아닌 구식 플래그)으로 배포한 gen2 함수는 CloudEvent가 아니라 2-인자 레거시 형식으로 호출됨을 실제 배포 후 런타임 에러(`TypeError: takes 1 positional argument but 2 were given`)로 확인 |

임계값(재고 소진 7/60일, 이슈 규칙 등)과 그 근거는 `docs/kpi_definitions.md`, `docs/decision_rules.md`에 있다. 데모용 기본값이며 실제 벤치마크 튜닝은 아니다.

## 배포된 리소스 (라이브, 2026-09-23 기준)

계정 `ysm@subproject.kr`, 프로젝트 `commerce-decision-demo`, 리전 `asia-northeast3`, 결제 계정 `015716-BC65BE-E667BC`.

| 리소스 | 이름 | 비고 |
|---|---|---|
| GCS 버킷 | `commerce-decision-demo-data`, `commerce-decision-demo-build-staging` | 데이터 버킷(raw CSV + snapshot) / Cloud Build 스테이징 |
| BigQuery 데이터셋 | `raw`, `staging`, `metrics` | `sql/` 참고 |
| Artifact Registry | `commerce-decision-app`, `commerce-lab-refresh` | 앱/리프레시 이미지 |
| Cloud Run 서비스 | `commerce-decision-app` | `commerce-app-runtime` SA로 실행, 현재 인증 전용 |
| Cloud Run Job | `commerce-lab-refresh` | `commerce-refresh-runtime` SA로 실행 |
| Cloud Scheduler | `commerce-lab-refresh` | `0 6 * * *`, `Asia/Seoul` |
| 결제 예산 알림 | "commerce-decision-demo safety budget" | ₩20,000(2026-09-24 상향), 실지출 50/90/100% + 예상지출 100% 이메일 알림 + Pub/Sub 하드캡 연동 |
| Pub/Sub 토픽 | `budget-hardcap-alerts` | 예산이 이 토픽으로 알림을 publish하도록 연결됨 |
| Cloud Function (2nd gen) | `budget-hardcap` | 예산 100% 도달 시 프로젝트 결제를 비활성화 -- 자세한 내용은 "예산 하드캡" 결정 항목 |
| 서비스 계정 | `cloudbuild-deployer`, `commerce-app-runtime`, `commerce-refresh-runtime`, `budget-hardcap-runtime` | 각각 필요한 버킷/데이터셋/저장소/리소스에만 최소 권한 |

**해체:** `GCP_PROJECT_ID=commerce-decision-demo GCS_BUCKET=commerce-decision-demo-data ./scripts/teardown_gcp.sh --yes` (되돌릴 수 없음). 예산 알림은 남겨둬도 무해하므로 삭제 대상 아님. 오너 승인 없이 실행하지 말 것.

## Git 워크플로

상세 규칙은 `CLAUDE.md` "Git" 섹션이 유일한 출처다. 요약:
- `develop`에서 단계별 커밋(`feat:`/`fix:`/`docs:`/`chore:` 등 접두어 필수). 로컬에만 존재하며 **원격에는 올리지 않는다.**
- `main`은 GitHub에 공개되는 브랜치이며, 항상 커밋 1개(현재 `feat: initial commit`)만 유지한다. `develop`에서 작업이 쌓이면 `git checkout --orphan`으로 새 단일 커밋을 만들어 `main`을 교체하는 방식으로 다시 압축한다(`git merge --squash`는 기존 `main` 히스토리 위에 얹히므로 커밋이 2개가 되어 쓰지 않는다).
- Claude/Anthropic 어트리뷰션 트레일러 절대 금지 -- `.githooks/commit-msg`가 위반 시 커밋 자체를 거부한다.
- 새 클론/머신마다 한 번 `git config core.hooksPath .githooks` 실행 필요(이 설정 자체는 버전 관리되지 않음).
- 오너의 그 순간의 명시적 승인 없이는 절대 푸시하지 않는다.
- **원격**: `https://github.com/yimsemin/commerce-decision-demo` (비공개). 2026-09-23에 생성 + `main` 최초 푸시 완료. `develop`은 푸시하지 않았다.

## 새 에이전트 / 다른 컴퓨터에서 이어가기

- **맥락의 출처는 이 5개 파일뿐이다:** `START_PROMPT.txt`(오너의 최초 지시, 원래 의도), `PROJECT.md`(제품 스펙), `CLAUDE.md`(운영 규칙 + Git 규칙), `README.md`(완성된 결과물 설명), 이 파일. 다른 곳에 숨겨진 맥락은 없다.
- **현재 상태:** 핵심 구현은 전부 끝났고 로컬/클라우드 모두 검증됨. 미완성 핵심 작업 없음.
- **라이브 GCP 리소스:** 위 "배포된 리소스" 참고. 이미 존재하므로 재생성하지 말 것 -- `scripts/provision_*.sh`는 멱등적이라 재실행해도 안전하지만, 먼저 `gcloud run services list` 등으로 존재를 확인할 것.
- **자격 증명은 머신별로 새로 설정해야 한다:** GCP는 `gcloud auth login` + `gcloud auth application-default login`(계정: `ysm@subproject.kr`), GitHub는 `gh auth login`(계정: `yimsemin`)이 각 머신에서 새로 필요하다. 이 저장소에는 어떤 자격 증명도 커밋되어 있지 않다.
- **Cloud SDK 설치 직후, 이미 열려 있던 터미널에서는 `gcloud`가 "command not found"일 수 있다.** 설치 프로그램(winget)은 사용자 PATH에 정상 등록하지만(레지스트리 레벨, `[Environment]::GetEnvironmentVariable('PATH','User')`로 확인 가능), 이미 실행 중이던 셸은 그 변경을 반영하지 못한다(OS가 PATH를 프로세스 시작 시점에 한 번만 읽기 때문). 해결책은 그 세션 안에서 매번 `$env:Path += ";$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin"`를 앞에 붙이는 임시방편이 아니라, **새 터미널 창을 여는 것**이다 -- 설치 이후에 새로 뜬 터미널/새 대화 세션은 별도 조치 없이 `gcloud`가 바로 잡힌다.
- **새 머신에서 이어가려면**: `git clone https://github.com/yimsemin/commerce-decision-demo.git` 후 `git checkout -b develop`으로 로컬 작업 브랜치를 새로 만든다(원격에 `develop`이 없으므로). `git config core.hooksPath .githooks`를 반드시 실행할 것.
- **남은 것은 전부 오너의 판단 사항**이지 기술적 블로커가 아니다(아래 참고).
- 작업 방식은 `CLAUDE.md`의 "역할"/"작업 방식"/"오너와의 상호작용" 섹션을 그대로 따른다: 일상적 기술 결정은 스스로, 계정/보안/비용/범위 관련만 오너에게 확인.

## 공개 전환 실행 기록 (2026-09-23)

- **저장소**: `gh repo edit --visibility public` + description/homepage/topics 설정 + `gh api .../pages`로 Pages 활성화(`main`/`docs`).
- **Cloud Run 공개 접근**: `iam.allowedPolicyMemberDomains` 조직 기본값(`organizations/70403340587`)은 전혀 건드리지 않았다. 대신:
  1. `roles/orgpolicy.policyAdmin`을 `ysm@subproject.kr`에 **조직 레벨**로 부여 -- GCP 제약상 이 역할 자체가 프로젝트 단위로는 부여 불가(`add-iam-policy-binding`이 `INVALID_ARGUMENT: Role ... is not supported for this resource`로 거부됨, 우회 아니라 정식 제약).
  2. 그 권한으로 **`projects/commerce-decision-demo`에만** `iam.allowedPolicyMemberDomains` 정책 오버라이드(`allowAll: true`)를 생성. 조직 전체 정책은 `updateTime` 불변으로 확인.
  3. `gcloud run services add-iam-policy-binding commerce-decision-app --member=allUsers --role=roles/run.invoker`. 정책 전파에 ~2분 소요(첫 시도는 `FAILED_PRECONDITION`으로 실패, 재시도로 성공).
  4. 익명 상태로 실제 접속 확인(200, 로그인 없이 KPI/Decisions 렌더링됨).
- IAM 바인딩/권한 부여 명령은 Claude Code 자동 모드의 classifier가 자동 차단해서 전부 오너가 직접 PowerShell에서 실행했다.
- `docs/index.html`의 CTA 버튼에 실제 Cloud Run URL 반영, `main` 재압축(`git checkout --orphan`) 후 재푸시로 GitHub Pages에도 반영.

## 확장 구조 (Lens 모듈화, 2026-09-24, 오너 요청)

**요청:** 경영진이 "이 관점으로도 보고 싶다"고 할 수 있으니 추가하기 쉬운 형태로 모듈화하고, 커스터마이징 가능한 부분을 열어 달라. 오너 답변: 커스터마이징 주체는 개발자/운영자 + 경영진 둘 다, 새 관점은 새 데이터 소스까지 포함.

**결정과 이유:**
- **Lens = 모듈 하나**(`src/commerce_lab/lenses/`). `compute`(KPI 섹션) / `detect`(규칙) / `params`(임계값) / `render`(탭) / `localizers`(한영 문장) / `data_sources`(새 테이블)를 한 파일에 둔다. 기존 `decisions/rules.py`와 `i18n.py`의 이슈별 문장, `main.py`의 탭 렌더러를 각 관점 모듈로 옮겼다. 스냅샷의 섹션 키(`sales`/`marketing`/`customer`/`inventory`)와 모양은 그대로다.
- **`detect`는 스냅샷 섹션만 읽는다.** 덕분에 앱이 저장된 지표만으로 경영진이 바꾼 임계값으로 이슈를 다시 판정할 수 있다(세션 한정, BigQuery/Gemini 호출 없음). 원칙 "KPI는 결정적, Gemini는 해석만"과 "앱은 스냅샷만 읽는다"를 깨지 않는다. 판매 속도 산정 기간처럼 `compute`가 쓰는 값은 `runtime=False`라 설정 파일 + 리프레시로만 바꾼다.
- **설정은 `config/lab.toml`**(stdlib `tomllib`, 새 의존성 없음): 활성 관점 목록(=탭 순서)과 임계값 덮어쓰기. 알 수 없는 키는 리프레시를 즉시 실패시킨다. 스냅샷에 `lenses`/`params`가 기록되어 앱은 설정 파일을 읽지 않는다. `Dockerfile.job`이 `config/`를 복사한다.
- **새 데이터 소스:** `DataSource`(컬럼 정의 + 합성 생성 함수). 소스별 전용 RNG(`Random(f"{seed}:{name}")`)를 써서 기존 5개 데이터셋이 바이트 단위로 그대로다(테스트로 확인). 클라우드 적재 시 `raw.<name>`을 `CREATE TABLE IF NOT EXISTS`로 만든다.
- **호환성:** 스냅샷 `schema_version` 1→2(`lenses`, `params`, 이슈별 `lens` 추가). 이전 v1 스냅샷도 앱이 그대로 렌더링한다(테스트로 확인) -- 앱을 먼저 재배포해도 안전하다.
- **범위 절제:** 예시용 신규 관점(반품률 등)은 프로덕션에 넣지 않았다(명시된 의사결정 질문이 뒷받침하지 않으므로). 대신 임시 `returns` 관점으로 전체 경로(새 데이터 소스→스냅샷→이슈→설정 덮어쓰기→앱 재판정)를 `tests/test_lenses/`에서 검증한다. 가이드는 `docs/extending.md`.
- 테스트 83 → 98개, 전부 통과. 로컬 브라우저로 앱(탭, 임계값 조정 패널, Decisions 필터)도 확인.

**클라우드 반영 (2026-09-24):** refresh Job 재빌드/배포 → 수동 1회 실행 성공(v2 스냅샷 업로드) → 앱 재배포(리비전 `00009`) → 라이브에서 확인. 이어서 UX 개선 후 앱/Job 재배포.

**UX 점검 후 개선(같은 날):** (1) 임계값 입력을 숫자 박스(Enter 필요, 적용 여부 불명확)에서 **슬라이더**(즉시 적용)로 교체. (2) 조정 중임을 알리는 **상단 배너**(어떤 값이 기본값에서 얼마로 바뀌었는지 + 되돌리기 버튼). (3) 슬라이더 문구에 방향/의미를 명시("ROAS 변화율 ≤ 이 값이면 high"). (4) 한국어 탭 이름 현지화(개요/성과/마케팅/고객/재고/의사결정). (5) Decisions 탭에 "N건 중 M건 표시"와 Overview와 같은 정렬. 한/영 모두 라이브·로컬 확인, 관리자 시나리오(config로 관점 부분 활성 + 임계값 기본값 변경)를 ko/en AppTest로 검증(`test_admin_config_...`). **접힘 안내 + 스크린샷 갱신(같은 날, 오너 요청):** 접힌 영역(근거 KPI, 전체 SKU, 임계값 패널, AI 프롬프트)의 제목에 "클릭하여 펼치기"와 내용 요약을 넣었다. 특히 근거 KPI는 이전의 정체불명 `{...}` 대신 "근거 KPI 보기 (지표 5개 · 클릭하여 펼치기)"로 표시된다. 스크린샷 14장을 현재 UI로 다시 캡처하고 `thresholds.png`를 추가했다 -- **새 설치 없이** 이미 venv에 있던 Playwright + 설치된 Microsoft Edge(`channel="msedge"`)로 촬영(스크립트는 저장소에 두지 않음). 시나리오 decision 이미지는 근거 KPI를 펼친 상태로 찍었다. 랜딩페이지(GitHub Pages)에는 `main` 재압축 + 푸시가 있어야 반영되며, 푸시는 오너 승인 대기.

## 남은 작업

1. **예산 하드캡 활성화 완료를 위한 오너 실행 1단계 남음 (2026-09-23)**: `budget-hardcap-runtime` SA에 결제 계정 레벨 IAM 역할(`roles/billing.user`)을 부여해야 하드캡이 실제로 작동한다. IAM 바인딩이라 Claude Code 자동 모드 classifier가 차단하므로 오너가 직접 실행:
   ```
   gcloud billing accounts add-iam-policy-binding 015716-BC65BE-E667BC \
     --member="serviceAccount:budget-hardcap-runtime@commerce-decision-demo.iam.gserviceaccount.com" \
     --role="roles/billing.user"
   ```
   실행 전까지는 예산 알림 이메일은 정상 발송되지만, 100% 도달 시 결제를 끄는 부분만 권한 오류로 동작하지 않는다(= 실패해도 조용히 아무 일도 안 하는 게 아니라 함수 로그에 에러가 남는 방식).
2. **지속 비용 (2026-09-23, 오너 결정)**: 무료체험판(카드 연결, 예산 소진 시 실제 결제 전환됨을 오너가 콘솔에서 확인)이 3개월 뒤 종료된다는 전제 하에, 사용량이 GCP Always Free 등급 범위 안이라면 리소스를 계속 운영하기로 결정했다. `scripts/teardown_gcp.sh --yes`로 정리하는 옵션은 보류. 예상치 못한 비용 급증에 대한 안전장치는 위 "예산 하드캡" 항목으로 대응한다. 트라이얼 자연 종료 시점(대략 2026-12-23 전후)의 자동 처리 방식(자동 유료 전환 vs 자동 정지)은 GCP 공식 동작이 불확실하므로, 그 시점이 다가오면 별도로 재점검 필요.
3. **테이블 컬럼명 번역 여부 (오너 판단 보류, 2026-09-23)**: Performance/Inventory/Decisions 등 여러 화면에서 `sku_id`, `net_revenue[...]`, `days_of_cover` 같은 메트릭 식별자가 한국어 화면에서도 원문 그대로 노출된다. [i18n.py](src/commerce_lab/app/i18n.py) 상단 주석에 "메트릭 식별자는 의도적으로 번역하지 않는다"는 기존 설계 결정이 명시돼 있어 이번에는 건드리지 않았다. 다만 처음 보는 방문자 기준 "포트폴리오 인상"을 더 다듬고 싶다면 재검토할 여지가 있다 -- 포트폴리오 스토리에 영향을 주는 판단이라 다음에 진행하려면 오너 확인 먼저.
4. **`global` Vertex AI 엔드포인트가 서비스 계정에서만 막혔던 정확한 원인 미규명**: `us-central1`로 바꿔서 실용적으로 해결은 했지만(위 "해결됨" 참고), 어떤 조직 정책이 `global`에서만 SA를 막았는지는 오너 계정으로도 조회 권한이 없어 끝내 못 봤다. 나중에 `global`이 꼭 필요해지면(예: 데이터 레지던시 요구 등) 조직 관리자 권한으로 다시 조사 필요.

### 해결됨 (2026-09-23)

- **Gemini 호출이 라이브에서 403으로 계속 실패하던 문제 -- 해결.** `commerce-refresh-runtime` SA가 `roles/aiplatform.user`를 프로젝트 레벨로 보유하고 있었는데도 `aiplatform.endpoints.predict`가 `.../locations/global/publishers/google/models/gemini-2.5-flash`에서 매 실행마다 `403 PERMISSION_DENIED`. 오너 계정(`ysm@subproject.kr`) 사용자 자격증명으로는 같은 엔드포인트가 정상 응답해서 SA에 한정된 문제로 좁혀졌고, 콘솔에서 직접 확인한 결과 거부(Deny) 정책도 VPC Service Controls도 원인이 아니었다(둘 다 이 프로젝트/조직에 설정 자체가 없음). **원인은 `global` 위치였다** -- [`GEMINI_LOCATION`을 `global`에서 `us-central1`로 변경](src/commerce_lab/gemini/config.py)하고 refresh job 이미지를 재빌드/재배포해 실행한 결과, 403 없이 정상적으로 요약이 생성됨을 라이브에서 확인(`app_snapshot.json`의 `gemini_summary`가 더 이상 `null`이 아님). 정확히 어떤 조직 정책이 `global`에서만 SA를 막았는지는 오너 계정으로도 조회 권한이 없어 규명하지 못했지만, 실용적으로는 리전 변경으로 해결.
- **Cloud Run Job 이미지가 최신 소스보다 오래돼 있었던 문제 -- 같은 재배포로 해결.** 위 재빌드/재배포 이후 로그 출력 문구가 현재 `refresh.py` `main()`과 일치함을 확인(`N period anchor(s), M decision item(s) at latest (date)`).
- **Performance/Marketing/CAC 테이블의 raw 숫자(예: `1.1405673774668819`, `11668.07`) -- 해결.** `st.dataframe`에 `column_config`(dollar / `%.2f` / `%+.1f%%`)를 적용해 `$11,668.07`, `-59.9%` 형태로 정리([main.py](src/commerce_lab/app/main.py)). 이건 Cloud Run **앱** 서비스(`Dockerfile`) 쪽 코드라서 위 refresh **job**(`Dockerfile.job`) 재배포와는 별개로 `commerce-decision-app` 서비스를 재빌드/재배포해야 했고, 실제로 진행해서 라이브 반영 확인함(리비전 `commerce-decision-app-00007-rzq`).
