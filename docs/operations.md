# 운영

현재 라이브 리소스, 운영 방법, 핵심 설계 결정. 제품 스펙은 [PROJECT.md](PROJECT.md), 규칙은 [AGENTS.md](../AGENTS.md).

## 현재 상태

모든 구성이 GCP 프로젝트 `commerce-decision-demo`(리전 `asia-northeast3`)에 배포되어 매일 자동 갱신된다. 데이터 생성 → GCS → BigQuery → KPI 계산(BigQuery) → 이슈 탐지 → Gemini 해석 → 스냅샷 → 앱 전 구간을 라이브로 검증했다([verification.md](verification.md)).

| 공개 주소 | 내용 |
|---|---|
| https://github.com/yimsemin/commerce-decision-demo | 저장소(공개) |
| https://yimsemin.github.io/commerce-decision-demo/ | 랜딩페이지. GitHub Pages가 `main`의 `docs/`를 서빙(빌드 없음) |
| https://commerce-decision-app-6uj2ksurka-du.a.run.app | 앱. 로그인 없이 접근 |

## 라이브 리소스

| 리소스 | 이름 | 비고 |
|---|---|---|
| GCS 버킷 | `commerce-decision-demo-data`, `commerce-decision-demo-build-staging` | 데이터(`raw/commerce/날짜/`, `snapshot/`) / Cloud Build 스테이징 |
| BigQuery | `raw`, `staging`, `metrics` | `metrics`: 테이블 함수 7개(`sales_summary`, `sales_by_brand_channel`, `sales_by_sku`, `marketing_by_segment`, `cac_by_channel`, `customer_mix`, `inventory_risk`)와 뷰 1개(`repeat_purchase_rate`) |
| Artifact Registry | `commerce-decision-app`, `commerce-lab-refresh` | 최근 3개 버전만 유지(`scripts/artifact_cleanup_policy.json`) |
| Cloud Run 서비스 | `commerce-decision-app` | 읽기 전용 SA `commerce-app-runtime` |
| Cloud Run Job | `commerce-lab-refresh` | SA `commerce-refresh-runtime` |
| Cloud Scheduler | `commerce-lab-refresh` | `0 6 * * *` Asia/Seoul |
| 결제 예산 | `commerce-decision-demo safety budget` | 월 ₩20,000. 실지출 50/90/100%와 예상 지출 100% 알림을 이메일과 Pub/Sub 토픽 `budget-hardcap-alerts`로 보냄 |
| Cloud Function | `budget-hardcap` (2nd gen) | 실지출이 예산 이상이면 프로젝트 결제를 끊는다 |
| 서비스 계정 | `cloudbuild-deployer`, `commerce-app-runtime`, `commerce-refresh-runtime`, `budget-hardcap-runtime` | 각각 필요한 리소스에만 최소 권한. 프로젝트 기본 SA는 쓰지 않음 |

## 운영

- **매일 갱신:** Scheduler가 06:00 KST에 Job을 실행한다. Job은 새 랜덤 시드로 데이터를 만들어 GCS에 올리고, BigQuery `raw`를 전체 교체한 뒤, `metrics` 함수로 기준일 5개의 KPI를 계산하고, Gemini 요약(최신 기준일 1회)을 붙여 `snapshot/app_snapshot.json`을 올린다. 시드는 스냅샷의 `data_seed`와 `raw/commerce/날짜/seed.txt`에 남는다.
- **수동 실행:** `gcloud run jobs execute commerce-lab-refresh --region asia-northeast3 --wait`. 같은 날 다시 실행하면 그날의 `raw` 폴더를 덮어쓴다.
- **배포:** `scripts/provision_gcp.sh`(버킷·데이터셋·SA·SQL), `scripts/deploy_app.sh`(앱), `scripts/provision_scheduler.sh`(Job·Scheduler), `scripts/provision_budget_hardcap.sh`(하드캡). 모두 멱등이다. 존재 여부를 먼저 확인한 뒤 실행한다.
- **KPI 대조:** `uv run python -m commerce_lab.pipeline.parity --seed N`이 같은 데이터에서 BigQuery와 pandas 결과를 비교한다. 오늘의 `raw` 테이블과 GCS 폴더를 교체하므로 갱신 직후가 아닌 때에 쓴다.
- **해체:** `GCP_PROJECT_ID=… GCS_BUCKET=… ./scripts/teardown_gcp.sh --yes`. 되돌릴 수 없으므로 오너 확인 후에만 실행한다. 결제 예산은 남겨 둬도 무해하다.
- **Gemini 끄기:** Job의 환경변수 `GEMINI_ENABLED=false`.
- **보관:** `raw/commerce/날짜/`는 삭제하지 않는다. 하루 약 0.4MB(연 약 150MB)로 Always Free 5GB 이내이고, 앱은 스냅샷 JSON 1개(약 124KB)만 읽어 보관량과 무관하다.

