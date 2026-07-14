# W3/M3 — Hadoop Streaming Word Count

4-node Hadoop 클러스터(master 1 + worker 3) 위에서, Python Mapper/Reducer를
Hadoop Streaming으로 실행해 전자책(txt) 파일의 단어 빈도를 계산하는 job.

## 1. 프로그램 실행 환경 구성 방법

`docker-compose.yaml`이 정의하는 4개 컨테이너로 구성된다.

| 서비스 | 컨테이너 이름 | hostname | 역할 |
|---|---|---|---|
| master | `m3-master` | `namenode` | NameNode, SecondaryNameNode, ResourceManager |
| worker1 | `m3-worker1` | `worker1` | DataNode, NodeManager |
| worker2 | `m3-worker2` | `worker2` | DataNode, NodeManager |
| worker3 | `m3-worker3` | `worker3` | DataNode, NodeManager |

모두 같은 이미지(`w3m3:latest`)를 사용하며, `master`만 호스트에 포트를
공개한다(`9870` HDFS UI, `8088` YARN UI, `9000` HDFS RPC).

```bash
cd missions/W3/M3

# 최초 실행이거나 Dockerfile/config/src/scripts를 바꿨다면 재빌드
docker compose build --no-cache
docker compose up -d

# 데몬이 완전히 뜰 때까지 대기 (약 20~30초)
sleep 20
```
## 2. 프로그램 컴파일 또는 실행 준비 방법

Mapper/Reducer는 Python 스크립트이므로 별도 컴파일이 필요 없다. 대신
`Dockerfile`이 이미지 빌드 시점에 아래 파일들을 컨테이너 안으로 복사하고
실행 권한을 부여해둔다.

```
src/mapper.py             -> /opt/wordcount/src/mapper.py
src/reducer.py            -> /opt/wordcount/src/reducer.py
scripts/run_wordcount.sh  -> /opt/wordcount/scripts/run_wordcount.sh   (chmod +x 적용됨)
```

`mapper.py`, `reducer.py`, `run_wordcount.sh` 중 하나라도 수정했다면, 위
"환경 구성" 단계의 `docker compose build --no-cache && docker compose up -d`를
다시 실행해서 새 내용을 이미지에 반영해야 한다. 준비가 끝났는지는 아래로
확인한다.

```bash
docker exec m3-master ls -al /opt/wordcount/src /opt/wordcount/scripts
```

## 3. 입력 전자책 파일을 HDFS에 업로드하는 방법

먼저 호스트에 있는 txt 파일을 `m3-master` 컨테이너 내부로 복사한다.

```bash
docker cp /path/to/moby_dick.txt m3-master:/data/wordcount/moby_dick.txt
```

HDFS 업로드 자체는 4번 단계의 `run_wordcount.sh`가 실행마다 자동으로
수행한다 (아래 위치에, 실행마다 새 타임스탬프 디렉토리를 만들어 업로드):

```
/user/root/wordcount/input/<RUN_ID>/moby_dick.txt
```

## 4. MapReduce 작업을 실행하는 방법

`master` 컨테이너 안에서, 업로드 → Streaming job 실행 → 결과 미리보기를
한 번에 처리하는 스크립트를 실행한다.

```bash
docker exec -it m3-master /opt/wordcount/scripts/run_wordcount.sh /data/wordcount/moby_dick.txt
```

내부 동작:

1. HDFS에 `/user/root/wordcount/input/<RUN_ID>/`를 만들고 파일 업로드
2. `hadoop jar hadoop-streaming-*.jar -mapper "python3 mapper.py" -reducer "python3 reducer.py" ...` 로 job 제출
3. `/user/root/wordcount/output/<RUN_ID>/` 결과 중 상위 20줄 미리보기 출력

실행마다 `RUN_ID`(타임스탬프)가 새로 생성되므로, 같은 파일로 여러 번
실행해도 이전 결과를 덮어쓰지 않는다.

## 5. 작업 진행 상황을 확인하는 방법

**터미널에서 실시간 확인**: `run_wordcount.sh`를 실행 중인 터미널에
Hadoop Streaming이 map/reduce 진행률(`map 0% reduce 0%` → `map 100%
reduce 100%`)을 직접 출력한다.

