# PROJECT.md 대비 End-to-end 검증

기준: 2026-09-23(M11, 라이브 배포 + 최소권한 IAM 리팩터 완료). 범례: **구현됨**(코드 존재) / **로컬 검증**(실제 실행하고 확인함, 단순 코드 리딩 아님) / **클라우드 검증**(실제 GCP에서 실행함).

## Definition of Done (§15)

| # | 항목 | 상태 | 근거 |
|---|---|---|---|
| 1 | 가상의 비즈니스 문제 이해 | 로컬 검증 | `PROJECT.md`(스펙) + `README.md`(포트폴리오 설명) |
| 2 | 합성 데이터 재현/확인 | 로컬 검증 | `python -m commerce_lab.datagen.generator` 실행 및 확인; `docs/synthetic_data.md`; `tests/test_datagen/` |
| 3 | 비즈니스 데이터 → BigQuery 메트릭 추적 | **클라우드 검증** | `scripts/provision_gcp.sh`를 `commerce-decision-demo` 프로젝트에 실제 실행: `raw`/`staging`/`metrics` 데이터셋과 모든 테이블/뷰 생성 완료; `raw.orders` 1,633행 독립 확인; `metrics.sales_by_brand_channel`을 라이브로 조회해 pandas 미러와 소수점까지 일치(Marlow/retail_partner -42.27%) |
| 4 | 경영 의사결정 앱 열기 | **클라우드 검증** + 로컬 검증 | Cloud Run(`commerce-decision-app`, asia-northeast3)에 배포, `/_stcore/health`가 인증된 요청에 `ok` 응답. 추가로: `streamlit.testing.v1.AppTest`(예외 0건, 탭 6개 모두), 로컬 `streamlit run` 정상, 실제 스크린샷(`docs/screenshots/*.png`) |
| 5 | 데이터에서 탐지된, 의도적으로 심어진 이슈 확인 | 로컬 + 클라우드 검증 | 라이브 `gemini_summary`와 로컬 스크린샷 모두, 심어놓은 4개 시나리오가 유일한 "high" 심각도 이슈로 나타남; `tests/test_decisions/test_rules.py` |
| 6 | 각 이슈의 근거 확인 | 로컬 검증 | 의사결정 카드가 `supporting_kpi` + `likely_drivers`를 보여줌(`docs/screenshots/overview.png`) |
| 7 | 근거 있는 Gemini 해석/요약 확인 | **클라우드 검증** | Vertex AI `global`에서 `gemini-2.5-flash`를 라이브로 호출(로컬 `refresh --summarize`, 수동 실행한 Cloud Run Job, Scheduler가 실제로 트리거한 무인 실행 모두)해 4개 시나리오를 정확히 요약 -- 픽스처가 아니다. `tests/test_gemini/`가 가짜 클라이언트로 "절대 죽지 않음" 계약을 커버 |
| 8 | 제안 조치와 후속 KPI 이해 | 로컬 검증 | 모든 의사결정 항목에 `possible_action` + `kpi_to_monitor` 존재(앱에서 확인 가능); `tests/test_decisions/test_post_action_verification.py`가 검증 메커니즘 자체(KPI가 임계값을 넘어 회복되면 이슈가 더 이상 나타나지 않음)를 보여줌 |
| 9 | 저장소 문서로 배포 재현 | **클라우드 검증** | 4개 스크립트(`provision_gcp.sh`, `deploy_app.sh`, `provision_scheduler.sh`, `teardown_gcp.sh`는 검토만 함) 모두 실제 프로젝트에 실행, 멱등성 확인을 위해 2회씩 재실행 -- 이후 전용 최소권한 서비스 계정으로 리팩터링해 다시 2회 재실행해도 동일하게 깔끔함. 과정에서 실제 버그 여러 건 발견/수정(`PROGRESS.md` 참고) |
| 10 | 설계 트레이드오프와 한계 이해 | 로컬 검증 | `README.md` 한계 섹션; 전체 결정/근거 로그는 `PROGRESS.md` |

## 핵심 질문 (§3)

1. 매출/주문에서 실질적으로 무엇이 바뀌었나 -- Overview + Performance 탭
2. 어떤 브랜드/채널/제품이 가장 크게 기여했나 -- Performance 탭, 절대 변화량 정렬
3. 마케팅 효율이 개선/악화되고 있나 -- Marketing 탭(ROAS 현재 vs 이전)
4. 획득/재구매 패턴이 변하고 있나 -- Customer 탭
5. 어떤 SKU가 품절/과잉재고 위험이 있나 -- Inventory 탭
6. 지금 무엇에 주목해야 하나 -- Decisions 탭, 심각도순
7. 조치 후 KPI가 개선됐나 -- 별도 기능이 아니라 구조상 그렇게 답해진다: 같은 결정적 규칙을 더 최신 데이터에 다시 돌리는 것이 곧 검증이다(`docs/decision_rules.md` "사후 조치 검증")

## 공개 접근: 미해결이 아니라 의도적으로 미룬 것

Cloud Run 앱은 배포되어 완전히 동작하지만, 현재는 공개 링크가 아니라 ID 토큰으로만 접근 가능하다. 두 가지 사실이 독립적으로 모두 성립한다: `subproject.kr` 조직의 도메인 제한 공유 정책이 `allUsers` 바인딩을 막고 있고, *동시에* 오너가 지금은 인증 전용으로 유지하는 것이 의도적인 선택이라고 확인했다(공개는 나중에 할 계획이며, 결정을 기다리는 중인 게 아니다). 옵션은 `PROGRESS.md`의 "남은 작업" 참고.