## 예산과 하드캡

예산 알림은 이메일만 보내고 지출을 막지 않으므로, 실지출이 예산 이상이면 `budget-hardcap`이 프로젝트 결제를 끊는다. 프로젝트 단위라 앱을 포함한 모든 과금 리소스가 함께 멈추고, 결제 계정을 다시 연결해야 복구된다. 함수는 받은 지출액을 `Budget alert: … cost=… budget=…` 로그로 남긴다. 함수의 서비스 계정에는 결제 계정 수준 `roles/billing.user`가 필요하며(결제 계정 IAM은 오너가 직접 부여), 부여 명령은 `scripts/provision_budget_hardcap.sh` 끝에 출력된다.

비용 전제: 무료 체험이 끝난 뒤에도 사용량이 Always Free 범위 안이면 계속 운영한다. 체험 종료(대략 2026-12-23) 때 자동 유료 전환인지 정지인지는 GCP 공식 동작이 불확실하므로 그 전에 확인한다.

## 앱 공개 접근 설정

호스팅 조직이 도메인 제한 공유 정책(`iam.allowedPolicyMemberDomains`)을 쓰면 `--allow-unauthenticated`만으로는 공개되지 않는다. 조직 정책은 그대로 두고 이 프로젝트에만 예외를 둔다.

1. 오너 계정에 조직 수준 `roles/orgpolicy.policyAdmin`을 부여한다. 이 역할은 프로젝트 단위로 부여할 수 없다.
2. 프로젝트에 `iam.allowedPolicyMemberDomains` 오버라이드(`allowAll: true`)를 만든다.
3. `gcloud run services add-iam-policy-binding commerce-decision-app --member=allUsers --role=roles/run.invoker`. 정책 전파에 2분쯤 걸려, 첫 시도가 `FAILED_PRECONDITION`이면 재시도한다.
4. 로그인 없이 접속해 확인한다.

IAM 바인딩 명령은 에이전트 자동 모드가 차단하므로 오너가 직접 실행한다.

## 핵심 설계 결정

