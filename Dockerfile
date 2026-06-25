FROM yashindane/chesslens-base:v1

MAINTAINER Yash Indane

EXPOSE 87

RUN mkdir /chesslens

COPY . /chesslens

WORKDIR /chesslens

ENTRYPOINT ["python3", "app.py"]
