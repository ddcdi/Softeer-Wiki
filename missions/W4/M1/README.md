# W4/M1 Spark Pi Job

Docker Compose로 Spark master, worker 2개, Spark History Server를 실행하고 `pi_job.py` 작업을 제출한다. 작업은 입력 데이터셋을 읽은 뒤 각 row를 몬테카를로 샘플로 사용해 원주율을 추정하고, 결과를 CSV로 저장한다.

## 구성

- `spark-master`: Spark master, Web UI `http://localhost:8080`
- `spark-worker-1`: worker 1, Web UI `http://localhost:8081`
- `spark-worker-2`: worker 2, Web UI `http://localhost:8082`
- `spark-history`: 완료된 Spark 애플리케이션 로그 UI, `http://localhost:18080`
- `spark-net`: 컨테이너 간 통신용 Docker bridge network

`./apps`는 컨테이너의 `/opt/spark/apps`에 마운트된다. 입력 데이터, 작업 스크립트, 출력 결과를 호스트와 컨테이너가 함께 볼 수 있다.

`./spark-events`는 Spark event log 저장 위치다. 작업 제출 시 event log 옵션을 켜면 History Server에서 완료된 작업을 확인할 수 있다.

## 실행 방법

1. 이미지 빌드

```bash
docker compose build
```

2. Spark 클러스터 실행

```bash
docker compose up -d
```

3. 컨테이너 상태 확인

```bash
docker compose ps
```

Compose 설정이 정상인지 확인하려면 다음 명령을 사용할 수 있다.

```bash
docker compose config
```

4. Spark 작업 제출

```bash
docker exec spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --conf spark.eventLog.enabled=true \
  --conf spark.eventLog.dir=file:/opt/spark/spark-events \
  /opt/spark/apps/pi_job.py \
  /opt/spark/apps/data/input.txt \
  /opt/spark/apps/output/pi_result \
  8
```

5. 실행 결과 확인

```bash
ls -al apps/output/pi_result
cat apps/output/pi_result/part-*.csv
```

결과 CSV 예시는 다음 컬럼을 가진다.

```text
input_path,sample_count,inside_count,pi_estimate
```

## 로그 확인

실행 중인 Spark 애플리케이션은 `http://localhost:4040`에서 확인할 수 있다. 작업이 끝나면 4040 UI는 사라질 수 있으므로 완료된 작업은 `http://localhost:18080`의 Spark History Server에서 확인한다.

컨테이너 로그는 다음 명령으로 확인한다.

```bash
docker compose logs spark-master
docker compose logs spark-worker-1
docker compose logs spark-worker-2
docker compose logs spark-history
```

최근 로그만 보고 싶으면 `--tail`을 사용한다.

```bash
docker compose logs --tail=100 spark-master
```

로그를 계속 따라가려면 `-f`를 사용한다.

```bash
docker compose logs -f spark-worker-1
```

## 오류 처리와 디버깅

컨테이너 간 네트워크 문제가 의심되면 먼저 모든 컨테이너가 같은 Compose 네트워크에 떠 있는지 확인한다.

```bash
docker network inspect spark-net
```

정확한 네트워크 목록은 다음 명령으로 확인한다.

```bash
docker network ls
```

worker가 master에 붙지 않으면 master URL이 `spark://spark-master:7077`인지 확인한다. Compose 내부에서는 서비스명 `spark-master`가 DNS 이름으로 동작한다.

```bash
docker compose logs spark-worker-1
docker compose logs spark-worker-2
```

작업 제출이 실패하면 입력 파일 경로와 출력 경로를 확인한다. 컨테이너 내부 기준 경로는 `/opt/spark/apps/...`이고, 호스트 기준 경로는 `missions/W4/M1/apps/...`이다.

```bash
docker exec spark-master ls -al /opt/spark/apps
docker exec spark-master ls -al /opt/spark/apps/data
```

출력 경로가 이미 있어도 `pi_job.py`는 `overwrite` 모드로 저장하므로 같은 위치에 다시 실행할 수 있다.

입력 데이터셋이 비어 있으면 작업 스크립트가 명시적으로 종료한다.

```text
Input dataset is empty. Monte Carlo estimation requires at least one row.
```

History Server에 작업이 보이지 않으면 Spark 작업 제출 명령에 다음 옵션이 포함되어 있는지 확인한다.

```bash
--conf spark.eventLog.enabled=true
--conf spark.eventLog.dir=file:/opt/spark/spark-events
```

클러스터를 완전히 내릴 때는 다음 명령을 사용한다.

```bash
docker compose down
```
