# W3/M4 — Hadoop Streaming Sentiment140 Count

4-node Hadoop 클러스터(master 1 + worker 3) 위에서 Sentiment140 CSV 파일을
Python Mapper/Reducer와 Hadoop Streaming으로 처리해 감정 라벨별 개수를
집계하는 작업이다.

Sentiment140 원본 라벨은 아래처럼 해석한다.

| 원본 라벨 | 의미 | 출력 카테고리 |
|---|---|---|
| `0` | negative | `negative` |
| `2` | neutral | `neutral` |
| `4` | positive | `positive` |

## 1. Hadoop 실행 환경 구성 방법

`docker-compose.yaml`은 4개의 컨테이너를 실행한다.

| 서비스 | 컨테이너 이름 | hostname | 역할 |
|---|---|---|---|
| master | `m4-master` | `namenode` | NameNode, SecondaryNameNode, ResourceManager |
| worker1 | `m4-worker1` | `worker1` | DataNode, NodeManager |
| worker2 | `m4-worker2` | `worker2` | DataNode, NodeManager |
| worker3 | `m4-worker3` | `worker3` | DataNode, NodeManager |

M4 이미지는 M3의 Hadoop 기본 이미지(`w3m3:latest`)를 기반으로 만들고,
tweet 분석용 Mapper/Reducer와 실행 스크립트를 추가한다.

그 다음 M4 클러스터를 빌드하고 실행한다.

```bash
cd ../M4
docker compose build
docker compose up -d

# Hadoop 데몬이 뜰 때까지 잠시 대기
sleep 20
```

실행 상태를 확인한다.

```bash
docker compose ps
docker exec m4-master jps
```

`NameNode`, `ResourceManager`, `SecondaryNameNode`가 보이면 master 노드가
정상적으로 올라온 것이다.

## 2. Sentiment140 데이터셋 다운로드 방법

Sentiment140 데이터셋은 Kaggle의 `kazanova/sentiment140` 데이터셋을 사용한다.

### kagglehub 사용

```bash
pip install kagglehub
python3 -c "import kagglehub; print(kagglehub.dataset_download('kazanova/sentiment140'))"
```

출력된 디렉터리 안에서 아래 CSV 파일을 찾는다.

```text
training.1600000.processed.noemoticon.csv
```

## 3. 데이터셋을 HDFS에 업로드하는 방법

먼저 호스트에 있는 CSV 파일을 master 컨테이너의 로컬 파일시스템으로 복사한다.
아래 명령에서 `/path/to/...` 부분은 실제 CSV 파일 위치로 바꾼다.

```bash
docker cp /path/to/training.1600000.processed.noemoticon.csv \
  m4-master:/data/training.1600000.processed.noemoticon.csv
```

복사 여부를 확인한다.

```bash
docker exec m4-master ls -lh /data/training.1600000.processed.noemoticon.csv
```

HDFS 업로드는 `run_tweet.sh`가 실행될 때 자동으로 수행한다. 실행마다
타임스탬프 기반 `RUN_ID`를 만들고 아래 경로에 입력 파일을 업로드한다.

```text
/user/root/tweet/input/<RUN_ID>/
```

수동으로 HDFS에 업로드하고 싶다면 아래처럼 실행할 수 있다.

```bash
docker exec m4-master hdfs dfs -mkdir -p /user/root/tweet/input/manual
docker exec m4-master hdfs dfs -put \
  /data/training.1600000.processed.noemoticon.csv \
  /user/root/tweet/input/manual/
```

## 4. Python Mapper와 Reducer 실행 준비 방법

Mapper/Reducer는 Python 스크립트라 별도 컴파일이 필요 없다. M4 이미지를
빌드하면 `Dockerfile`이 아래 파일을 컨테이너 안으로 복사한다.

```text
src/mapper.py             -> /opt/tweet/src/mapper.py
src/reducer.py            -> /opt/tweet/src/reducer.py
scripts/run_tweet.sh      -> /opt/tweet/scripts/run_tweet.sh
```

준비 상태를 확인한다.

```bash
docker exec m4-master ls -al /opt/tweet/src /opt/tweet/scripts
```

`mapper.py`, `reducer.py`, `run_tweet.sh`를 수정했다면 이미지를 다시 빌드하고
컨테이너를 재생성해야 한다.

```bash
docker compose build
docker compose up -d
```

Mapper/Reducer를 로컬 방식으로 빠르게 테스트할 수도 있다.

```bash
docker exec m4-master sh -c \
  "head -n 1000 /data/training.1600000.processed.noemoticon.csv \
  | /opt/tweet/src/mapper.py \
  | sort \
  | /opt/tweet/src/reducer.py"
```

## 5. Hadoop Streaming을 이용하여 MapReduce 작업을 실행하는 방법

master 컨테이너에서 실행 스크립트를 호출한다.

```bash
docker exec -it m4-master \
  /opt/tweet/scripts/run_tweet.sh \
  /data/training.1600000.processed.noemoticon.csv
```

스크립트 내부 동작은 다음과 같다.

1. `/user/root/tweet/input/<RUN_ID>/`에 CSV 파일 업로드
2. Hadoop Streaming jar로 `mapper.py`, `reducer.py` 실행
3. `/user/root/tweet/output/<RUN_ID>/`에 결과 저장
4. HDFS 결과를 `/opt/tweet/results/result_<RUN_ID>.tsv`로 병합 저장
5. 결과 상위 20줄 출력