**YARN Web UI에서 확인**: 브라우저로 `http://localhost:8088` 접속 →
Applications 목록에서 방금 실행한 job을 클릭하면 상태(`RUNNING` /
`FINISHED`), 진행률, 컨테이너별 로그를 볼 수 있다.

**CLI로 확인**: 별도 터미널에서

```bash
docker exec m3-master yarn application -list -appStates ALL
```

## 6. HDFS에서 출력 결과를 확인하는 방법

지금까지의 실행 목록(`RUN_ID` 목록) 확인:

```bash
docker exec m3-master hdfs dfs -ls /user/root/wordcount/output
```

특정 실행의 전체 결과 확인:

```bash
docker exec m3-master hdfs dfs -cat /user/root/wordcount/output/<RUN_ID>/part-*
```

예시 (Moby Dick 기준, 상위 10개 단어):

```
the	14727
of	6746
and	6515
a	4805
to	4709
in	4244
that	3100
it	2537
his	2532
i	2127
```

## 7. 출력 결과를 로컬 파일로 가져오는 방법

먼저 `master` 컨테이너 안에서 HDFS의 여러 파트 파일을 하나로 합쳐
컨테이너 로컬 파일로 받는다.

```bash
docker exec m3-master hdfs dfs -getmerge \
    /user/root/wordcount/output/<RUN_ID> \
    /root/wordcount_result_<RUN_ID>.txt
```

그 다음, 호스트(맥)로 복사한다.

```bash
docker cp m3-master:/root/wordcount_result_<RUN_ID>.txt ./wordcount_result_<RUN_ID>.txt
```

## 8. 결과의 정확성을 검증하는 방법

**(1) 총 토큰 수 일치 검증** — Reducer가 만든 모든 단어의 카운트 합은,
Mapper가 만든 전체 토큰(단어) 수와 정확히 같아야 한다(reduce는 map
결과를 합산만 하므로).

```bash
# 로컬에서 mapper만 돌려서 전체 토큰 수 계산
python3 missions/W3/M3/src/mapper.py < /path/to/moby_dick.txt | wc -l

# HDFS 결과의 카운트 합계 계산
docker exec m3-master hdfs dfs -cat /user/root/wordcount/output/<RUN_ID>/part-* \
    | awk -F'\t' '{sum += $2} END {print sum}'
```

두 값이 정확히 같으면, MapReduce가 토큰을 누락/중복 없이 집계했다는 뜻이다.

**(2) 특정 단어 스팟 체크** — 임의의 단어 하나를 골라, 로컬에서 같은
mapper 로직으로 계산한 값과 HDFS 결과값을 직접 비교한다.

```bash
# 로컬에서 "whale" 토큰 개수 계산
python3 missions/W3/M3/src/mapper.py < /path/to/moby_dick.txt | grep -P '^whale\t' | wc -l

# HDFS 결과에서 "whale" 라인 확인
docker exec m3-master hdfs dfs -cat /user/root/wordcount/output/<RUN_ID>/part-* \
    | grep -P '^whale\t'
```

두 값이 일치하면 해당 단어에 대해 클러스터가 계산한 결과가 정확하다는
뜻이다.

## Mapper / Reducer 동작

- `src/mapper.py`: 각 줄을 소문자로 변환한 뒤 `[a-z0-9]+` 정규식으로
  토큰을 추출해 `word\t1`을 출력한다 (구두점 자동 제거, 대소문자 통합).
- `src/reducer.py`: 정렬된 `word\tcount` 입력을 받아 같은 단어의 개수를
  합산해 `word\ttotal_count`를 출력한다.


# 사용 전자책 정보
전자책 제목: 	Moby-Dick; or, The Whale
한국어 제목:	모비 딕, 혹은 고래
저자:	Herman Melville
언어:	영어
전자책 번호:	Project Gutenberg eBook #2701
최초 공개일:	2001년 7월 1일
최종 업데이트일:	2026년 2월 10일
출처:	Project Gutenberg
전자책 페이지:	https://www.gutenberg.org/ebooks/2701
제공 형식:	일반 텍스트, HTML, EPUB, Kindle 등