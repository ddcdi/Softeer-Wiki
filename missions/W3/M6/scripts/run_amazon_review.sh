#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
    echo ">>> 사용법: $0 <입력 파일 또는 디렉터리 경로>"
    exit 1
fi

LOCAL_INPUT_PATH="$1"

if [ ! -e "$LOCAL_INPUT_PATH" ]; then
    echo ">>> ERROR: 입력 경로를 찾을 수 없습니다: $LOCAL_INPUT_PATH"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../src" && pwd)"

RESULT_DIR="$SCRIPT_DIR/../results"
mkdir -p "$RESULT_DIR"
RESULT_DIR="$(cd "$RESULT_DIR" && pwd)"

RUN_ID="$(date +%Y%m%d_%H%M%S)"
INPUT_DIR="/user/root/amazon_reviews/input/${RUN_ID}"
OUTPUT_DIR="/user/root/amazon_reviews/output/${RUN_ID}"
RESULT_FILE="${RESULT_DIR}/result_${RUN_ID}.tsv"

STREAMING_JAR=$(ls "${HADOOP_HOME}"/share/hadoop/tools/lib/hadoop-streaming-*.jar 2>/dev/null | head -n1)

if [ -z "$STREAMING_JAR" ]; then
    echo ">>> ERROR: hadoop-streaming jar를 찾을 수 없습니다 (\$HADOOP_HOME/share/hadoop/tools/lib/)"
    exit 1
fi

echo ">>> [1/4] HDFS 입력 경로 업로드: ${INPUT_DIR}"
hdfs dfs -mkdir -p "$INPUT_DIR"

shopt -s nullglob
INPUT_FILES=()

if [ -d "$LOCAL_INPUT_PATH" ]; then
    for ext in jsonl json txt; do
        for f in "$LOCAL_INPUT_PATH"/*."$ext"; do
            [ -f "$f" ] && INPUT_FILES+=("$f")
        done
    done

    if [ ${#INPUT_FILES[@]} -eq 0 ]; then
        echo ">>> ERROR: 디렉터리에 업로드할 입력 파일(.jsonl/.json/.txt)이 없습니다: $LOCAL_INPUT_PATH"
        exit 1
    fi

    echo ">>>   - 디렉터리 모드: ${#INPUT_FILES[@]}개 파일 업로드"
    hdfs dfs -put "${INPUT_FILES[@]}" "$INPUT_DIR/"
else
    echo ">>>   - 단일 파일 모드 업로드: $LOCAL_INPUT_PATH"
    hdfs dfs -put "$LOCAL_INPUT_PATH" "$INPUT_DIR/"
fi
shopt -u nullglob

echo ">>> [2/4] Hadoop Streaming 집계 실행 (output: ${OUTPUT_DIR})"
hadoop jar "$STREAMING_JAR" \
    -files "${SRC_DIR}/mapper.py,${SRC_DIR}/reducer.py" \
    -mapper "python3 mapper.py" \
    -reducer "python3 reducer.py" \
    -input "$INPUT_DIR" \
    -output "$OUTPUT_DIR"

echo ">>> [3/4] 결과 병합 후 컨테이너 로컬 파일로 저장: ${RESULT_FILE}"
hdfs dfs -getmerge "$OUTPUT_DIR" "$RESULT_FILE"

echo ">>> [4/4] 결과 미리보기 (상위 20줄)"
head -n 20 "$RESULT_FILE"

echo ">>> 저장된 결과 파일: ${RESULT_FILE}"
