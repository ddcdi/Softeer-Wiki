FROM w3m4:latest

# MovieLens rating count(Hadoop Streaming) job files
COPY src/mapper.py /opt/movielen/src/mapper.py
COPY src/reducer.py /opt/movielen/src/reducer.py
COPY scripts/run_movielen.sh /opt/movielen/scripts/run_movielen.sh
RUN chmod +x /opt/movielen/scripts/run_movielen.sh
