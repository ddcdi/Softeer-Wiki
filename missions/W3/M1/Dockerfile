FROM ubuntu:22.04

# ---------------------------------------------------------
# 1. 기본 패키지 + Java + SSH 설치
#    - openjdk-11-jdk : Hadoop 실행에 필요한 JVM
#    - openssh-server/client : Hadoop 데몬 간 통신(localhost 포함)에 필요
#    - net-tools, vim : 디버깅/편집용 (없어도 되지만 학습 중엔 편함)
#    - DEBIAN_FRONTEND=noninteractive : apt 설치 중 대화형 프롬프트 방지
# ---------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    openjdk-11-jdk \
    openssh-server \
    openssh-client \
    wget \
    net-tools \
    vim \
    sudo \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------
# 2. 환경변수 설정
#    JAVA_HOME은 설치된 JDK 경로를 실제로 확인해서 넣어야 함
#    (버전 올리면 이 경로도 같이 바뀌어야 함)
# ---------------------------------------------------------

# ---------------------------------------------------------
# 2-1. JAVA_HOME 설정
#    아키텍처와 상관없는 심볼릭 링크를 만들어 /usr/lib/jvm/java-11-openjdk로 연결
# ---------------------------------------------------------
RUN ln -s $(dirname $(dirname $(readlink -f $(which java)))) /usr/lib/jvm/java-11-openjdk
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk

ENV HADOOP_VERSION=3.3.6
ENV HADOOP_HOME=/opt/hadoop
ENV HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
ENV PATH=$PATH:$JAVA_HOME/bin:$HADOOP_HOME/bin:$HADOOP_HOME/sbin

# ---------------------------------------------------------
# 2-2. root 계정으로 Hadoop 데몬 실행을 허용
#      Hadoop 3.x부터는 안전장치로 root 실행을 기본 차단하는데,
#      학습용 단일 노드 컨테이너는 별도 사용자를 만들지 않고 root로만
#      동작하므로, 각 데몬 역할별로 "root로 실행해도 된다"고 명시해야 함.
#      (운영 클러스터에서는 hdfs/yarn 같은 전용 계정을 쓰는 게 정석)
# ---------------------------------------------------------

ENV HDFS_NAMENODE_USER=root
ENV HDFS_DATANODE_USER=root
ENV HDFS_SECONDARYNAMENODE_USER=root
ENV YARN_RESOURCEMANAGER_USER=root
ENV YARN_NODEMANAGER_USER=root

# ---------------------------------------------------------
# 3. Hadoop 다운로드 및 설치
#    공식 아카이브 미러에서 tar.gz를 받아 /opt/hadoop 에 풀어줌
# ---------------------------------------------------------
RUN wget -q https://downloads.apache.org/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz \
    && tar -xzf hadoop-${HADOOP_VERSION}.tar.gz -C /opt \
    && mv /opt/hadoop-${HADOOP_VERSION} $HADOOP_HOME \
    && rm hadoop-${HADOOP_VERSION}.tar.gz

# ---------------------------------------------------------
# 4. SSH 설정 (passwordless SSH)
#    Hadoop 시작 스크립트가 ssh localhost 로 각 데몬을 띄우기 때문에
#    비밀번호 없이 로그인 가능해야 함
# ---------------------------------------------------------

# 4-1. sshd가 사용할 호스트 키 생성 (사용자 키와는 별개, sshd 자체에 필요)
RUN ssh-keygen -A
 
# 4-2. root 계정 SSH 로그인 허용
#      Ubuntu 기본 설정은 root의 SSH 로그인을 막아두므로 명시적으로 열어줘야 함
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
 
# 4-3. 사용자(root)용 SSH 키 생성 + 자기 자신을 인증 목록에 등록 (passwordless)
RUN ssh-keygen -t rsa -P '' -f ~/.ssh/id_rsa \
    && cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys \
    && chmod 0600 ~/.ssh/authorized_keys \
    && chmod 700 ~/.ssh
 
# 4-4. 처음 접속 시 뜨는 host key 확인 프롬프트를 자동화 환경에서 끄기
#      (자동 스크립트가 "yes/no" 입력을 기다리며 멈추는 걸 방지)
#      printf로 명확하게 개행을 넣어 셸마다 \n 해석이 달라지는 문제를 피함
RUN printf 'Host localhost\n\tStrictHostKeyChecking no\nHost 0.0.0.0\n\tStrictHostKeyChecking no\n' >> ~/.ssh/config \
    && chmod 600 ~/.ssh/config

# ---------------------------------------------------------
# 5. Hadoop 설정 파일 복사
#    config/ 폴더에 미리 작성해둔 xml들을 $HADOOP_CONF_DIR로 복사
# ---------------------------------------------------------
COPY config/core-site.xml $HADOOP_CONF_DIR/core-site.xml
COPY config/hdfs-site.xml $HADOOP_CONF_DIR/hdfs-site.xml
COPY config/mapred-site.xml $HADOOP_CONF_DIR/mapred-site.xml
COPY config/yarn-site.xml $HADOOP_CONF_DIR/yarn-site.xml

# JAVA_HOME을 hadoop-env.sh에도 명시 (Hadoop 스크립트가 이 파일을 읽음)
RUN echo "export JAVA_HOME=$JAVA_HOME" >> $HADOOP_CONF_DIR/hadoop-env.sh

# ---------------------------------------------------------
# 6. HDFS 데이터 디렉토리 생성 (hdfs-site.xml에서 지정할 경로와 일치해야 함)
# ---------------------------------------------------------
RUN mkdir -p /root/hdfs/namenode /root/hdfs/datanode

# ---------------------------------------------------------
# 7. 시작 스크립트 등록
# ---------------------------------------------------------
COPY start-hadoop.sh /root/start-hadoop.sh
RUN chmod +x /root/start-hadoop.sh

# Web UI(9870, 9868), ResourceManager UI(8088), HDFS RPC(9000) 등 노출
EXPOSE 9870 9868 8088 9000 8042 19888

CMD ["/root/start-hadoop.sh"]