정상 실행 시 결과는 대략 아래 형태로 출력된다.

```text
negative    800000
positive    800000
```

Sentiment140 학습 데이터의 `training.1600000.processed.noemoticon.csv`에는 보통
`0`과 `4` 라벨만 포함되어 있어 `neutral`이 나오지 않는다.

## 6. 작업 진행 상황을 확인하는 방법

실행 중인 터미널에는 Hadoop Streaming 진행률이 출력된다.

```text
map 0% reduce 0%
map 100% reduce 100%
```

YARN Web UI에서도 확인할 수 있다.

```text
http://localhost:8088
```

Applications 목록에서 방금 실행한 작업을 선택하면 상태, 진행률, 로그를 볼 수
있다.

CLI로 확인하려면 아래 명령을 사용한다.

```bash
docker exec m4-master yarn application -list -appStates ALL
```

특정 애플리케이션 로그가 필요하면 `application_...` ID를 넣어 조회한다.

```bash
docker exec m4-master yarn logs -applicationId <APPLICATION_ID>
```

## 7. HDFS에서 출력 결과를 조회하는 방법

실행 결과 목록을 확인한다.

```bash
docker exec m4-master hdfs dfs -ls /user/root/tweet/output
```

특정 실행 결과를 조회한다.

```bash
docker exec m4-master hdfs dfs -cat /user/root/tweet/output/<RUN_ID>/part-*
```

출력 예시는 아래와 같다.

```text
negative    800000
positive    800000
```

HDFS에 업로드된 입력 파일도 확인할 수 있다.

```bash
docker exec m4-master hdfs dfs -ls /user/root/tweet/input/<RUN_ID>
```

## 8. 출력 결과를 로컬 파일로 가져오는 방법

`run_tweet.sh`는 실행 결과를 자동으로 컨테이너 안의
`/opt/tweet/results/result_<RUN_ID>.tsv` 파일로 저장한다. 컨테이너 안에서
결과 파일 목록을 확인한다.

```bash
docker exec m4-master ls -lh /opt/tweet/results
```

호스트로 복사한다.

```bash
docker cp m4-master:/opt/tweet/results/result_<RUN_ID>.tsv \
  ./result_<RUN_ID>.tsv
```

HDFS 결과를 직접 병합해서 다른 위치에 저장할 수도 있다.

```bash
docker exec m4-master hdfs dfs -getmerge \
  /user/root/tweet/output/<RUN_ID> \
  /root/tweet_result_<RUN_ID>.tsv

docker cp m4-master:/root/tweet_result_<RUN_ID>.tsv \
  ./tweet_result_<RUN_ID>.tsv
```

## 9. 감정 분석 결과를 해석하고 검증하는 방법

이 작업은 트윗 문장을 새로 분류하는 모델이 아니라, Sentiment140 CSV에 이미
들어 있는 감정 라벨을 Hadoop으로 집계하는 작업이다. 따라서 결과는 라벨별
데이터 개수로 해석한다.

```text
negative    800000
positive    800000
```

위 결과는 부정 라벨 트윗 800,000개, 긍정 라벨 트윗 800,000개가 입력 데이터에
있다는 뜻이다. `neutral`이 없다면 입력 CSV에 라벨 `2`가 없거나 매우 적다는
뜻이다.

총합 검증은 결과 카운트의 합과 Mapper가 처리한 레코드 수를 비교한다.

```bash
# Mapper가 유효한 CSV 레코드에서 출력한 라인 수
docker exec m4-master sh -c \
  "/opt/tweet/src/mapper.py < /data/training.1600000.processed.noemoticon.csv | wc -l"

# HDFS 결과 카운트 합
docker exec m4-master sh -c \
  "hdfs dfs -cat /user/root/tweet/output/<RUN_ID>/part-* \
  | awk -F'\t' '{sum += $2} END {print sum}'"
```

두 값이 같으면 Mapper가 출력한 모든 라벨이 Reducer에서 누락 없이 합산된
것이다.

라벨별 검증은 원본 CSV의 첫 번째 컬럼을 직접 세어 비교한다.

```bash
docker exec m4-master sh -c \
  "awk -F',' '{count[\$1]++} END {for (label in count) print label, count[label]}' \
  /data/training.1600000.processed.noemoticon.csv"
```

`0`의 개수는 `negative`, `2`의 개수는 `neutral`, `4`의 개수는 `positive`
결과와 일치해야 한다. 단순 `awk -F','` 검증은 CSV 인용부호를 완전히 파싱하지
않으므로, 최종 기준은 Python `csv` 모듈을 사용하는 `mapper.py` 결과로 두는
것이 안전하다.

## Mapper / Reducer 동작

- `src/mapper.py`: CSV 한 줄을 Python `csv.reader`로 파싱하고, 첫 번째 컬럼
  라벨을 `negative`, `neutral`, `positive`로 변환해 `category\t1`을 출력한다.
  Sentiment140 CSV는 `latin-1` 인코딩으로 읽는다.
- `src/reducer.py`: 정렬된 `category\tcount` 입력을 받아 같은 카테고리의
  개수를 합산하고 `category\ttotal_count`를 출력한다.
