#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
    echo ">>> 사용법: $0 <컨테이너 안의 입력 txt 파일 경로>"
    exit 1
fi

LOCAL_INPUT="$1"

if [ ! -f "$LOCAL_INPUT" ]; then
    echo ">>> ERROR: 입력 파일을 찾을 수 없습니다: $LOCAL_INPUT"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../src" && pwd)"

RUN_ID="$(date +%Y%m%d_%H%M%S)"
INPUT_DIR="/user/root/wordcount/input/${RUN_ID}"
OUTPUT_DIR="/user/root/wordcount/output/${RUN_ID}"

STREAMING_JAR=$(ls "${HADOOP_HOME}"/share/hadoop/tools/lib/hadoop-streaming-*.jar 2>/dev/null | head -n1)

if [ -z "$STREAMING_JAR" ]; then
    echo ">>> ERROR: hadoop-streaming jar를 찾을 수 없습니다 (\$HADOOP_HOME/share/hadoop/tools/lib/)"
    exit 1
fi

echo ">>> [1/3] HDFS 입력 경로 업로드: ${INPUT_DIR}"
hdfs dfs -mkdir -p "$INPUT_DIR"
hdfs dfs -put "$LOCAL_INPUT" "$INPUT_DIR/"

echo ">>> [2/3] Hadoop Streaming Word Count 실행 (output: ${OUTPUT_DIR})"
hadoop jar "$STREAMING_JAR" \
    -files "${SRC_DIR}/mapper.py,${SRC_DIR}/reducer.py" \
    -mapper "python3 mapper.py" \
    -reducer "python3 reducer.py" \
    -input "$INPUT_DIR" \
    -output "$OUTPUT_DIR"

echo ">>> [3/3] 결과 미리보기 (상위 20줄)"
hdfs dfs -cat "${OUTPUT_DIR}/part-"* | head -n 20

echo ">>> 전체 결과 확인: hdfs dfs -cat ${OUTPUT_DIR}/part-*"
