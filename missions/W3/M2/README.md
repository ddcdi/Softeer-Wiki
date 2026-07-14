## 1. 설정 변경 스크립트 실행 방법
 
**호스트(맥) 터미널에서, `docker-compose.yml`이 있는 프로젝트 루트 디렉토리에서** 실행.
 
```bash
cd M2
python3 assignment/configure_hadoop.py conf
```
 
**딱 한 번만 실행하면 된다.** master/worker1/worker2에 각각 따로 실행할 필요가 없다.
— `conf/`가 3개 컨테이너 전체에 bind mount로 공유되기 때문.
 
### 동작 내용
 
1. `conf/` 안의 `core-site.xml`, `hdfs-site.xml`, `mapred-site.xml`,
   `yarn-site.xml`을 각각 백업 (`파일명.xml.bak.<타임스탬프>`)
2. 요구된 설정값으로 XML 수정 (기존 property가 있으면 값만 교체, 없으면 새로 추가)
3. `docker compose restart` 호출 → master, worker1, worker2 전체가 재시작되며,
   각 컨테이너의 시작 스크립트(`start-hadoop.sh`)가 새 설정을 읽어 Hadoop 데몬을
   다시 띄움
4. 각 설정 변경 성공/실패 요약 출력
### 변경되는 설정값
 
| 파일 | 키 | 값 |
|---|---|---|
| core-site.xml | fs.defaultFS | hdfs://namenode:9000 |
| core-site.xml | hadoop.tmp.dir | /hadoop/tmp |
| core-site.xml | io.file.buffer.size | 131072 |
| hdfs-site.xml | dfs.replication | 2 |
| hdfs-site.xml | dfs.blocksize | 134217728 |
| hdfs-site.xml | dfs.namenode.name.dir | /hadoop/dfs/name |
| mapred-site.xml | mapreduce.framework.name | yarn |
| mapred-site.xml | mapreduce.jobhistory.address | namenode:10020 |
| mapred-site.xml | mapreduce.task.io.sort.mb | 256 |
| yarn-site.xml | yarn.resourcemanager.address | namenode:8032 |
| yarn-site.xml | yarn.nodemanager.resource.memory-mb | 8192 |
| yarn-site.xml | yarn.scheduler.minimum-allocation-mb | 1024 |
 
---
 
## 2. 검증 스크립트 실행 방법
 
설정 변경 스크립트 실행 후, 클러스터가 재시작을 마칠 시간을 조금 기다린 뒤
(약 20~30초) **master 컨테이너 안에서** 실행.
 
```bash
docker exec -it master python3 /assignment/verify_hadoop.py
```
 
### 검증 항목
 
1. 설정값 12개 확인 (core/hdfs 6개는 `hdfs getconf`, mapred/yarn 6개는 xml 직접 확인)
2. 기본 파일시스템(`fs.defaultFS`) 실제 접근 가능 여부 (`hdfs dfs -ls /`)
3. 테스트 파일 생성 후 실제 Replication Factor 확인
4. Pi 예제 MapReduce Job 실행 → YARN 위에서 정상 완료되는지 확인
5. ResourceManager REST API로 클러스터 전체 메모리(totalMB) 조회
### 출력 예시
 
```
[1] 설정값 검증 (core/hdfs)
PASS: ['hdfs', 'getconf', '-confKey', 'fs.defaultFS'] -> hdfs://namenode:9000
PASS: ['hdfs', 'getconf', '-confKey', 'hadoop.tmp.dir'] -> /hadoop/tmp
PASS: ['hdfs', 'getconf', '-confKey', 'io.file.buffer.size'] -> 131072
PASS: ['hdfs', 'getconf', '-confKey', 'dfs.replication'] -> 2
PASS: ['hdfs', 'getconf', '-confKey', 'dfs.blocksize'] -> 134217728
PASS: ['hdfs', 'getconf', '-confKey', 'dfs.namenode.name.dir'] -> /hadoop/dfs/name
 
[1-2] 설정값 검증 (mapred/yarn, xml 직접 확인)
PASS: [mapred-site.xml] mapreduce.framework.name -> yarn
PASS: [mapred-site.xml] mapreduce.jobhistory.address -> namenode:10020
PASS: [mapred-site.xml] mapreduce.task.io.sort.mb -> 256
PASS: [yarn-site.xml] yarn.resourcemanager.address -> namenode:8032
PASS: [yarn-site.xml] yarn.nodemanager.resource.memory-mb -> 8192
PASS: [yarn-site.xml] yarn.scheduler.minimum-allocation-mb -> 1024
 
[2] 기본 파일시스템 동작 확인
PASS: ['hdfs', 'dfs', '-ls', '/'] -> 정상 응답 (기본 파일시스템 접근 가능)
 
[3] HDFS 복제 계수(Replication Factor) 확인
PASS: Replication factor is 2
 
[4] MapReduce Job 실행 확인 (YARN 프레임워크 사용 여부)
PASS: MapReduce Job(pi) 정상 실행됨 (YARN 프레임워크 사용)
 
[5] YARN 클러스터 메모리 확인
INFO: http://namenode:8088/ws/v1/cluster/metrics -> totalMB = 16384
PASS: YARN 클러스터 전체 메모리 조회 성공 (totalMB=16384)
 
=== 검증 결과: PASS 16 / FAIL 0 ===
```
 
종료 코드가 `0`이면 전체 PASS, `1`이면 하나 이상 FAIL이 있다는 뜻.
 
---
 
## 3. Hadoop 클러스터 설정 방법
 
```bash
# 1) 클러스터 기동 (최초 실행이거나, Dockerfile/compose를 바꿨다면 재빌드)
docker compose down
docker compose build --no-cache
docker compose up -d
 
# 2) 설정 변경 스크립트 실행 (호스트에서, 딱 한 번)
python3 assignment/configure_hadoop.py conf
 
# 3) 재시작 완료 대기 후 데몬 상태 확인
sleep 20
docker exec -it master jps
docker exec -it worker1 jps
docker exec -it worker2 jps
 
# 4) 검증
docker exec -it master python3 /assignment/verify_hadoop.py
```
 
---
 
## 4. 테스트 수행 방법
 
전체 시나리오를 처음부터 끝까지 한 번에 재현하려면:
 
```bash
# 1. 클러스터 완전 초기화 후 재기동
docker compose down
docker compose build --no-cache
docker compose up -d
sleep 20
 
# 2. 변경 전 상태 확인 (선택 - 기대한 대로 아직 바뀌지 않았는지)
docker exec -it master hdfs getconf -confKey fs.defaultFS
# -> hdfs://master:9000 (아직 원래 값)
 
# 3. 설정 변경 실행
python3 assignment/configure_hadoop.py conf
 
# 4. 재시작 대기
sleep 20
 
# 5. 데몬 재기동 확인
docker exec -it master jps
docker exec -it worker1 jps
docker exec -it worker2 jps
 
# 6. 검증 스크립트 실행
docker exec -it master python3 /assignment/verify_hadoop.py
 
# 7. 종료 코드 확인
docker exec -it master python3 /assignment/verify_hadoop.py; echo "종료 코드: $?"
```
 
`종료 코드: 0`이 나오면 전체 테스트 통과입니다.
 
---