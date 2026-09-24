# Gemini 통합

구현: `src/commerce_lab/gemini/`. 코드베이스 전체에서 생성형 모델을 호출하는 곳은 여기 *하나뿐*이다. 그 앞단(datagen, metrics, decisions)은 모두 결정적이며 Gemini가 호출되는 시점에는 이미 계산이 끝나 있다.

## 제한된 역할

Gemini는 M4의 `DecisionItem` 목록과 상위 매출 KPI만 받는다(`gemini/prompts.py::build_executive_summary_prompt`) -- 원본 주문/마케팅/재고 행은 절대 받지 않고, 숫자를 계산해달라는 요청도 받지 않는다. 시스템 지시문은 명시적으로 이렇게 말한다: 주어진 사실만 사용하라, 추가 메트릭/원인/숫자를 만들어내지 마라, 불확실하면 추측 대신 그렇다고 말하라, 짧은 경영진 요약으로 종합하라. 이는 PROJECT.md §7("Gemini는 뒷받침되지 않는 사실을 만들어내서는 안 되며, 가능한 한 제한 없는 원본 데이터가 아니라 구조화된 메트릭/이슈 컨텍스트를 받아야 한다")을 그대로 반영한다.

Gemini가 쓰는 것은 정확히 하나, `snapshot["gemini_summary"]`라는 짧은 서술 문자열뿐이다. `DecisionItem`의 심각도, 사실, 권장 조치는 절대 바꾸지 않는다 -- 이것들은 전부 `commerce_lab.decisions`에서 나온다.

## 모델과 엔드포인트

- 모델: `gemini-2.5-flash`.
- 위치: Vertex AI `global` 엔드포인트(`GOOGLE_CLOUD_LOCATION`/클라이언트 `location="global"`). 2026-09-22 웹 조사로, `generateContent` 호출에 대해 문서화되고 실제로 동작하는 옵션이며 Gemini 2.5 Flash가 명시적으로 지원됨을 확인했다. 알려진 제약(정확한 처리 리전을 제어할 수 없음, 튜닝/배치/컨텍스트 캐싱 미지원)은 이 앱에는 해당하지 않는다: 모든 데이터가 합성 데이터라 데이터 상주(residency) 요구사항이 없고, 리프레시마다 캐시 없이 한 번 호출하는 텍스트 콜이기 때문이다. 오너 지시에 따라, 임의의 `us-central1` 대체안보다 가장 단순하게 지원되는 옵션인 `global`을 우선했다. 이후 실제 배포에서 다른 모델/위치 조합이 필요해지면 `gemini/config.py` 한 파일만 고치면 된다.
- 2026-09-23: 실제로 `global` 엔드포인트에서 `gemini-2.5-flash`를 라이브로 호출해 4개 시나리오를 정확히 반영한 요약을 받는 데 성공했다(로컬 실행, 수동 실행한 Cloud Run Job, Cloud Scheduler가 실제로 트리거한 무인 실행 모두에서 확인). `docs/verification.md` 참고.

## 실패 처리

`generate_executive_summary()`는 절대 예외를 던지지 않는다. 어떤 실패든(자격 증명 누락, 쿼터, 네트워크, 모델 불가) 잡아서 로그를 남기고 `gemini_summary: None`으로 낮춘다. 앱(`commerce_lab.app.main`)은 그래도 항상 렌더링된다 -- `gemini_summary`가 null이면 같은 의사결정 항목들로 만든 결정적 대체 요약(`commerce_lab.app.view_helpers.fallback_executive_summary`)을 보여주므로, "근거 있는 Gemini 해석을 본다"는 Definition of Done 항목이 페이지 전체를 깨뜨리지 않고 우아하게 저하될 수 있다.

## 호출

리프레시의 선택적 단계로, 기본으로는 실행되지 않는다: `python -m commerce_lab.pipeline.refresh --summarize`(`GCP_PROJECT_ID`와 라이브 Vertex AI 자격 증명 필요).
