FROM w3m5:latest

# Amazon Review rating count(Hadoop Streaming) job files
COPY src/mapper.py /opt/amazon_review/src/mapper.py
COPY src/reducer.py /opt/amazon_review/src/reducer.py
COPY scripts/run_amz.sh /opt/amazon_review/scripts/run_amz.sh
RUN chmod +x /opt/amazon_review/scripts/run_amz.sh
