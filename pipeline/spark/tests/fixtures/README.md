```
contract/    입력 계약 샘플 — 이벤트 3건 + 그 이벤트가 가리키는 객체 (S15P21A102-159)
corpus/      한국어·영어·혼합·코드 포함 문서 30건 (실제 수집 데이터에서 발췌, 익명화)
snapshots/   각 문서의 추출 결과
```

## `contract/`

`ingest` 가 Kafka·MinIO 없이 파싱·검증 코드를 테스트하는 근거다. 계약은 [02](../../docs/02-input-contract.md),
생산 측 설명은 [`pipeline/docs/spark-integration.md`](../../../docs/spark-integration.md).

```
contract/
├─ article-event.json         기사 이벤트. object_key 가 있다
├─ run-summary-success.json   실행 요약(성공). object_key 가 null 이고 record_count > 0
├─ run-summary-failed.json    실행 요약(실패). failure_reason 이 있다
└─ objects/<object_key 그대로>/
   ├─ article.json            article-event.json 의 object_key 가 가리키는 실물
   └─ raw.xml                 raw_object_key 가 가리키는 실물
```

`objects/` 아래 경로는 MinIO 의 `object_key` 와 **같은 형태**이다. 그래서 테스트가 버킷 루트만
바꿔 끼우면 실제 s3a 경로와 같은 코드로 읽힌다.

**손으로 고치지 않는다.** `sha256(article.json)` 이 이벤트의 `checksum` 과 같아야 하고, 메시지의
값이 `article.json` 의 값과 같아야 한다. 크롤러 쪽 `pipeline/tests/common/test_contract_fixtures.py`
가 그 둘을 검사하므로, 손으로 고치면 그쪽이 깨진다. 갱신 절차는
[`spark-integration.md`](../../../docs/spark-integration.md) 의 "fixture 갱신" 절이다.

`objects/` 아래 두 파일은 `pipeline/.gitattributes` 가 `-text` 로 묶어 뒀다. `core.autocrlf=true`
인 Windows 작업자가 체크아웃해도 개행이 바뀌지 않는다 — 바뀌면 sha256 이 달라져 fixture 가
거짓말을 하게 된다.

**⚠️ 소비 측 단위 테스트는 아직 이 fixture 를 읽지 않는다.** `spark/tests/unit/test_contract.py`
가 메시지 형태를 손으로 옮겨 뒀다. 둘이 나뉘어져도 지금은 아무도 못 잡으므로, `classify()` 를 여기
3건에 돌리는 테스트를 하나 두는 편이 낫다.

## `corpus/` · `snapshots/`

회귀 스냅샷용 고정 데이터 ([09 §4](../../docs/09-dev-and-test.md) · [04 §9](../../docs/04-keyword-extraction-spec.md)).

**아직 비어 있다.** 실제 수집 데이터가 없으면 채울 수 없다 — [09 §7](../../docs/09-dev-and-test.md) 의 항목 5 다.
코드를 고쳤을 때 스냅샷이 바뀌면 실패한다. 의도한 변경이면 갱신하고 diff 를 커밋에 남긴다.
