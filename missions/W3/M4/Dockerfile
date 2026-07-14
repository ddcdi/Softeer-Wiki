FROM w3m3:latest

# Tweet sentiment count(Hadoop Streaming) job files
COPY src/mapper.py /opt/tweet/src/mapper.py
COPY src/reducer.py /opt/tweet/src/reducer.py
COPY scripts/run_tweet.sh /opt/tweet/scripts/run_tweet.sh
RUN chmod +x /opt/tweet/scripts/run_tweet.sh
