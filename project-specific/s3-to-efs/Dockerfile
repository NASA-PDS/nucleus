FROM ubuntu:18.04

RUN apt-get update && apt-get install -y curl && apt-get install -y unzip && apt-get install -y sudo && apt-get install -y nfs-common

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && ./aws/install

RUN rm -rf aws && rm awscliv2.zip

ADD data-prep.sh /

RUN chmod +x /data-prep.sh

CMD ["/bin/bash", "-c", "/data-prep.sh"]
