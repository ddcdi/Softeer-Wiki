#!/bin/bash

# ---------------------------------------------------------
# ROLE 환경변수로 이 컨테이너가 master인지 worker인지 판단
# docker-compose.yml에서 각 서비스마다 이 값을 다르게 주입함
#   master  -> ROLE=master
#   worker1, worker2 -> ROLE=worker
# ---------------------------------------------------------
echo ">>> 이 컨테이너의 ROLE = ${ROLE}"

if [ "$ROLE" = "master" ]; then

    # -----------------------------------------------------
    # [master] 1. NameNode 저장 경로를 "설정값에서" 동적으로 읽음
    #   설정 변경 스크립트가 dfs.namenode.name.dir 값을 바꿀 수 있으므로,
    #   경로를 하드코딩하지 않고 매번 실제 설정을 조회해서 판단함.
    #   (file:// 접두사가 붙어있는 경우 제거하고 순수 경로만 사용)
    # -----------------------------------------------------
    NAME_DIR=$(hdfs getconf -confKey dfs.namenode.name.dir 2>/dev/null | sed 's#^file://##')

    if [ -z "$NAME_DIR" ]; then
        echo ">>> [master] WARNING: dfs.namenode.name.dir 조회 실패, 기본 경로 사용"
        NAME_DIR="/root/hdfs/namenode"
    fi
 
    mkdir -p "$NAME_DIR"


    if [ ! -d "$NAME_DIR/current" ]; then
        echo ">>> [master] NameNode 저장 경로($NAME_DIR)가 아직 포맷되지 않음. 최초 포맷을 진행합니다."
        hdfs namenode -format -force
    else
        echo ">>> [master] 이미 포맷된 NameNode 발견($NAME_DIR). 포맷을 건너뜁니다."
    fi

    # -----------------------------------------------------
    # [master] 2. 마스터 전용 데몬만 직접 실행
    #   start-dfs.sh / start-yarn.sh (SSH로 workers 순회) 대신
    #   각 데몬을 개별 명령으로 직접 시작 -> SSH 불필요
    # -----------------------------------------------------
    echo ">>> [master] NameNode 시작"
    hdfs --daemon start namenode

    echo ">>> [master] SecondaryNameNode 시작"
    hdfs --daemon start secondarynamenode

    echo ">>> [master] ResourceManager 시작"
    yarn --daemon start resourcemanager

elif [ "$ROLE" = "worker" ]; then

    # -----------------------------------------------------
    # [worker] 1. master의 NameNode가 뜰 시간을 잠깐 기다림
    #   DataNode/NodeManager는 연결 실패시 자동 재시도하지만,
    #   초반 에러 로그를 줄이기 위해 짧게 대기
    # -----------------------------------------------------
    echo ">>> [worker] master 준비를 위해 10초 대기"
    sleep 10
    
    # -----------------------------------------------------
    # [worker] 2. DataNode 시작
    #   NameNode가 재포맷되어 클러스터 ID가 바뀐 경우, 기존 DataNode
    #   저장소와 맞지 않아 시작에 실패할 수 있음. 이 경우 로컬 저장소를
    #   한 번 비우고 재시도해서 새 클러스터에 다시 등록되게 함.
    #   (평소 재시작 시에는 클러스터 ID가 그대로라 이 분기를 안 타고,
    #    기존 데이터는 그대로 보존됨)
    # -----------------------------------------------------
    DATA_DIR=$(hdfs getconf -confKey dfs.datanode.data.dir 2>/dev/null | sed 's#^file://##')
 
    echo ">>> [worker] DataNode 시작"
    hdfs --daemon start datanode
    sleep 5
 
    if ! jps | grep -q DataNode; then
        echo ">>> [worker] DataNode 시작 실패 감지 (클러스터 ID 불일치 가능성) - 로컬 저장소 초기화 후 재시도"
        if [ -n "$DATA_DIR" ] && [ -d "$DATA_DIR" ]; then
            rm -rf "${DATA_DIR:?}"/*
        fi
        hdfs --daemon start datanode
    fi
 
    echo ">>> [worker] NodeManager 시작"
    yarn --daemon start nodemanager

else
    echo ">>> ERROR: ROLE 환경변수가 설정되지 않았습니다 (master 또는 worker 필요)"
    exit 1
fi

# ---------------------------------------------------------
# 상태 확인 (docker logs로 확인 가능)
# ---------------------------------------------------------
echo ">>> 실행 중인 Java 프로세스 목록:"
jps

# ---------------------------------------------------------
# 컨테이너를 계속 살려두기 (데몬들은 백그라운드 프로세스라서 필요)
# ---------------------------------------------------------
tail -f /dev/null