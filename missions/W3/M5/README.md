# W3/M5 - MovieLens 20M 평균 평점 계산

MovieLens 20M Dataset의 `ratings.csv`를 Hadoop Streaming으로 처리해 영화별 평균 평점을 계산하는 작업이다.

입력 CSV는 일반적으로 아래 형식을 따른다.

```text
userId,movieId,rating,timestamp
```

이 작업에서는 `movieId`와 `rating`만 사용한다. Mapper는 `movieId`별로 평점을 내보내고, Reducer는 같은 영화의 평점을 모두 평균 내어 출력한다.

## 1. Hadoop 실행 환경 구성 방법

이 프로젝트는 4개 컨테이너로 구성된 Hadoop 클러스터를 사용한다.

| 서비스 | 컨테이너 이름 | hostname | 역할 |
|---|---|---|---|
| master | `m5-master` | `namenode` | NameNode, SecondaryNameNode, ResourceManager |
| worker1 | `m5-worker1` | `worker1` | DataNode, NodeManager |
| worker2 | `m5-worker2` | `worker2` | DataNode, NodeManager |
| worker3 | `m5-worker3` | `worker3` | DataNode, NodeManager |

클러스터를 빌드하고 실행한다.

```bash
cd /Users/admin/Documents/GitHub/Softeer-Wiki/missions/W3/M5
docker compose build
docker compose up -d
```

실행 상태를 확인한다.

```bash
docker compose ps
docker exec m5-master jps
```

`NameNode`, `ResourceManager`, `SecondaryNameNode`가 보이면 master 노드가 정상적으로 올라온 것이다.

## 2. MovieLens 20M Dataset 다운로드 방법

MovieLens 20M Dataset은 GroupLens에서 제공한다.

1. 아래 주소에서 `ml-20m.zip`을 다운로드한다.

```text
https://grouplens.org/datasets/movielens/20m/
```

2. 압축을 풀면 `ratings.csv` 파일이 있다.

```text
ml-20m/ratings.csv
```

3. `ratings.csv`를 master 컨테이너로 복사한다.

```bash
docker cp /path/to/ml-20m/ratings.csv m5-master:/data/ratings.csv
```

복사 여부를 확인한다.

```bash
docker exec m5-master ls -lh /data/ratings.csv
```

## 3. 평점 데이터 파일을 HDFS에 업로드하는 방법

이 작업 스크립트는 입력 파일을 실행 시점에 자동으로 HDFS에 업로드한다. HDFS 입력 경로는 다음과 같이 생성된다.

```text
/user/root/movielen/input/<RUN_ID>/
```

`run_movielen.sh`를 쓰지 않고 수동으로 업로드하려면 아래처럼 실행한다.

```bash
docker exec m5-master hdfs dfs -mkdir -p /user/root/movielen/input/manual
docker exec m5-master hdfs dfs -put /data/ratings.csv /user/root/movielen/input/manual/
```

업로드 결과를 확인한다.

```bash
docker exec m5-master hdfs dfs -ls /user/root/movielen/input/manual
```

## 4. Python Mapper와 Reducer 실행 준비 방법

Mapper와 Reducer는 Python 스크립트라 별도 컴파일이 필요 없다. Docker 이미지에는 아래 파일이 포함된다.

```text
src/mapper.py             -> /opt/movielen/src/mapper.py
src/reducer.py            -> /opt/movielen/src/reducer.py
scripts/run_movielen.sh   -> /opt/movielen/scripts/run_movielen.sh
```

준비 상태를 확인한다.

```bash
docker exec m5-master ls -al /opt/movielen/src /opt/movielen/scripts
```

`mapper.py`와 `reducer.py`를 수정했다면 이미지를 다시 빌드하고 컨테이너를 재생성해야 한다.

```bash
docker compose build
docker compose up -d
```

## 5. Hadoop Streaming을 이용하여 MapReduce 작업을 실행하는 방법

master 컨테이너에서 실행 스크립트를 호출한다.

```bash
docker exec -it m5-master \
	/opt/movielen/scripts/run_movielen.sh \
	/data/ratings.csv
```

스크립트 내부 동작은 다음과 같다.

