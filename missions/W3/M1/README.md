# Docker 이미지 빌드 방법
## 버전 정하기
- Java: OpenJDK 11 (Hadoop 3.x와 호환 잘 됨)
- Hadoop: 3.3.6 (안정적인 최신 3.x 버전)
- Base OS: Ubuntu 22.04

## SSH 설정 (passwordless SSH)
Hadoop의 start-dfs.sh, start-yarn.sh는 내부적으로 SSH를 통해 각 데몬(NameNode, DataNode 등)을 실행시킨다.  

이때 비밀번호를 입력하지 않고 자동으로 로그인이 되어야 스크립트가 멈추지 않고 끝까지 실행. 이걸 "passwordless SSH" 또는 "SSH 키 기반 인증"

## Docker 이미지 빌드
```
docker build -t w3m1 .
```

# Docker 컨테이너 실행 방법

## 컨테이너 실행
```
docker run -d \
  --name w3 \
  -p 9870:9870 \
  -p 8088:8088 \
  -p 8042:8042 \
  -p 9000:9000 \
  -v hadoop_namenode:/root/hdfs/namenode \
  -v hadoop_datanode:/root/hdfs/datanode \
  w3m1
```

### 데이터 영속성 (-v 호스트경로:컨테이너경로)
도커의 컨테이너는 삭제되면 내부 데이터가 모두 사라진다. 하지만 하둡은 파일 시스템이기 때문에 데이터가 사라지면 안 된다. 그래서 볼륨(Volume)을 사용.

-v hadoop_namenode:/root/hdfs/namenode:

- Docker의 볼륨(Docker Volume)인 hadoop_namenode를 컨테이너 내부의 /root/hdfs/namenode 폴더와 연결.

- 이렇게 하면, 컨테이너를 지웠다가 나중에 다시 실행해도 hadoop_namenode 볼륨에 저장된 파일 시스템 데이터가 그대로 남아있다.

-v hadoop_datanode:/root/hdfs/datanode:

- 실제 데이터 블록이 저장되는 폴더를 컨테이너 외부 볼륨과 연결하여 데이터 손실을 방지.

## 컨테이너 접속
```
docker exec -it w3 bash
```

# HDFS 기본 작업 수행 방법

## 디렉터리 생성
```
hdfs dfs -mkdir -p /user/root/data
```

## 파일 업로드
도커 컨테이너 안에 mtcars.csv 파일이 있다고 가정
```
hdfs dfs -put /tmp/mtcars.csv /user/root/data/
```

## 파일 다운로드(또는 조회)
```
# HDFS 파일 내용 보기
hdfs dfs -cat /user/root/data/mtcars.csv

# HDFS 파일을 로컬로 다시 다운로드
hdfs dfs -get /user/root/data/mtcars.csv /tmp/downloaded.txt
```

## HDFS 안의 파일 목록 보기
```
hdfs dfs -ls /user/root/data
```

## 삭제
```
hdfs dfs -rm /user/root/data/somefile.txt
```

## 용량/상태 확인
```
hdfs dfsadmin -report
```

## Web UI 접속
http://localhost:9870