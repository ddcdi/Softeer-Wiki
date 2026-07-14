# W3/M6 - Amazon Reviews 2023 리뷰 개수 및 평균 평점 계산

Amazon Reviews 2023 JSONL 데이터를 Hadoop Streaming으로 처리해 상품별 리뷰 개수와 평균 평점을 계산하고, 리뷰 수 기준으로 정렬하는 작업이다.

최종 출력 형식은 다음과 같다.

```text
product_id    review_count    average_rating
```

## 1. Hadoop 실행 환경 구성 방법

이 프로젝트는 4개 컨테이너로 구성된 Hadoop 클러스터를 사용한다.

| 서비스 | 컨테이너 이름 | hostname | 역할 |
|---|---|---|---|
| master | `m6-master` | `namenode` | NameNode, SecondaryNameNode, ResourceManager |
| worker1 | `m6-worker1` | `worker1` | DataNode, NodeManager |
| worker2 | `m6-worker2` | `worker2` | DataNode, NodeManager |
| worker3 | `m6-worker3` | `worker3` | DataNode, NodeManager |

클러스터를 빌드하고 실행한다.

```bash
cd /Users/admin/Documents/GitHub/Softeer-Wiki/missions/W3/M6
docker compose build
docker compose up -d
```

실행 상태를 확인한다.

```bash
docker compose ps
docker exec m6-master jps
```

`NameNode`, `ResourceManager`, `SecondaryNameNode`가 보이면 master 노드가 정상적으로 올라온 것이다.

## 2. Amazon Reviews 2023 데이터셋 다운로드 방법

Amazon Reviews 2023 공개 JSONL 파일을 다운로드한다. 파일은 보통 제품 카테고리별로 여러 개의 `.jsonl` 또는 `.jsonl.gz` 파일로 제공된다.

예시 절차는 다음과 같다.

1. Amazon Reviews 2023 공개 페이지에서 필요한 카테고리의 파일을 내려받는다.
2. 압축 파일이면 해제해서 `.jsonl` 파일로 준비한다.
3. 여러 개의 JSONL 파일이 있으면 하나의 폴더에 모아둔다.

폴더 구조는 다음과 같다.

```text
amazon_reviews/
├── Automotive.jsonl
├── Amazon_Fashion.jsonl
```

## 3. 사용한 데이터셋의 이름과 출처

데이터셋 이름은 Amazon Reviews 2023이다.

실습에는 아래 두가지 데이터셋을 사용했다.
Automotive.jsonl
Amazon_Fashion.jsonl

출처는 Amazon이 공개한 고객 리뷰 데이터셋이다. 이 작업에서는 공개 JSONL 리뷰 레코드를 사용하며, 상품 식별자와 평점 정보를 포함한 레코드를 집계한다.

## 4. 데이터 파일 구조 및 주요 컬럼 설명

Amazon Reviews 2023 파일은 JSON Lines 형식이다. 즉, 한 줄이 하나의 JSON 객체다.

예시 레코드는 다음과 같다.

```json
{"parent_asin":"B001E4KFG0","rating":5.0,"title":"Great product","text":"..."}
```

주요 컬럼은 다음과 같다.

1. `parent_asin`: 상품의 상위 식별자이다. 이 작업에서 우선적으로 사용하는 상품 ID이다.
2. `asin`: 상품 식별자 대체 컬럼이다. `parent_asin`이 없을 때 사용한다.
3. `product_id` / `item_id`: 일부 변형 스키마에서 사용할 수 있는 대체 상품 ID 필드이다.
4. `rating`: 평점 값이다. 이 작업에서 우선적으로 사용하는 평점 필드이다.
5. `overall`: 일부 데이터 변형에서 평점을 담는 대체 필드이다.
6. `stars`: 또 다른 평점 대체 필드이다.
7. `title`: 리뷰 제목이다.
8. `text`: 리뷰 본문이다.
9. `timestamp`: 리뷰 시각 정보이다.
10. `verified_purchase`: 실제 구매 여부 정보이다.