1. `/user/root/movielen/input/<RUN_ID>/`에 CSV 파일 업로드
2. Hadoop Streaming jar로 `mapper.py`, `reducer.py` 실행
3. `/user/root/movielen/output/<RUN_ID>/`에 결과 저장
4. HDFS 결과를 `/opt/movielen/results/result_<RUN_ID>.tsv`로 병합 저장
5. 결과 상위 20줄 출력

정상 실행 시 출력은 아래처럼 영화 ID와 평균 평점 형태가 된다.

```text
1    3.92
2    3.18
10   4.05
```

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

Applications 목록에서 방금 실행한 작업을 선택하면 상태, 진행률, 로그를 볼 수 있다.

CLI로 확인하려면 아래 명령을 사용한다.

```bash
docker exec m5-master yarn application -list -appStates ALL
```

특정 애플리케이션 로그가 필요하면 `application_...` ID를 넣어 조회한다.

```bash
docker exec m5-master yarn logs -applicationId <APPLICATION_ID>
```

## 7. HDFS에서 출력 결과를 조회하는 방법

실행 결과 목록을 확인한다.

```bash
docker exec m5-master hdfs dfs -ls /user/root/movielen/output
```

특정 실행 결과를 조회한다.

```bash
docker exec m5-master hdfs dfs -cat /user/root/movielen/output/<RUN_ID>/part-*
```

출력 예시는 아래와 같다.

```text
1    3.92
2    3.18
10   4.05
```

입력 파일도 다시 확인할 수 있다.

```bash
docker exec m5-master hdfs dfs -ls /user/root/movielen/input/<RUN_ID>
```

## 8. 출력 결과를 로컬 파일로 가져오는 방법

`run_movielen.sh`는 실행 결과를 자동으로 컨테이너 내부의 `/opt/movielen/results/result_<RUN_ID>.tsv` 파일로 저장한다. 컨테이너 안에서 결과 파일 목록을 확인한다.

```bash
docker exec m5-master ls -lh /opt/movielen/results
```

호스트로 복사한다.

```bash
docker cp m5-master:/opt/movielen/results/result_<RUN_ID>.tsv \
	./result_<RUN_ID>.tsv
```

HDFS 결과를 직접 병합해서 다른 위치에 저장할 수도 있다.

```bash
docker exec m5-master hdfs dfs -getmerge \
	/user/root/movielen/output/<RUN_ID> \
	/root/movielen_result_<RUN_ID>.tsv

docker cp m5-master:/root/movielen_result_<RUN_ID>.tsv \
	./movielen_result_<RUN_ID>.tsv
```

## 9. 영화별 평균 평점 결과를 해석하는 방법

이 작업은 영화별로 평점을 평균 내는 집계 작업이다. 따라서 출력의 각 줄은 아래 의미를 가진다.

```text
movieId    average_rating
```

예를 들어 아래 출력이 있다면,

```text
50    4.0
```

`movieId = 50`인 영화의 평균 평점이 `4.0`이라는 뜻이다. MovieLens 원본 파일의 `movieId`는 영화 제목이 아니라 영화 식별자이므로, 영화 이름이 필요하면 `movies.csv`를 별도로 참조해야 한다.

## 10. 계산 결과의 정확성을 검증하는 방법

가장 쉬운 검증 방법은 작은 샘플을 직접 계산해서 비교하는 것이다.

예를 들어 아래 입력이 있다고 가정한다.

```text
userId,movieId,rating,timestamp
1,50,4.0,1112486027
2,50,3.0,1112484676
3,10,5.0,1112484819
```

이때 기대 결과는 아래와 같다.

```text
10    5.0
50    3.5
```

검증 방법은 다음과 같다.

1. 샘플 CSV를 만들어 `/data/sample_ratings.csv`로 복사한다.
2. `run_movielen.sh`를 샘플 파일에 실행한다.
3. 출력된 평균값을 직접 계산한 값과 비교한다.

추가로 Mapper와 Reducer를 파이프로 연결해 로컬 검증도 할 수 있다.

```bash
docker exec m5-master sh -c \
	"cat /data/sample_ratings.csv \
	| /opt/movielen/src/mapper.py \
	| sort \
	| /opt/movielen/src/reducer.py"
```

정확성을 더 엄밀하게 확인하려면 Python이나 pandas로 같은 입력 파일을 읽어 영화별 평균을 계산한 뒤, Hadoop Streaming 결과와 비교하면 된다.
