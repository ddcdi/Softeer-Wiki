FROM quay.io/jupyter/scipy-notebook:latest

# jovyan은 Jupyter Docker 공식 이미지에서 쓰는 기본 리눅스 사용자 계정 이름
WORKDIR /home/jovyan/work

COPY requirements.txt /tmp/requirements.txt

USER root


RUN apt-get update && apt-get install -y --no-install-recommends fonts-nanum \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 시스템 의존성이라 root 필요
RUN python -m playwright install-deps chromium

# 권한 문제가 생기거나 보안상 이유로 root 권한으로 설치하는 것이 꺼려진다면, 아래와 같이 NB_UID를 이용하여 jovyan 계정으로 설치할 수도 있다.
USER ${NB_UID}

RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN python -m playwright install chromium

COPY --chown=jovyan:users mtcars.csv /home/jovyan/work/mtcars.csv
COPY --chown=jovyan:users W1M1.ipynb /home/jovyan/work/W1M1.ipynb
COPY --chown=jovyan:users kakao_review_wordcloud.ipynb /home/jovyan/work/kakao_review_wordcloud.ipynb

CMD ["start-notebook.py", "--ServerApp.ip=0.0.0.0", "--ServerApp.port=8888"]

# start-notebook.py
# → Jupyter 공식 이미지에서 제공하는 실행 스크립트

# --ServerApp.ip=0.0.0.0
# → 컨테이너 외부에서도 접속 가능하게 열기

# --ServerApp.port=8888
# → Jupyter를 컨테이너 내부 8888 포트에서 실행

# --ServerApp.token=
# → 접속 토큰 비우기

# --ServerApp.password=
# → 비밀번호 비우기