현재 Mapper는 상품 ID 후보 필드와 평점 후보 필드를 순서대로 탐색한 뒤, 유효한 값만 `상품ID    평점` 형태로 출력한다.

## 5. 입력 데이터를 HDFS에 업로드하는 방법

여러 JSONL 파일을 하나의 HDFS 입력 디렉터리에 넣고, Hadoop Streaming은 그 디렉터리를 통째로 입력으로 사용한다.

예시 디렉터리 이름은 다음과 같다.

```text
/user/root/amazon_reviews/input/<RUN_ID>/
```

업로드 예시는 다음과 같다.

```bash
docker exec -it m6-master bash -lc '
RUN_ID=$(date +%Y%m%d_%H%M%S)
hdfs dfs -mkdir -p /user/root/amazon_reviews/input/$RUN_ID
hdfs dfs -put /data/amazon_reviews/*.jsonl /user/root/amazon_reviews/input/$RUN_ID/
hdfs dfs -ls /user/root/amazon_reviews/input/$RUN_ID
'
```

여러 파일을 같은 디렉터리에 넣으면 Hadoop이 자동으로 분산 처리한다.

## 6. Python Mapper와 Reducer 실행 준비 방법

Mapper와 Reducer는 Python 스크립트라 별도 컴파일이 필요 없다.

Docker 이미지에는 다음 파일이 들어간다.

```text
src/mapper.py    -> /opt/amazon_review/src/mapper.py
src/reducer.py   -> /opt/amazon_review/src/reducer.py
scripts/run_amz.sh -> /opt/amazon_review/scripts/run_amz.sh
```

준비 상태를 확인한다.

```bash
docker exec m6-master ls -al /opt/amazon_review/src /opt/amazon_review/scripts
```

`mapper.py`와 `reducer.py`를 수정했다면 이미지를 다시 빌드하고 컨테이너를 재생성해야 한다.

```bash
cd /Users/admin/Documents/GitHub/Softeer-Wiki/missions/W3/M6
docker compose build
docker compose up -d
```

## 7. Hadoop Streaming을 이용하여 MapReduce 작업을 실행하는 방법

master 컨테이너에서 Hadoop Streaming을 직접 실행한다.

```bash
docker exec -it m6-master bash
```

컨테이너 안에서 다음과 같이 실행한다.

```bash
STREAMING_JAR=$(ls /opt/hadoop/share/hadoop/tools/lib/hadoop-streaming-*.jar | head -n 1)

hadoop jar "$STREAMING_JAR" \
  -files /opt/amazon_review/src/mapper.py,/opt/amazon_review/src/reducer.py \
  -mapper "python3 mapper.py" \
  -reducer "python3 reducer.py" \
  -input /user/root/amazon_reviews/input/<RUN_ID> \
  -output /user/root/amazon_reviews/output/<RUN_ID>
```

정상 실행 시 출력 디렉터리 `/user/root/amazon_reviews/output/<RUN_ID>`가 생성된다.

Mapper와 Reducer 동작은 다음과 같다.

1. Mapper는 각 JSONL 레코드에서 상품 ID와 평점을 읽는다.
2. Reducer는 같은 상품 ID의 평점을 모두 모아 리뷰 개수와 평균 평점을 계산한다.
3. 최종 출력은 `상품ID    리뷰개수    평균평점`이다.

## 8. 작업 진행 상황을 확인하는 방법

실행 중인 터미널에는 Hadoop Streaming 진행률이 출력된다.

```text
map 0% reduce 0%
map 100% reduce 100%
```

YARN Web UI에서도 확인할 수 있다.

```text
http://localhost:8088
```

Applications 목록에서 방금 실행한 작업을 선택하면 상태, 진행률, 로그를 볼 수 있다.

CLI로 확인하려면 아래 명령을 사용한다.

```bash
docker exec m6-master yarn application -list -appStates ALL
```

특정 애플리케이션 로그가 필요하면 `application_...` ID를 넣어 조회한다.

