#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
    echo ">>> 사용법: $0 <HDFS 집계 결과 디렉터리>"
    exit 1
fi

HDFS_OUTPUT_DIR="$1"

if ! hdfs dfs -test -e "$HDFS_OUTPUT_DIR"; then
    echo ">>> ERROR: HDFS 결과 경로를 찾을 수 없습니다: $HDFS_OUTPUT_DIR"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RESULT_DIR="$SCRIPT_DIR/../results"
mkdir -p "$RESULT_DIR"
RESULT_DIR="$(cd "$RESULT_DIR" && pwd)"

RUN_ID="$(basename "$HDFS_OUTPUT_DIR")"
MERGED_RESULT_FILE="${RESULT_DIR}/result_${RUN_ID}.tsv"
SORTED_RESULT_FILE="${RESULT_DIR}/result_${RUN_ID}_sorted.tsv"
HDFS_SORTED_OUTPUT_DIR="/user/root/amazon_reviews/sorted/${RUN_ID}"
HDFS_SORTED_OUTPUT_FILE="${HDFS_SORTED_OUTPUT_DIR}/$(basename "$SORTED_RESULT_FILE")"

echo ">>> [1/3] HDFS 집계 결과 병합: ${HDFS_OUTPUT_DIR} -> ${MERGED_RESULT_FILE}"
hdfs dfs -getmerge "$HDFS_OUTPUT_DIR" "$MERGED_RESULT_FILE"

echo ">>> [2/3] 리뷰 수 기준 내림차순 정렬: ${SORTED_RESULT_FILE}"
sort -t $'\t' -k2,2nr -k1,1 "$MERGED_RESULT_FILE" > "$SORTED_RESULT_FILE"

echo ">>> [3/4] 정렬 결과를 HDFS에 저장: ${HDFS_SORTED_OUTPUT_DIR}"
hdfs dfs -mkdir -p "$HDFS_SORTED_OUTPUT_DIR"
hdfs dfs -put -f "$SORTED_RESULT_FILE" "$HDFS_SORTED_OUTPUT_FILE"

echo ">>> [4/4] 컨테이너에서 정렬 결과 전체 출력"
cat "$SORTED_RESULT_FILE"

echo ">>> [4/4] HDFS에 저장된 정렬 결과 출력"
hdfs dfs -cat "$HDFS_SORTED_OUTPUT_FILE"

echo ">>> 저장된 병합 파일: ${MERGED_RESULT_FILE}"
echo ">>> 저장된 정렬 파일: ${SORTED_RESULT_FILE}"
echo ">>> HDFS 정렬 결과 파일: ${HDFS_SORTED_OUTPUT_FILE}"