| 결정 | 선택 | 이유 |
|---|---|---|
| 데이터 | 합성 데이터만 사용. 기간은 2026-05-25~09-21(120일)로 고정, 값은 실행마다 새 랜덤 시드 | 실제 데이터 의존성 회피. 시드가 4개 시나리오를 뚜렷하게 심지 못하면 같은 시드에서 파생한 다음 시도로 최대 50회 재생성([synthetic_data.md](synthetic_data.md)) |
| 근거(source of truth) | KPI는 BigQuery 테이블 함수가 결정적으로 계산, Gemini는 해석만 | AI 해석은 근거가 있고 감사 가능해야 함. 기준일마다 파라미터가 필요해 뷰 대신 테이블 함수를 쓴다. `Lens.compute_warehouse`가 없는 관점은 pandas로 계산하고 스냅샷 `metrics_source`에 표시 |
| 공개 읽기 경로 | 앱은 `app_snapshot.json` 하나만 읽는다 | 공개 트래픽이 BigQuery·Gemini를 직접 호출하지 않게 함 |
| 비교 시점 | 최신 기준일 + 15일 간격 과거 기준일 최대 5개를 스냅샷 하나에 미리 계산, 윈도(30일)는 고정 | 앱이 정적 파일만 읽으면서 시점 이동을 지원하는 가장 단순한 방법. 윈도는 심은 시나리오 임계값과 맞물림 |
| 컨테이너 | 앱(`Dockerfile`, 최소 의존성)과 리프레시(`Dockerfile.job`, BigQuery·Gemini SDK 포함) 분리 | 상시 구동 앱에 불필요한 SDK를 넣지 않음 |
| 서비스 계정 | 용도별 최소 권한 SA 4개 | 프로젝트 기본 SA는 광범위한 권한을 가짐 |
| BigQuery 권한 | 데이터셋 access ACL(`bq update`)로 부여 | `bq add-iam-policy-binding -d`는 이 환경에서 allowlist가 필요 |
| 빌드 버킷 | 전용 스테이징 버킷(`<프로젝트>-build-staging`) | 자동 생성되는 `_cloudbuild` 버킷 대신 권한을 명확히 스코프 |
| GCP 도구 | `gcloud storage`(`gsutil` 아님), 재현 가능한 CLI 스크립트(IaC라 부르지 않음) | `gsutil`은 레거시. Terraform은 필요해질 때까지 범위 밖 |
| Gemini | `gemini-2.5-flash`, Vertex AI `us-central1`, `max_output_tokens=400`, `temperature=0.2`, thinking 예산 0, 타임아웃 30초·재시도 없음, 저장 요약 최대 1500자. 실패하면 예외 없이 `None`으로 저하 | 비용·남용 표면 최소화, 외부 API 실패가 파이프라인과 앱을 깨지 않게 함. 호출은 스케줄된 Job에서만 하고 프롬프트에는 계산된 구조화 사실만 들어간다 |
| Gemini 언어 | 실제 호출은 영어 1회. 한국어 화면은 결정적 대체 요약 사용 | 호출을 늘리지 않고 AI가 번역을 왜곡할 여지를 없앰 |
| 앱 i18n | 결정 카드 문장은 `issue_type`·`affected`·`supporting_kpi`로부터 언어별로 렌더링(`app/i18n.py`). 메트릭 식별자는 번역하지 않음 | 사실과 서술의 분리 유지 |
| 예상 매출 영향 | 마케팅 효율 악화·매출 하락 규칙에서만 계산, 나머지는 `None` | 원가·판매가·주문 귀속 데이터가 없는 항목에 방어 불가능한 추정치를 만들지 않음 |
| 이슈 정렬 | 심각도가 1차, 같은 등급 안에서만 예상 매출 영향 절대값으로 2차 | 심각도는 규칙의 판단이라 금액으로 뒤집지 않음 |
| 추세 차트 | 결정 카드마다 모든 기준일의 같은 세그먼트 값을 미니 라인차트로 표시(2개 미만이면 숨김) | 다중 기준일 스냅샷을 재사용해 새 계산 없이 추세 제공 |
| 다른 AI로 분석 | 개요 탭에 복사용 프롬프트(`app/copy_prompt.py`) | 앱이 외부 AI를 호출하지 않아 비용·공격면 없음 |
| 하드캡 함수 | Billing API를 `google-auth`+`requests`로 직접 호출, 빌드는 `cloudbuild-deployer` 재사용, 시그니처 `stop_billing(event, context)`, 최대 인스턴스 5·재시도 활성 | 클라이언트 라이브러리의 grpc 체인이 buildpack 빌드에서 실패. 기본 Compute SA는 권한이 없어 빌드가 조용히 실패. `--trigger-topic` 배포는 2-인자 레거시 형식으로 호출됨. 동시 알림이 429로 거부되지 않게 함 |
| 라이선스 | MIT | |
| 랜딩페이지 | 정적 HTML, `word-break: keep-all`, 이미지 `lazy` 미사용(탭 전환 시 비활성 패널 이미지가 로드되지 않음), 라이트/다크 토글(localStorage, 최초는 OS 설정) | 빌드 없이 가장 단순. 스크린샷은 로컬 앱의 실제 실행 캡처이며 캡처 시점의 예시 데이터 |

임계값(재고 소진 7/60일, 이슈 규칙 등)과 근거는 [kpi_definitions.md](kpi_definitions.md), [decision_rules.md](decision_rules.md)에 있다. 데모용 기본값이며 실제 벤치마크 튜닝은 아니다.

## 새 환경에서 이어가기

- 맥락의 출처: [START_PROMPT.txt](START_PROMPT.txt)(최초 지시), [PROJECT.md](PROJECT.md), [AGENTS.md](../AGENTS.md), [README.md](../README.md), 이 문서.
- 환경: `git clone https://github.com/yimsemin/commerce-decision-demo.git` → `git config core.hooksPath .githooks` → `uv sync --extra dev --extra pipeline`.
- 자격 증명은 머신별로 설정한다: GCP는 `gcloud auth login`과 `gcloud auth application-default login`(오너 계정), GitHub는 `gh auth login`(계정 `yimsemin`). 저장소에는 어떤 자격 증명도 없다.
- 라이브 리소스는 이미 있으므로 재생성하지 않는다. `scripts/provision_*.sh`는 멱등이지만 먼저 `gcloud run services list` 등으로 존재를 확인한다.

## 한계와 열린 항목

- 한국어 화면에서도 `sku_id`, `days_of_cover` 같은 메트릭 식별자가 원문으로 보인다(위 i18n 결정). 번역할지는 포트폴리오 인상에 영향을 주는 오너 판단이다.
- Vertex AI `global` 위치는 서비스 계정에서만 403이었고, 원인(조직 수준 정책으로 추정)은 조회 권한이 없어 규명하지 못했다. `us-central1`로 쓰고 있으며, `global`이 필요해지면 조직 관리자 권한으로 조사한다.
- 합성 데이터 기간이 고정이라 기준일은 매일 같다. 갱신되는 것은 값이다.