```bash
docker exec m6-master yarn logs -applicationId <APPLICATION_ID>
```

## 9. HDFS에서 출력 결과를 조회하는 방법

실행 결과 목록을 확인한다.

```bash
docker exec m6-master hdfs dfs -ls /user/root/amazon_reviews/output/<RUN_ID>
```

특정 실행 결과를 조회한다.

```bash
docker exec m6-master hdfs dfs -cat /user/root/amazon_reviews/output/<RUN_ID>/part-*
```

출력 예시는 아래와 같다.

```text
B001E4KFG0    3    4.3333
B00813GRG4    1    3.0000
```

## 10. 출력 결과를 로컬 파일로 가져오는 방법

HDFS 결과를 로컬 컨테이너 파일로 가져오려면 `getmerge`를 사용한다.

```bash
docker exec m6-master hdfs dfs -getmerge \
  /user/root/amazon_reviews/output/<RUN_ID> \
  /opt/amazon_review/results/result_<RUN_ID>.tsv
```

컨테이너 안에서 파일을 확인한다.

```bash
docker exec m6-master ls -lh /opt/amazon_review/results
docker exec m6-master cat /opt/amazon_review/results/result_<RUN_ID>.tsv
```

호스트로 복사하려면 다음과 같이 실행한다.

```bash
docker cp m6-master:/opt/amazon_review/results/result_<RUN_ID>.tsv ./result_<RUN_ID>.tsv
```

## 11. 리뷰 수를 기준으로 결과를 정렬하는 방법

이 프로젝트에서는 `run_amz.sh`로 HDFS 집계 결과를 가져와 정렬한다.

실행 예시는 다음과 같다.

```bash
docker exec -it m6-master /opt/amazon_review/scripts/run_amz.sh /user/root/amazon_reviews/output/<RUN_ID>
```

스크립트 내부 동작은 다음과 같다.

1. HDFS의 집계 결과 디렉터리를 로컬로 병합한다.
2. `review_count` 기준으로 내림차순 정렬한다.
3. 동률이면 상품 ID 기준으로 정렬한다.
4. 정렬 파일을 다시 HDFS의 `/user/root/amazon_reviews/sorted/<RUN_ID>/`에 저장한다.
5. 로컬 `cat`과 HDFS `cat`으로 전체 결과를 확인한다.

동일한 정렬을 직접 수행하려면 다음 명령을 사용한다.

```bash
sort -t $'\t' -k2,2nr -k1,1 result_<RUN_ID>.tsv > result_<RUN_ID>_sorted.tsv
```

## 12. 리뷰 개수와 평균 평점 결과를 검증하는 방법

가장 쉬운 검증 방법은 작은 샘플을 직접 계산해서 비교하는 것이다.

예를 들어 아래 입력이 있다고 가정한다.

```text
{"parent_asin":"B001E4KFG0","rating":5.0}
{"parent_asin":"B001E4KFG0","rating":4.0}
{"parent_asin":"B00813GRG4","rating":3.0}
```

이때 기대 결과는 아래와 같다.

```text
B001E4KFG0    2    4.5000
B00813GRG4    1    3.0000
```

검증 방법은 다음과 같다.

1. 작은 JSONL 샘플을 만들어 HDFS 입력 디렉터리에 올린다.
2. Hadoop Streaming을 실행한다.
3. Reducer 결과의 리뷰 개수와 평균 평점을 수동 계산값과 비교한다.
4. 로컬에서도 `mapper -> sort -> reducer` 파이프라인으로 검증한다.

로컬 검증 예시는 다음과 같다.

```bash
cat sample.jsonl \
  | python3 /opt/amazon_review/src/mapper.py \
  | sort \
  | python3 /opt/amazon_review/src/reducer.py
```

추가로 정렬 결과가 맞는지 확인하려면 리뷰 개수 내림차순으로 정렬되어 있는지, 그리고 같은 리뷰 개수에서는 상품 ID 오름차순인지 살펴보면 된다.
