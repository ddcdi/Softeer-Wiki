# ------------------------------------------------------------
# Base image: 도커 공식 spark 이미지 (Python3 포함, 최신 유지보수 중)
#   - amd64 / arm64v8 멀티아키텍처 지원
#   - Spark 4.x(최신 메이저)를 쓰고 싶으면: spark:4.0.3-python3
# ------------------------------------------------------------
FROM spark:3.5.8-python3

# 패키지 설치를 위해 잠시 root로 전환
USER root

# 스파크 기본 작업 디렉터리
WORKDIR /opt/spark/work-dir

# 파이썬 의존성 설치 (requirements.txt에 필요한 패키지 추가)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 스파크 애플리케이션(파이썬 스크립트) 복사
# ./apps 폴더에 .py 파일들을 넣어두면 이미지 안에 함께 들어갑니다.
# COPY ./apps /opt/spark/apps

# 이미지 기본 non-root 유저(spark_uid=185)로 복귀
USER 185