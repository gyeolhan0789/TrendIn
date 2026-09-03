"""수집 어댑터 공통 기반. 소스 어댑터 셋(RSS·목록 페이지·API)이 이 계약을 공유한다.

설계는 pipeline/docs/web-collect.md 에 있다. 이 패키지의 책임은 "후보 → raw → article.json"
까지이고, 저장·발급·중복 판정은 여기 없다.
"""
